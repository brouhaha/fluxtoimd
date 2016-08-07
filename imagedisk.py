#!/usr/bin/env python3
# ImageDisk library
# Copyright 2016 Eric Smith <spacewar@gmail.com>

# ImageDisk software and documentation can be found at:
#   http://www.classiccmp.org/dunfield/img/index.htm
# The ImageDisk file format is documented in chapter 6
# of IMD.TXT in the ImageDisk binary ZIP archive.

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
import datetime
from collections import OrderedDict

from modulation import FM, MFM, IntelM2FM


class ImageDisk:
    class NotImageDiskFileException(Exception):
        pass

    class DuplicateSectorException(Exception):
        pass
    
    class MixedModeTrackException(Exception):
        pass

    class InvalidSectorSizeException(Exception):
        pass
    
    class NonexistentSectorException(Exception):
        pass

    class Sector:
        def __init__(self, mode, deleted, size_code, data):
            self.mode = mode
            self.deleted = deleted
            self.size_code = size_code
            self.data = data
    
    __sector_size_map = { 128: 0,
                          256: 1,
                          512: 2,
                          1024: 3,
                          2048: 4,
                          4096: 5 }


    def write_sector(self, mode, cylinder, head, sector, data, deleted = False, replace_ok = False):
        track_coord = (cylinder, head)
        if track_coord not in self.tracks:
            self.tracks[track_coord] = OrderedDict()
        if (not replace_ok) and (sector in self.tracks[track_coord]):
            raise DuplicateSectorException('duplicate sector, cyl=%d, head=%d, sector=%d' % (cylinder, head, sector))
        if len(data) not in self.__sector_size_map:
            raise InvalidSectorSizeException('invalid sector size, cyl=%d, head=%d, sector=%d, size=%d' % (cylinder, head, sector, len(data)))
        self.tracks[track_coord][sector] = ImageDisk.Sector(mode, deleted, self.__sector_size_map[len(data)], data)


    def __read_track(self, f):
        header = f.read(5)
        if len(header) != 5:
            raise EOFError()
        mode = header[0]
        cylinder = header[1]
        head = header[2]
        sector_count = header[3]
        sector_size_code = header[4]
        sector_size_codes = [sector_size_code] * sector_count
        sector_numbers = f.read(sector_count)
        # XXX optional cylinder map not yet supported
        # XXX optional head map not yet supported
        if sector_size_code == 0xff:
            sector_size_codes = f.read(sector_count)
        for i in range(sector_count):
            data_type = f.read(1)[0]
            assert data_type <= 0x08
            bad = data_type in [0x00, 0x05, 0x06, 0x07, 0x08]
            deleted = data_type in [0x03, 0x04, 0x07, 0x08]
            compressed = data_type in [0x02, 0x04, 0x06, 0x08]
            if compressed:
                data = f.read(1) * (128 << sector_size_codes[i])
            else:
                data = f.read(128 << sector_size_codes[i])
            self.write_sector(mode, cylinder, head, sector_numbers[i], data)


    # if a file or filename is specified as f, will read that image
    def __init__(self, f = None, comment = None, timestamp = None):
        self.tracks = { }
        if f:
            do_close = False
            if type(f) is str:
                f = open(f, 'rb')
            # XXX read header
            s = f.read(4)
            if s != b'IMD ':
                raise NotImageDiskFileException()
            c = 0
            while c != bytes([0x1a]):
                c = f.read(1)
            while True:
                try:
                    self.__read_track(f)
                except EOFError:
                    break
            if do_close:
                f.close()
        self.comment = comment
        if timestamp is None:
            self.timestamp = datetime.datetime.utcnow()
        else:
            self.timestamp = timestamp

    def read_sector(self, cylinder, head, sector):
        try:
            data = self.tracks[(cylinder, head)][sector].data
        except KeyError:
            raise NonexistentSectorException()
        return data

    def __write_track(self, f, tc):
        mode = None
        track = self.tracks[tc]
        sector_count = len(track)
        sector_size_code = None
        for sector_number in track:
            sector = track[sector_number]
            if mode is None:
                mode = sector.mode
            elif mode != sector.mode:
                raise MixedModeTrackException('mixed modes, cyl=%d, head=%d' % tc)
            if sector_size_code is None:
                sector_size_code = sector.size_code
            elif sector_size_code != sector.size_code:
                sector_size_code = 0xff  # indicate mixed sector sizes
            
        f.write(bytes([mode,
                       tc[0], # cylinder
                       tc[1], # head
                       sector_count,
                       sector_size_code]))
        f.write(bytes(track.keys())) # sector map
        # XXX doesn't currently support the optional cylinder map
        # XXX doesn't currently support the optional head map
        if sector_size_code == 0xff:
            # write sector size map
            f.write(bytes([sector.size_code for sector in track]))
        for sector_number in track:
            if track[sector_number].deleted:
                data_code = 0x03
            else:
                data_code = 0x01
            data = track[sector_number].data
            compress = data[1:] == data[:-1]
            if compress:
                f.write(bytes([data_code + 1]))
                f.write(data[0:1])
            else:
                f.write(bytes([data_code]))
                f.write(data)


    def write(self, f):
        do_close = False
        if type(f) is str:
            f = open(f, 'wb')
            do_close = True

        # write header
        dt = self.timestamp.strftime('%d/%m/%Y %H:%M:%S')
        f.write(bytes('IMD 1.18 %s\r' % dt, encoding='ascii'))
        if self.comment is not None:
            f.write(self.comment, '\r')
        f.write(bytes([0x1a]))

        tl = sorted(self.tracks.keys())
        for tc in tl:
            self.__write_track(f, tc)

        if do_close:
            f.close()


def auto_int(x):
    return int(x, 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'ImageDisk library test, writes an empty disk image',
                                     formatter_class = argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('image', type=argparse.FileType('wb'))
    
    parser_modulation = parser.add_mutually_exclusive_group(required = False)
    parser_modulation.add_argument('--fm',   action = 'store_const', const = FM,   dest = 'modulation', help = 'FM modulation, IBM 3740 single density')
    parser_modulation.add_argument('--mfm',  action = 'store_const', const = MFM,  dest = 'modulation', help = 'MFM modulation, IBM System/34 double density')
    parser_modulation.add_argument('--m2fm', action = 'store_const', const = IntelM2FM, dest = 'modulation', help = 'M2FM modulation, Intel MDS, SBC 202 double density')

    parser.add_argument('-t', '--tracks',  type = int, default = 77, help = 'tracks per side')
    parser.add_argument('-s', '--sectors', type = int, help = 'sectors per track')
    parser.add_argument('-b', '--bytes',   type = int, help = 'bytes per sector')
    parser.add_argument('-d', '--data',    type = auto_int, default = 0xe5, help = 'data byte to fill sectors')

    parser.set_defaults(modulation = FM)

    args = parser.parse_args()

    sectors = args.sectors
    if sectors is None:
        sectors = args.modulation.default_sectors_per_track

    bytes_per_sector = args.bytes
    if bytes_per_sector is None:
        bytes_per_sector = args.modulation.default_bytes_per_sector

    imd = ImageDisk()  # no file, so creating a new image
    
    head = 0
    for track in range(args.tracks):
        for sector in range(1, sectors + 1):
            imd.write_sector(args.modulation.imagedisk_mode, track, head, sector, bytes([args.data] * bytes_per_sector))
    imd.write(args.image)
