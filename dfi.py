#!/usr/bin/env python3
# DFI disk image format library
# Copyright 2016 Eric Smith <spacewar@gmail.com>

# File format documentation is at:
#   http://www.discferret.com/wiki/DFI_image_format

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
import operator
from collections import Counter

class DFIBlock:
    class __DeltaIter:
        def __init__(self, dfi_block):
            dfi_block.generate_flux_trans_rel()
            self.dfi_block = dfi_block
            self.index = 0

        def __iter__(self):
            return self

        def __next__(self):
            try:
                v = self.dfi_block.flux_trans_rel[self.index] * self.dfi_block.time_increment
                self.index += 1
                return v
            except IndexError:
                raise StopIteration

    def parse_data_version_1(self, data):
        time_inc = 0
        for b in data:
            if (b & 0x7f) == 0x00:
                time_inc += 127
            else:
                time_inc += (b & 0x7f)
                self.flux_trans_abs.append(time_inc)
        self.end_time = time_inc

    def parse_data_version_2(self, data):
        time_inc = 0
        for b in data:
            if (b & 0x7f) == 0x00:
                continue  # why should there ever be a zero byte???
            if (b & 0x7f) == 0x7f:
                time_inc += 127
            elif (b & 0x80) != 0:
                time_inc += (b & 0x7f)
                self.index_pos.append(time_inc)
                # break    # XXX break here to only use first revolution
            else:
                time_inc += (b & 0x7f)
                self.flux_trans_abs.append(time_inc)
        self.end_time = time_inc

    _parse_data = { 1: parse_data_version_1,
                    2: parse_data_version_2 }

    def coordinates(self):
        return (self.cylinder, self.head, self.sector)

    def __init__(self, dfi):
        self.dfi = dfi
        self.cylinder = dfi.get_16_be()
        self.head = dfi.get_16_be()
        self.sector = dfi.get_16_be()
        self.data_len = dfi.get_32_be()
        self.raw_data = dfi.read(self.data_len)
        self.time_increment = 1.0 / dfi.frequency

    def generate_flux_trans_abs(self):
        if hasattr(self, 'flux_trans_abs'):
            return
        self.index_pos = []
        self.flux_trans_abs = []
        self._parse_data[self.dfi.version](self, self.raw_data)

    def generate_flux_trans_rel(self):
        if hasattr(self, 'flux_trans_rel'):
            return
        self.generate_flux_trans_abs()
        self.flux_trans_rel = [self.flux_trans_abs[i] - self.flux_trans_abs[i-1] for i in range(1, len(self.flux_trans_abs))]

    def get_delta_iter(self):
        return self.__DeltaIter(self)

    def print_hist(self, bucket_size = 2.5):
        self.generate_flux_trans_rel()
        counts = Counter(self.flux_trans_rel)
        hist = { }
        for i in counts.keys():
            bucket = int((i + bucket_size / 2) // bucket_size)
            hist[bucket] = hist.get(bucket, 0) + counts[i]

        # maximum value
        m = max(hist.items(), key=operator.itemgetter(1))[1]

        # minimum, maximum keys
        f = min(hist.items(), key=operator.itemgetter(0))[0]        
        l = max(hist.items(), key=operator.itemgetter(0))[0]        

        for i in range(f, l + 1):
            c = hist.get(i, 0)
            s = '*' * int(65*c/m)
            if len(s) == 0 and c != 0:
                s = '.'
            print("%3.2f: %5d %s" % (i * bucket_size / (self.dfi.frequency / 1.0e6), c, s))


class DFI:
    def read(self, length):
        return self.f.read(length)

    def get_16_be(self):
        d = self.f.read(2)
        if len(d) != 2:
            raise EOFError()
        return (d[0]<<8) + (d[1])

    def get_32_be(self):
        d = self.f.read(4)
        if len(d) != 4:
            raise EOFError()
        return (d[0]<<24) + (d[1]<<16) + (d[2]<<8) + (d[3])

    magic_to_version = { b'DFER' : 1,
                         b'DFE2' : 2 }

    def __init__(self, f, frequency = 25.0e6):
        self.f = f
        self.frequency = frequency
        magic = self.f.read(4)
        if magic not in self.magic_to_version:
            raise Exception('bad magic ' + str(magic))
        self.version = self.magic_to_version[magic]

        self.blocks = {}
        while True:
            try:
                block = DFIBlock(self)
                self.blocks[block.coordinates()] = block
            except EOFError:
                break


# test program accepts command line arguments for 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'DFI library test, prints flux transition time histogram for a chosen track',
                                     formatter_class = argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('image', type=argparse.FileType('rb', 0))
    parser.add_argument('-s', '--side',       type=int,   help = 'head', default=0) # head
    parser.add_argument('-t', '--track',      type=int,   help = 'cylinder', default=0) # cylinder
    parser.add_argument('-f', '--frequency',  type=float, help = 'sample rate in MHz', default=25.0)
    parser.add_argument('-r', '--resolution', type=float, help = 'histogram resolution in us', default=0.2)
    args = parser.parse_args()
    image = DFI(args.image, frequency = args.frequency * 1.0e6)

    block = image.blocks[(args.track, args.side, 1)]

    bucket_size = int(args.frequency * args.resolution)
    block.print_hist(bucket_size = bucket_size)
