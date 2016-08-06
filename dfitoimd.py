#!/usr/bin/env python3
# data extraction from floppy disk flux transition images
# Copyright 2016 Eric Smith <spacewar@gmail.com>

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

from adpll import ADPLL
from crc import CRC
from dfi import DFI
from imagedisk import ImageDisk


def hex_dump(b, prefix = ''):
    for i in range(0, len(b), 16):
        print(prefix + '%02x: ' % i, end='')
        for j in range(16):
            if (i + j) < len(b):
                print('%02x ' % b[i+j], end='')
            else:
                print('   ', end='')
        for j in range(16):
            if (i + j) < len(b):
                if 0x20 <= b[i+j] <= 0x7e:
                    print('%c' % b[i+j], end='')
                else:
                    print('.', end='')
        print()


class Modulation:
    # bits is a string of channel bits ('0' or '1'), which are nominally
    # pairs of (clock, data)
    # XXX this presently doesn't verify that the clock bits meet the
    # encoding rules
    @staticmethod
    def decode(channel_bits):
        bytes = []
        bits = ''
        for i in range(0, len(channel_bits), 2):
            clock = int(channel_bits[i])
            data = int(channel_bits[i+1])
            bits += '01'[data]
            if len(bits) == 8:
                bytes.append(int(bits, 2))
                bits = ''
        return bytes
    

class FM(Modulation):

    default_bit_rate_kbps = 250
    default_sectors_per_track = 26
    imagedisk_mode = 0x00

    crc_init = 0xffff

    id_to_data_half_bits = 400

    # Would prefer to use a more general @staticmethod encode, but then can't call in
    # class initialization
    def encode_mark(data, clock):
        bits = ''
        for i in range(7, -1, -1):
            c = (clock >> i) & 1
            d = (data  >> i) & 1
            bits += ('%d%d' % (c, d))
        return bits

    index_address_mark         = encode_mark(0xfc, clock = 0xd7)
    id_address_mark            = encode_mark(0xfe, clock = 0xc7)
    data_address_mark          = encode_mark(0xfb, clock = 0xc7)
    deleted_data_address_mark  = encode_mark(0xf8, clock = 0xc7)

    del encode_mark


class MFM(Modulation):

    default_bit_rate_kbps = 500
    default_sectors_per_track = 26
    imagedisk_mode = 0x03

    # Would prefer to use a more general @staticmethod encode, but then can't call in
    # class initialization
    def encode_mark(data1, clock1, data2):
        prev_d = 0
        bits = ''
        for i in range(7, -1, -1):
            c = (clock1 >> i) & 1
            d = (data1  >> i) & 1
            bits += ('%d%d' % (c, d))
            prev_d = d
        for i in range(7, -1, -1):
            d = (data2  >> i) & 1
            if prev_d == 0 and d == 0:
                c = 1
            else:
                c = 0
            bits += ('%d%d' % (c, d))
            prev_d = d
        return bits

    index_address_mark         = encode_mark(0xc2, 0xd7, 0xfc)
    id_address_mark            = encode_mark(0xa1, 0xc7, 0xfe)
    data_address_mark          = encode_mark(0xa1, 0xc7, 0xfb)
    deleted_data_address_mark  = encode_mark(0xa1, 0xc7, 0xf8)

    del encode_mark
    


class IntelM2FM(Modulation):

    default_bit_rate_kbps = 500
    default_sectors_per_track = 52
    imagedisk_mode = 0x03  # ImageDisk doesn't (yet?) have a defined mode for
                           # Intel M2FM

    crc_init = 0x0000

    id_to_data_half_bits = 600

    # Would prefer to use a more general @staticmethod encode, but then can't call in
    # class initialization
    def encode_mark(data, clock):
        bits = ''
        for i in range(7, -1, -1):
            c = (clock >> i) & 1
            d = (data  >> i) & 1
            bits += ('%d%d' % (c, d))
        return bits

    index_address_mark         = encode_mark(0x0c, clock = 0x71)
    id_address_mark            = encode_mark(0x0e, clock = 0x70)
    data_address_mark          = encode_mark(0x0b, clock = 0x70)
    deleted_data_address_mark  = encode_mark(0x08, clock = 0x72)

    del encode_mark



