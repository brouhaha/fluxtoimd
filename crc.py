#!/usr/bin/env python3
# parameterized CRC implementation
# Copyright 2016 Eric Smith <spacewar@gmail.com>

# supports operation on arbitrary data word widths

# supports table-driven operation with selectable table size(s)
# for common 8-bit use, after instantiation, call make_table(8)

# Algorithms defined per section 14 of "A Painless Guide to CRC
# Error Detection Algorithms" by Ross N. Williams:
#   http://www.ross.net/crc/download/crc_v3.txt

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

from collections import namedtuple
import struct

class CRC:

    CRCParam = namedtuple('CRCParam',
                          ['name',
                           'order',
                           'poly',
                           'init',
                           'xorot',
                           'refin',    # reflect input data
                           'refot'])   # reflect output word
    
    crc16_ccitt_param = CRCParam(name = 'CRC-16-CCITT',
                                 order = 16,
                                 poly = 0x1021,
                                 init = 0xffff,
                                 xorot = 0x0000,
                                 refin = False,
                                 refot = False)

    crc32_param = CRCParam(name = 'CRC-32',
                           order = 32,
                           poly = 0x04c11db7,
                           init = 0xffffffff,
                           xorot = 0xffffffff,
                           refin = True,
                           refot = True)

    crc32_bzip2_param = CRCParam(name = 'CRC-32/BZIP2',
                                 order = 32,
                                 poly = 0x04c11db7,
                                 init = 0xffffffff,
                                 xorot = 0xffffffff,
                                 refin = False,
                                 refot = False)

    # Catagnoli polynomial
    crc32c_param = CRCParam(name = 'CRC-32C',
                            order = 32,
                            poly = 0x1edc6f41,
                            init = 0xffffffff,
                            xorot = 0xffffffff,
                            refin = True,
                            refot = True)

    def __init__(self,
                 param):
        self.tables = { }
        self.cache = { }
        self.param = param
        self.reg = param.init
        self.widmask = (1 << self.param.order) - 1
        self.topbit = 1 << (self.param.order - 1)

    def reset(self):
        self.reg = self.param.init
        
    def reflect(self, data, bit_count):
        d1 = data
        d2 = 0
        for b in range(bit_count):
            d2 <<= 1
            if d1 & 1:
                d2 |= 1
            d1 >>= 1
        #print("%02x %02x" % (data, d2))
        return d2
                
    # this one works only for bit_count <= self.param.order
    def comp1(self, data, bit_count = 8):
        if self.param.refin:
            data = self.reflect(data, bit_count)
        self.reg ^= data << (self.param.order - bit_count)
        for b in range(bit_count):
            if self.reg & self.topbit:
                self.reg = (self.reg << 1) ^ self.param.poly
            else:
                self.reg <<= 1
            self.reg &= self.widmask

    # this one doesn't restrict bit_count
    def comp2(self, data, bit_count = 8):
        if self.param.refin:
            r = range(bit_count)
        else:
            r = range(bit_count - 1, -1, -1)
        for b in r:
            self.reg ^= ((data >> b) & 1) << (self.param.order - 1)
            if self.reg & self.topbit:
                self.reg = (self.reg << 1) ^ self.param.poly
            else:
                self.reg <<= 1
            self.reg &= self.widmask

    def find_table(self, bit_count):
        self.cache[bit_count] = 0  # assume no suitable table
        for i in range(bit_count, 1, -1):
            if i in self.tables:
                self.cache[bit_count] = i
                return

    def comp_int(self, data, bit_count = 8):
        if self.param.refin:
            data = self.reflect(data, bit_count)
        while bit_count > 0:
            if bit_count not in self.cache:
                self.find_table(bit_count)
            table_size = self.cache[bit_count]
            if table_size:
                b = data >> (bit_count - table_size) & ((1 << table_size) - 1)
              
                self.reg = self.tables[table_size][(self.reg >> (self.param.order - table_size)) ^ b] ^ (self.reg << table_size)
                self.reg &= self.widmask
                bit_count -= table_size
            else:
                b = (data >> bit_count - 1) & 1
                self.reg ^= b << (self.param.order - 1)
                if self.reg & self.topbit:
                    self.reg = (self.reg << 1) ^ self.param.poly
                else:
                    self.reg <<= 1
                self.reg &= self.widmask
                bit_count -= 1

    def comp(self, data, bit_count = 8):
        try:
            for b in data:
                self.comp_int(b, bit_count)
        except TypeError:
            self.comp_int(data, bit_count)

    def make_table_entry(self, d, bit_count):
        v = 0
        for b in range(bit_count - 1, -1, -1):
            b = (d >> bit_count - 1) & 1
            v ^= b << (self.param.order - 1)
            if v & self.topbit:
                v = (v << 1) ^ self.param.poly
            else:
                v <<= 1
            v &= self.widmask
            bit_count -= 1
        return v
                        
    def make_table(self, bit_count = 8):
        if bit_count in self.tables:
            return
        assert bit_count > 1

        self.cache = { }

        self.tables[bit_count] = [self.make_table_entry(i, bit_count) for i in range(1 << bit_count)]

        #for i in range(len(self.tables[bit_count])):
        #    print("%02x: %08x" % (i, self.tables[bit_count][i]))

    def get(self):
        if self.param.refot:
            return self.reflect(self.reg ^ self.param.xorot, self.param.order)
        else:
            return self.reg ^ self.param.xorot

    def crc(self, data):
        self.reset()
        self.comp(data)
        return self.get()


if __name__ == '__main__':

    pass_count = 0
    fail_count = 0

    def test(param, data, expected_value, use_table = True):
        global pass_count, fail_count
        crc = CRC(param)
        if use_table:
            crc.make_table(5)
            crc.make_table(3)
        for b in data:
            crc.comp(b)
        v = crc.get()
        if v == expected_value:
            print('%s OK' % param.name)
            pass_count += 1
        else:
            print('%s crc result %08x, expected %08x' % (param.name, v, expected_value))
            fail_count += 1
    

    def swap32(i):
        return struct.unpack("<I", struct.pack(">I", i))[0]


    # http://reveng.sourceforge.net/crc-catalogue/17plus.htm
    # http://stackoverflow.com/questions/1918090/crc-test-vectors-for-crc16-ccitt
    vector = [ord(c) for c in '123456789']
    test(CRC.crc16_ccitt_param, vector, 0x29b1)
    test(CRC.crc32_param,       vector, 0xcbf43926)
    test(CRC.crc32_bzip2_param, vector, 0xfc891918)
    test(CRC.crc32c_param,      vector, 0xe3069283)


    # Test vectors for CRC-32C from RFC3270:
    #   https://tools.ietf.org/html/rfc3720#appendix-B.4
    test(CRC.crc32c_param, [0x00] * 32,       swap32(0xaa36918a))
    test(CRC.crc32c_param, [0xff] * 32,       swap32(0x43aba862))
    test(CRC.crc32c_param, range(32),         swap32(0x4e79dd46))
    test(CRC.crc32c_param, range(31, -1, -1), swap32(0x5cdb3f11))

    print("%d passed, %d failed" % (pass_count, fail_count))

