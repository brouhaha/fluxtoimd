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

import datetime
from collections import OrderedDict

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
        mode = f.read(1)
        if mode == b'':
            raise EOFError()
        cylinder = f.read(1)
        head = f.read(1)
        sector_count = f.read(1)
        sector_size_code = f.read(1)
        sector_numbers = [None] * sector_count
        sector_size_codes = [sector_size_code] * sector_count
        for i in range(sector_count):
            sector_numbers[i] = f.read(1)
        # XXX optional cylinder map not supported
        # XXX optional head map not supported
        if sector_size_code == 0xff:
            for i in range(sector_count):
                sector_size_codes[i] = f.read(1)
        for i in range(sector_count):
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
            while c != 0x1a:
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
            data = self.tracks[(cylinder, head)][sector][2]
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
                f.write(bytes([0x03]))
            else:
                f.write(bytes([0x01]))
            f.write(track[sector_number].data)


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


if __name__ == '__main__':
    imd = ImageDisk()
    for track in range(77):
        for sector in range(1, 27):
            imd.write_sector(0x00, track, 0x00, sector, bytes([0xe5] * 128))
    imd.write('foo.imd')
