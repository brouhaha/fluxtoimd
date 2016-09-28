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
import re
import zipfile

from fluximage import FluxImage, FluxImageBlock

class KyroFluxStreamOOBBlock:
    def __init__(self, kfs, length):
        self.kfs = kfs
        self.length = length

        self.read_oob_payload()

        read_length = (kfs.stream_offset - kfs.block_offset) - 4
        if (not kfs.logical_eof) and (self.length != read_length):
            raise Exception('Internal error: OOB block length %d, but expected %d bytes' % (self.length, read_length))

        # OOB blockfs don't count toward stream offset!
        kfs.stream_offset = kfs.block_offset

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
        pos_error = self.kfs.block_offset - self.stream_pos
        self.xfer_time  = self.kfs.read_u32_le()

        if (self.kfs.debug):
            print('StreamInfo at %d' % self.kfs.block_offset)
            print('  stream_pos:     %d' % self.stream_pos, end='')
            if pos_error:
                print('  (error %d)' % pos_error, end='')
            print()
            print('  xfer_time:      %d' % self.xfer_time)

@KyroFluxStreamOOBBlock.register_subclass(0x02)
class KyroFluxIndex(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        self.index_number = self.kfs.index_count
        self.kfs.index_count += 1
        
        self.next_flux_stream_pos  = self.kfs.read_u32_le()
        self.sample_counter        = self.kfs.read_u32_le()
        self.index_counter         = self.kfs.read_u32_le()

        if self.kfs.debug:
            print('Index %d at stream %d' % (self.index_number, self.kfs.block_offset))
            print('  next_flux_stream_pos:  %d' % self.next_flux_stream_pos)
            print('  sample_counter:        %d' % self.sample_counter)
            print('  index_counter:         %d' % self.index_counter)

    def found_target_flux(self, prev_flux_sample_counter, flux_sample_counter):
        self.index_abs = prev_flux_sample_counter + self.sample_counter
        self.kfs.index_abs.append(self.index_abs)
        if self.kfs.debug:
            print('post index %d flux transition found at sample count %d' % (self.index_number, self.index_abs))
            

@KyroFluxStreamOOBBlock.register_subclass(0x03)
class KyroFluxStreamEnd(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        self.stream_pos  = self.kfs.read_u32_le()
        pos_error = self.kfs.block_offset - self.stream_pos
        self.result_code = self.kfs.read_u32_le()
        self.kfs.stream_end = True

        if self.kfs.debug:
            print('StreamEnd at %d' % self.kfs.block_offset)
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
        fields = [i.split('=') for i in text[:-1].split(', ')]
        self.kfs.info.update(dict(fields))

        if self.kfs.debug:
            print('Info at %d' % self.kfs.block_offset)
            for (k, v) in fields:
                print('  %s=%s' % (k, v))

@KyroFluxStreamOOBBlock.register_subclass(0x0d)
class KyroFluxEOF(KyroFluxStreamOOBBlock):
    def read_oob_payload(self):
        self.kfs.logical_eof = True

        if self.kfs.debug:
            print('Logical EOF at %d' % self.kfs.block_offset)

class KyroFluxStream(FluxImageBlock):
    def flux_change(self, offset):
        # record flux change here
        self.flux_sample_counter += self.overflow + offset
        self.overflow = 0

        self.flux_trans_abs.append(self.flux_sample_counter)

        if self.stream_offset in self.pending_index_blocks:
            index = self.pending_index_blocks[self.stream_offset]
            index.found_target_flux(self.prev_flux_sample_counter,
                                    self.flux_sample_counter)
            del self.pending_index_blocks[self.stream_offset]

        self.prev_flux_sample_counter = self.flux_sample_counter

        if self.debug:
            print('flux at %d' % self.flux_sample_counter)

    def get_block(self):
        self.block_offset = self.stream_offset
        try:
            bt = self.read_u8()
        except EOFError:
            print('unexpected EOF')
            self.logical_eof = True
            return
        if bt != 0x0d and self.stream_end:
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
            if self.debug:
                print('overflow')
        elif bt == 0x0c: # Flux3
            self.flux_change(self.read_u16_le)
        elif bt == 0x0d: # OOB
            block = KyroFluxStreamOOBBlock.factory(self)
            self.oob_blocks.append(block)
            if isinstance(block, KyroFluxIndex):
                self.pending_index_blocks[block.next_flux_stream_pos] = block
        else: # 0x0e..0xff: Flux1
            self.flux_change(bt)

    def __init__(self, fluximagefile, debug = False):
        super().__init__(fluximagefile, debug)
        self.info = { }
        self.overflow = 0
        self.stream_end = False
        self.logical_eof = False

        self.prev_flux_sample_counter = 0
        self.flux_sample_counter = 0
        self.flux_trans_abs = [ ]

        self.oob_blocks = [ ]

        self.index_count = 0
        self.pending_index_blocks = { }
        self.index_abs = [ ]

        while not self.logical_eof:
            self.get_block()

        try:
            self.frequency = float(self.info['sck'])
        except:
            self.frequency = 18.432e6 * 73 / 56

        if self.pending_index_blocks:
            print('%d unresolved index blocks' % len(self.pending_index_blocks))


class KFSF(FluxImage):
    def __init__(self, fluximagefile, debug = False):
        super().__init__(fluximagefile, debug)
        
        try:
            zf = zipfile.ZipFile(fluximagefile)
        except:
            zf = None

        if zf is None:
            head = 0
            track = 0
            self.blocks[(track, head, 1)] = KyroFluxStream(fluximagefile, debug = debug)
        else:
            for fn in zf.namelist():
                #print(fn)
                m = re.match('.*track([0-9]{2})\.([0-9])\.raw$', fn)
                if m:
                    head = int(m.group(2))
                    track = int(m.group(1))
                    if True:
                        print('reading head %d track %02d' % (head, track))
                    try:
                        with zf.open(fn) as f:
                            self.blocks[(track, head, 1)] = KyroFluxStream(f, debug = debug)
                    except Exception as e:
                        print('%s reading head %d track %02d' % (str(e), head, track))


# test program accepts command line arguments for 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'KFSF library test, prints flux transition time histogram for a chosen track',
                                     formatter_class = argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('image', type=argparse.FileType('rb', 0))
    parser.add_argument('-s', '--side',       type=int,   help = 'head', default=0) # head
    parser.add_argument('-t', '--track',      type=int,   help = 'cylinder', default=0) # cylinder
    parser.add_argument('-r', '--resolution', type=float, help = 'histogram resolution in us', default=0.2)
    parser.add_argument('-d', '--debug',      action='store_true', help = 'print debugging information')
    args = parser.parse_args()

    image = KFSF(args.image, debug = args.debug)

    block = image.blocks[(args.track, args.side, 1)]

    bucket_size = int(block.frequency * args.resolution / 1.0e6)
    block.print_hist(bucket_size = bucket_size)
