import struct

from fluximage import CHS, FluxImage, FluxImageBlock, FluxImageDummyBlock

class SCPBlock(FluxImageBlock):

    def __init__(self, fluximagefile, frequency, head, cylinder, revolutions, debug = False):
        super().__init__(fluximagefile, debug)
        self.frequency = frequency
        self.head = head
        self.cylinder = cylinder
        self.sector = 1

        if self.debug:
            print('head %d, cylinder %d' % (self.head, self.cylinder))

        magic = self.fluximagefile.read(3)
        if magic != b'TRK':
            raise Exception('bad magic ' + str(magic))
        trk_no = self.read_u8()
        trk_duration = []
        trk_len = []
        trk_ptr = []

        for _ in range(revolutions):
            trk_duration.append(self.read_u32_le())
            trk_len.append(self.read_u32_le())
            trk_ptr.append(self.read_u32_le())

        self.index_pos = []
        self.flux_trans_abs = []
        time_inc = 0
        for r in range(revolutions):
            if self.debug:
                print('revolution %d, length %d' % (r+1, trk_len[r]))
            for _ in range(trk_len[r]):
                time_inc += self.read_u16_be()
                self.flux_trans_abs.append(time_inc)
            if trk_len[r] > 0:
                self.index_pos.append(time_inc)
                self.end_time = time_inc



class SCP(FluxImage):

    def read_u8(self):
        return struct.unpack('<B', self.fluximagefile.read(1))[0]

    def read_s8(self):
        return struct.unpack('<b', self.fluximagefile.read(1))[0]

    def read_u32_le(self):
        return struct.unpack('<I', self.fluximagefile.read(4))[0]

    def __init__(self, fluximagefile, debug = False):
        super().__init__(fluximagefile, debug)

        magic = self.fluximagefile.read(3)
        if magic != b'SCP':
            raise Exception('bad magic ' + str(magic))

        version = self.read_u8()
        subversion = version%16
        version = version/16
        type = self.read_u8()
        revolutions = self.read_u8()
        starttrack = self.read_u8()
        endtrack = self.read_u8()
        flags = self.read_u8()
        width = self.read_u8()
        head_cfg = self.read_s8()
        main_head = (0, 0, 1)[head_cfg]
        heads = (2, 1, 1)[head_cfg]
        self.frequency = 40e6/(self.read_u8()+1)
        checksum = self.read_u32_le()

        if self.debug:
            print('freq %f, %i head(s), track %i -> %i, %i revolutions' % (self.frequency, heads, starttrack, endtrack, revolutions))

        track_ptrs = []
        for track in range(starttrack, endtrack+1):
            track_ptrs.append(self.read_u32_le())
            if heads == 1:
                track_ptrs.append(self.read_u32_le())

        self.blocks = {}
        for track in range(starttrack, endtrack+1):
            if debug:
                print('Loading track ' + str(track))
            if track_ptrs[track] != 0:
                fluximagefile.seek(track_ptrs[track])
                block = SCPBlock(fluximagefile, self.frequency, main_head + track%heads, int(track/heads), revolutions, debug = self.debug)
            elif heads != 1:
                block = FluxImageDummyBlock(self.frequency, main_head + track%heads, int(track/heads))
            if debug:
                print('CHS ' + str(block.chs()))
            self.blocks[block.chs()] = block