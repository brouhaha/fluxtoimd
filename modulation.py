#!/usr/bin/env python3
# Magnetic disk modulation schemes
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
    

# FM is IBM 3740 single-density format
# standards, single-sided: ECMA 54, ISO 5654, ANSI X3.73
# standards, double-sided: ECMA 59

class FM(Modulation):

    default_bit_rate_kbps = 250
    default_sectors_per_track = 26
    default_bytes_per_sector = 128
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


# MFM is IBM System/34 double-density format
# standards: ECMA 69, ISO 7065, ANSI X3.121

class MFM(Modulation):

    default_bit_rate_kbps = 500
    default_sectors_per_track = 26
    default_bytes_per_sector = 256
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
    


# An Intel-proprietary M2FM floppy format, used by the Intel SBC 202
# floppy controller in Intel MDS 800, Series II, and Series III development
# systems.
# Documentation:
#   SBC 202 Double Density Diskette Controller Hardware Reference Manual,
#      Intel 1977, Order Number 9800420A
#   Intelled Double Density Diskette Operating System Hardware Reference Manual,
#      Intel 1977, Order Number 98-422A

class IntelM2FM(Modulation):

    default_bit_rate_kbps = 500
    default_sectors_per_track = 52
    default_bytes_per_sector = 128
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
