from collections import Counter, namedtuple
import operator
import struct

CHS = namedtuple('CHS', ['cylinder', 'head', 'sector'])

'''A FluxImageBlock represents one flux image, which is a single track
   for a soft-sectored disk, or a single sector for a hard-sectored disk'''
class FluxImageBlock:
    def __init__(self, fluximagefile, debug = False):
        self.fluximagefile = fluximagefile
        self.debug = debug
        self.stream_offset = 0

    def chs(self):
        return CHS(self.cylinder, self.head, self.sector)

    def read(self, count):
        d = self.fluximagefile.read(count)
        if len(d) != count:
            raise EOFError()
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

    class __DeltaIter:
        def __init__(self, block):
            block.generate_flux_trans_rel()
            self.block = block
            self.index = 0

        def __iter__(self):
            return self

        def __next__(self):
            try:
                v = self.block.flux_trans_rel[self.index] / self.block.frequency
                self.index += 1
                return v
            except IndexError:
                raise StopIteration

    def generate_flux_trans_rel(self):
        if hasattr(self, 'flux_trans_rel'):
            return
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
            print("%3.2f: %5d %s" % (i * bucket_size / (self.frequency / 1.0e6), c, s))


class FluxImageDummyBlock(FluxImageBlock):
    def __init__(self, frequency, head, cylinder):
        self.frequency = frequency
        self.cylinder = cylinder
        self.head = head
        self.sector = 1
        self.index_pos = [0]
        self.flux_trans_abs = [0]
        self.flux_trans_rel = [0]


class FluxImage:
    def __init__(self, fluximagefile, debug = False):
        self.fluximagefile = fluximagefile
        self.debug = debug
        self.blocks = { }

