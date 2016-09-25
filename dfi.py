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

from fluximage import FluxImage, FluxImageBlock

class DFIBlock(FluxImageBlock):
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

    def __init__(self, fluximagefile, version, frequency, debug = False):
        super().__init__(fluximagefile, debug)
        self.version = version
        self.frequency = frequency
        self.cylinder = self.read_u16_be()
        self.head = self.read_u16_be()
        self.sector = self.read_u16_be()

        if self.debug:
            print('version %d, freq %f' % (version, frequency))
            print('head %d, cylinder %d, sector %d' % (self.head,
                                                       self.cylinder,
                                                       self.sector))

        self.data_len = self.read_u32_be()
        self.raw_data = self.read(self.data_len)
        self.time_increment = 1.0 / frequency

    def generate_flux_trans_abs(self):
        if hasattr(self, 'flux_trans_abs'):
            return
        self.index_pos = []
        self.flux_trans_abs = []
        self._parse_data[self.version](self, self.raw_data)


class DFI(FluxImage):
    magic_to_version = { b'DFER' : 1,
                         b'DFE2' : 2 }

    def __init__(self, fluximagefile, debug = False, frequency = 25.0e6):
        super().__init__(fluximagefile, debug)
        self.frequency = frequency
        magic = self.fluximagefile.read(4)
        if magic not in self.magic_to_version:
            raise Exception('bad magic ' + str(magic))
        version = self.magic_to_version[magic]

        self.blocks = {}
        while True:
            try:
                block = DFIBlock(fluximagefile, version, frequency, debug = self.debug)
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
    parser.add_argument('-d', '--debug',      action='store_true', help = 'print debugging information')
    args = parser.parse_args()
    image = DFI(args.image, frequency = args.frequency * 1.0e6, debug = args.debug)

    block = image.blocks[(args.track, args.side, 1)]

    bucket_size = int(args.frequency * args.resolution)
    block.print_hist(bucket_size = bucket_size)
