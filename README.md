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
  (used by SBC 202 floppy controller in Intel MDS 800/Series II/Series III
  development systems)

* HP M2FM double-density 256 byte/sector format
  (used by HP 7902, 9885, 9895)

There is untested code to support the following formats:

* IBM System/34 MFM double-density
  (industry standard double-density as used by most floppy controllers)

In principle the code should work with images of 5¼ inch and 3½ inch
floppy disks, but that has not been tested.

USAGE:

To use with kryoflux to read Intel m2fm and fm disks (MDS/ISIS)

Read 8" single sided disk as stream file. Use -g2 to read double sided disks.
This reads each track about five times to allow error recovery.
  ./dtc  -fdirname/track -g0 -i0 -d0 -p -e76 -dd0

Zip up the output directory
  zip -rj filename.zip dirname/*

Process the files
  ./fluxtoimd -F ksf --intelm2fm filename.zip filename.imd -C "Description of disk"

Uncorrectable read errors will generate this message if all reads of sector
had data CRC error
*** BAD: track 21 sector 46

If the sector was not found or had header CRC error for all reads this error
will be generated.
*** BAD nodata: track 03 sector 26

Summary of errors are printed at the end of the conversion.

To extract the files with isisutils into a directory
  ./isis.py -x -d output_dir file.imd 

To extract into a zip file 
  ./isis.py -x -z output.zip file.imd 

To view directory
  ./isis.py -v file.imd 

For CP/M disks cpmtools can extract with this diskdef for double density
disks.
# Intel MDS/22 8" Double Density
diskdef mds-dd
  seclen 128
  tracks 77
  sectrk 52
  blocksize 2048
  maxdir 128
  skew 0
  boottrk 2
  os 2.2
end

Untested single density
# Intel MDS/22 8" Single Density
diskdef mds-sd
  seclen 128
  tracks 77
  sectrk 26
  blocksize 1024
  maxdir 64
  skew 0
  boottrk 2
  os 2.2
end

For cpmtools the .imd files need to be converted to raw .img file.
Libdsk can convert
  ./libdsk-1.5.12/tools/dskconv -otype raw filename.imd filename.img
And disk utilities
  ./Disk-Utilities/disk-analyse/disk-analyse filename.imd filename.img

For directory 
  ./cpmtools/cpmls -f mds-dd filename.img

To extract
  ./cpmcp -f mds-dd filename.img '0:*' output-directory