def dump_track(modulation, image, track, sectors_per_track = None):

    if sectors_per_track is None:
        sectors_per_track = modulation.default_sectors_per_track

    sectors = [None] * (sectors_per_track + 1)   # index 0 not used

    block = image.blocks[(track, 0, 1)]

    di = block.get_delta_iter()

    adpll = ADPLL(di,
                  osc_period = hbc,
                  max_adj_pct = 3.0,
                  window_pct = 50.0,
                  freq_adj_factor = 0.005,
                  phase_adj_factor = 0.1)


    bits = ''
    for b in adpll:
        bits += '01'[b]
    #print(len(bits))

    id_address_mark_locs = [m.start() for m in re.finditer(modulation.id_address_mark, bits)]
    #print('id address marks at: ', id_address_mark_locs)


    for id_pos in id_address_mark_locs:
        #print('id field at channel bit %d' % id_pos)
        id_field = modulation.decode(bits[id_pos: id_pos + len(modulation.id_address_mark) + 96])
        crc.reset()
        crc.comp(id_field)
        if crc.get() != 0:
            print("*** bad ID field CRC %04x" % crc.get())
            hex_dump(id_field)
            continue
        id_track, id_head, id_sector, id_size = id_field[1:5]
        if id_track != track:
            print("*** ID field with wrong track number")
            hex_dump(id_field)
            continue
        if id_size != 0:
            print("*** ID field with sector size")
            hex_dump(id_field)
            continue
        if sectors [id_sector] is not None:
            continue
        bc = 128 << id_size

        deleted = False
        data_pos = bits.find(modulation.data_address_mark, id_pos + len(modulation.id_address_mark) + 96)
        if (modulation.id_to_data_half_bits - 50) <= (data_pos - id_pos) <= (modulation.id_to_data_half_bits + 50):
            #print('  data at channel bit offset %d' % (data_pos - id_pos))
            pass
        else:
            data_pos = bits.find(modulation.deleted_data_address_mark, id_pos + len(modulation.id_address_mark) + 96)
            if (modulation.id_to_data_half_bits - 50) <= (data_pos - id_pos) <= (modulation.id_to_data_half_bits + 50):
                #print('  deleted data at channel bit offset %d' % (deleted_data_pos - id_pos))
                deleted = True
            else:
                print('*** ID field without data field ***')
                hex_dump(id_field)
                continue

        data_field = modulation.decode(bits[data_pos: data_pos + len(modulation.id_address_mark) + (bc + 2) * 16])
        crc.reset()
        crc.comp(data_field)
        if crc.get() != 0:
            print("*** bad data field CRC")
            continue

        sectors [id_sector] = (deleted, data_field[1:bc+1])

    return sectors


parser = argparse.ArgumentParser(description = 'DFI library test, prints flux transition time histogram for a chosen track',
                                     formatter_class = argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('dfi_image', type=argparse.FileType('rb'))
parser.add_argument('imagedisk_image', type=argparse.FileType('wb'))

parser_modulation = parser.add_mutually_exclusive_group(required = False)
parser_modulation.add_argument('--fm',   action = 'store_const', const = FM,   dest = 'modulation', help = 'FM modulation, IBM 3740 single density')
parser_modulation.add_argument('--mfm',  action = 'store_const', const = MFM,  dest = 'modulation', help = 'MFM modulation, IBM System/34 double density')
parser_modulation.add_argument('--m2fm', action = 'store_const', const = IntelM2FM, dest = 'modulation', help = 'M2FM modulation, Intel MDS, SBC 202 double density')

parser.set_defaults(modulation = 'fm')

parser.add_argument('-f', '--frequency',  type=float, help = 'sample rate in MHz', default=25.0)
parser.add_argument('-b', '--bit-rate',   type=float, help = 'bit rate in Kbps')
parser.add_argument('-v', '--verbose',    action = 'store_true')
args = parser.parse_args()

dfi_image = DFI(args.dfi_image, frequency = args.frequency * 1.0e6)

if args.imagedisk_image is not None:
    imd = ImageDisk()

if args.bit_rate is None:
    args.bit_rate = args.modulation.default_bit_rate_kbps


crc_param = CRC.CRCParam(name = 'CRC-16-CCITT',
                         order = 16,
                         poly = 0x1021,
                         init = args.modulation.crc_init,
                         xorot = 0x0000,
                         refin = False,
                         refot = False)


crc = CRC(crc_param)
crc.make_table(8)


hbr = args.bit_rate * 2000   # half-bit rate in Hz
hbc = 1/hbr                  # half-bit cycle in s


tracks = [None] * 77
for track in range(77):
    tracks [track] = dump_track(args.modulation, dfi_image, track)



sectors_per_track = args.modulation.default_sectors_per_track

data_sectors = 0
deleted_sectors = 0
total = 0
for track in range(77):
    if args.imagedisk_image is not None:
        for sector in range(1, sectors_per_track + 1):
            deleted = tracks[track][sector][0]
            data = tracks[track][sector][1]
            imd.write_sector(args.modulation.imagedisk_mode,
                             track,  # cylinder
                             0,      # head
                             sector,
                             bytes(data),
                             deleted = deleted)
    if args.verbose:
        print('%2d: ' % track, end='')
        for sector in range(1, sectors_per_track + 1):
            total += 1
            data = tracks[track][sector]
            if data is not None:
                if data[0]:
                    print('D', end='')
                    deleted_sectors += 1
                else:
                    print('.', end='')
                    data_sectors += 1
            else:
                print('*', end='')
        print()

if args.imagedisk_image is not None:
    imd.write(args.imagedisk_image)

if args.verbose:
    print('%d data sectors, %d deleted data sectors, out of %d' % (data_sectors, deleted_sectors, total))

