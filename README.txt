fluxtoimd.py is a Python 3 program to read floppy disk flux transitions
images, demodulate the data, and write the data to an ImageDisk image file.
DiscFerret (.dfi) images and ZIP files of KryoFlux Stream File images are
supported as input.

Copyright 2016 Eric Smith <spacewar@gmail.com>

    This program is free software: you can redistribute it and/or
    modify it under the terms of version 3 of the GNU General Public
    License as published by the Free Software Foundation.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see
    <http://www.gnu.org/licenses/>.

Currently fluxtoimd.py only supports 8-inch floppy disks in either IBM
3740 FM single-sided single-density 128 byte/sector format, or Intel
M2FM single-sided double-density M2FM 128 byte/sector format as used
by Intel MDS 800/Series II/Series III development systems using the
Intel SBC 202 floppy controller.  Additional format flexibility may be
added later; the motivation for developing fluxtoimd.py was
specifically to deal double-density Intel MDS disks.
