fluxtoimd.py is a Python 3 program to read floppy disk flux transitions
images, demodulate the data, and write the data to an ImageDisk image file.
DiscFerret (.dfi) images and ZIP files of KryoFlux Stream File images are
supported as input.

Copyright © 2016 Eric Smith <spacewar@gmail.com>

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

Currently fluxtoimd.py supports 8-inch floppy disks in the following
formats:

* IBM 3740 FM single-density
  (industry-standard single density as used by most floppy controllers)

* Intel M2FM double-density 128 byte/sector format
  (used by SBC 202 floppy controller in Intel MDS 300/Series II/Series III
  development systems)

* HP M2FM double-density 256 byte/sector format
  (used by HP 7902, 9885, 9895)

There is untested code to support the following formats:

* IBM System/34 MFM double-density
  (industry standard double-density as used by most floppy controllers)

In principle the code should work with images of 5¼ inch and 3½ inch
floppy disks, but that has not been tested.
