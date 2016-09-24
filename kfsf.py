#!/usr/bin/env python3
# KryoFlux stream file library
# Copyright 2016 Eric Smith <spacewar@gmail.com>

# KryoFlux stream file format is documented in:
#   http://www.kryoflux.com/download/kryoflux_stream_protocol_rev1.1.pdf

#    This program is free software: you can redistribute it and/or
#    modify it under the terms of version 3 of the GNU General Public
#    License as published by the Free Software Foundation.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see
#    <http://www.gnu.org/licenses/>.

import argparse
from collections import Counter
import io
import operator
import re
import struct
import zipfile

class KyroFluxStreamOOBBlock:
    def __init__(self, kfs, length):
        self.oob_header_offset = kfs.stream_offset - 4
        self.kfs = kfs
        self.length = length

        self.read_oob_payload()

        read_length = (kfs.stream_offset - self.oob_header_offset) - 4
        if (not kfs.logical_eof) and (self.length != read_length):
            raise Exception('Internal error: OOB block length %d, but expected %d bytes' % (self.length, read_length))

        # OOB blockfs don't count toward stream offset!
        kfs.stream_offset = self.oob_header_offset

    oob_type_map = { }

    @classmethod
    def register_subclass(cls, val):
        def inner(subclass):
            cls.oob_type_map[val] = subclass
            return subclass
        return inner
    
    @classmethod
    def factory(cls, kfs):
        oob_type = kfs.read_u8()
        oob_length = kfs.read_u16_le()
        if oob_type not in cls.oob_type_map:
            raise Exception('Unknown OOB block type %02x' % oob_type)
        return cls.oob_type_map[oob_type](kfs, oob_length)

@KyroFluxStreamOOBBlock.register_subclass(0x01)
class KyroFluxStreamInfo(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        self.stream_pos = self.kfs.read_u32_le()
        pos_error = self.oob_header_offset - self.stream_pos
        self.xfer_time  = self.kfs.read_u32_le()

        if (self.kfs.debug):
            print('StreamInfo at %d' % self.oob_header_offset)
            print('  stream_pos:     %d' % self.stream_pos, end='')
            if pos_error:
                print('  (error %d)' % pos_error, end='')
            print()
            print('  xfer_time:      %d' % self.xfer_time)

@KyroFluxStreamOOBBlock.register_subclass(0x02)
class KyroFluxIndex(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        self.next_flux_pos  = self.kfs.read_u32_le()
        self.sample_counter = self.kfs.read_u32_le()
        self.index_counter  = self.kfs.read_u32_le()

        if (self.kfs.debug):
            print('Index at %d' % self.oob_header_offset)
            print('  next_flux_pos:  %d' % self.next_flux_pos)
            print('  sample_counter: %d' % self.sample_counter)
            print('  index_counter:  %d' % self.index_counter)

@KyroFluxStreamOOBBlock.register_subclass(0x03)
class KyroFluxStreamEnd(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        self.stream_pos  = self.kfs.read_u32_le()
        pos_error = self.oob_header_offset - self.stream_pos
        self.result_code = self.kfs.read_u32_le()
        self.kfs.stream_end = True

        if self.kfs.debug:
            print('StreamEnd at %d' % self.oob_header_offset)
            print('  stream_pos:     %d' % self.stream_pos, end='')
            if pos_error:
                print('  (error %d)' % pos_error, end='')
            print()
            print('  result_code:    %d' % self.result_code)

@KyroFluxStreamOOBBlock.register_subclass(0x04)
class KyroFluxInfo(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        text = self.kfs.read(self.length).decode('ascii')
        if text[-1] != '\x00':
            raise Exception('Info text not null-terminated')
        fields = dict([i.split('=') for i in text[:-1].split(',')])
        self.kfs.info.update(fields)

        if self.kfs.debug:
            print('Info at %d' % self.oob_header_offset)

@KyroFluxStreamOOBBlock.register_subclass(0x0d)
class KyroFluxEOF(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        self.kfs.logical_eof = True

        if self.kfs.debug:
            print('Logical EOF at %d' % self.oob_header_offset)

class KyroFluxStream:
    def read(self, count):
        d = self.f.read(count)
        if len(d) != count:
            raise Exception('requested read of %d bytes, only %d available' % (count, len(d)))
        self.stream_offset += count
        return d

    def read_integer(self, count, signed = False, big_endian = False):
        fmt = '<>' [big_endian]
        fmt += { 1: 'b',
                 2: 'h',
                 4: 'i',
                 8: 'q' } [count]
        if not signed:
            fmt = fmt.upper()
        d = self.read(count)
        return struct.unpack(fmt, d) [0]

    def read_u8(self):
        return self.read_integer(1)

    def read_s8(self):
        return self.read_integer(1, signed = True)

    def read_u16_le(self):
        return self.read_integer(2)

    def read_u16_be(self):
        return self.read_integer(2, big_endian = True)

    def read_s16_le(self):
        return self.read_integer(2, signed = True)

    def read_s16_be(self):
        return self.read_integer(2, signed = True, big_endian = True)

    def read_u32_le(self):
        return self.read_integer(4)

    def read_u32_be(self):
        return self.read_integer(4, big_endian = True)

    def read_s32_le(self):
        return self.read_integer(4, signed = True)

    def read_s32_be(self):
        return self.read_integer(4, signed = True, big_endian = True)

    def flux_change(self, offset):
        # record flux change here
        self.overflow = 0

    def get_block(self):
        bt = self.read_u8()
        if self.stream_end and bt != 0x0d:
            raise Exception('In-band data past stream end')
        if bt <= 0x07:  # Flux2
            self.flux_change((bt << 8) + self.read_u8())
        elif bt == 0x08: # Nop1
            pass
        elif bt == 0x09: # Nop2
            self.read(1)
        elif bt == 0x0a: # Nop3
            self.read(2)
        elif bt == 0x0b: # Ovl16
            self.overflow += 0x10000
        elif bt == 0x0c: # Flux3
            self.flux_change(self.read_u16_le)
        elif bt == 0x0d: # OOB
            block = KyroFluxStreamOOBBlock.factory(self)
        else: # 0x0e..0xff: Flux1
            self.flux_change(bt)

    def __init__(self, f, debug = False):
        #self.f = io.BytesIO(f)
        self.f = f
        self.debug = debug
        self.info = { }
        self.stream_offset = 0
        self.overflow = 0
        self.stream_end = False
        self.logical_eof = False
        while not self.logical_eof:
            self.get_block()


class KFSF:
    def __init__(self, f):
        self.tracks = {}
        
        try:
            zf = zipfile.ZipFile(f)
        except:
            zf = None

        if zf is None:
            head = 0
            track = 0
            self.tracks[(head, track)] = KyroFluxStream(f)
        else:
            for fn in zf.namelist():
                #print(fn)
                m = re.match('.*track([0-9]{2})\.([0-9])\.raw$', fn)
                if m:
                    head = int(m.group(2))
                    track = int(m.group(1))
                    print('reading head %d track %02d' % (head, track))
                    with zf.open(fn) as f:
                        self.tracks[(head, track)] = KyroFluxStream(f)

# test program accepts command line arguments for 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'KSF library test, prints flux transition time histogram for a chosen track',
                                     formatter_class = argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('image', type=argparse.FileType('rb', 0))
    parser.add_argument('-r', '--resolution', type=float, help = 'histogram resolution in us', default=0.2)
    args = parser.parse_args()

    image = KFSF(args.image)

    block = image.blocks[(args.track, args.side, 1)]

    bucket_size = int(args.frequency * args.resolution)
    block.print_hist(bucket_size = bucket_size)
