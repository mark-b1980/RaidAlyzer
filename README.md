# RaidAlyzer 

Simple GUI tool to analyze RAID image-files to help with RAID data recovery and reverse-engineering of a RAID array.

## Usage

 1. Click `Open disk images` and select the files to analyze (for now are only binary images supported)
 2. Click `Start analysis` - the results are updates periodically while the analysis is running
 3. Click `Stop analysis` to cancel the analysis before the process is complete

### Patterns and entropy in data

This function check if a sector is filled with `0x00` (Zero), a non-zero pattern (e.g. `0xAA` or `0xFF`) and if calculates the average entropy of all sectors. It checks furthermore of the bootsector signature `0x55AA` is found at the last 2 bytes of some sector and if the EFI partitiontable header `EFI PART` is found at the beginning of some sector.  

**Sample output:**

```
 #  FILE                   ZERO %  PATTERN %  ENTROPY
 0  01.img                 18.2 %     19.7 %      7.5
 1  02.img                 18.1 %     19.6 %      7.5
 2  03.img                 18.2 %     19.7 %      7.5
 3  04.img                100.0 %      0.0 %      0.0

---

Bootsector signature found in file: 01.img at sector 0
EFI PART header found in file:      01.img at sector 1
```

This samples shows that the image `04.img` is only filled with `0x00` bytes and thatfor this is likely a new drive or a drive that did not belong to the array. 

The files `01.img` - `03.img` having the same average entropy and they have a similiar pattern in the data (similiar values for zero- and pattern-filled sectors). This indicate that the drives `01.img`, `02.img` and `03.img` belong to the same array while `04.img` is very likely not part of the array.

The found bootsector-signature in sector `0` of the file `01.img` and the EFI partitiontable header in sector `1` of the same file are a strong indication that there is no offset in that RAID array and that `01.img` is the first disk in a right oriented array or the 2nd disk in a left-oriented array.

### Mirror analysis

The mirror analysis helps to identify identical copies of drives (mirrors) like in a RAID1 or RAID10.

**Sample output:**

```
                      01.img                02.img                03.img                04.img  
01.img                   ---                    0%                    0%                  100%  
02.img                    0%                   ---                  100%                    0%  
03.img                    0%                  100%                   ---                    0%  
04.img                  100%                    0%                    0%                   ---  
```

This samples shows that `01.img` and `04.img` are copies of each other and `02.img` and `03.img` are also copies of each other. This mean we have here most-likely a RAID10.

### Paraity analysis

The parity analysis does a XOR calculation over all drives and the same calculation for each constellation with one of the drives excluded. 

```
ALL FILES                       0%
WITHOUT 01.img                  1%
WITHOUT 02.img                  1%
WITHOUT 03.img                  0%
WITHOUT 04.img                100%
```

This show us without `04.img` we have a complete RAID5 with all drives. This is also the same sample as in [patterns and entropy in data](#patterns-and-entropy-in-data).

```
ALL FILES                     100%
WITHOUT 01.img                  0%
WITHOUT 02.img                  1%
WITHOUT 03.img                  1%
```

This show us we have here most-likely a RAID5 with all 3 drives present. (Same sample as above but without `04.img`)

```
ALL FILES                       1%
WITHOUT 02.img                  2%
WITHOUT 03.img                  1%
WITHOUT 04.img                  3%
```

This show us we have a RAID5 with at least one missing drive or maybe a RAID6 or RAID1, given there are no mirrors detected.

### Detection of partial complete arrays and cutting points

Occational clients do not know that a restore take time and I had cases where I need to stitch 2 drives together into a complete array as the data where partially complete with one of the drive to s certain point and partially complete with another drive to a certain point...

This would look in a ideal case like that:

```
ALL FILES                       0%
WITHOUT 02.img                  0%
WITHOUT 03.img                  0%
WITHOUT 04.img                 40%
WITHOUT 05.img                 60%
```

You can see that the the overall parity match is 0% (also close to 0% is fine) and 40% match without `04.img` and the other 60% match without `05.img`. That let us hope that by combining the 40% of `05.img` which seem to match with the 60% of `04.img` which seem to match will give us a complete array.

Thise becomes even more crear wehn looking at the `reaidalyzer_report_YYYYMMDD_hhmmss.txt` file created by the tool:

```
Parity Check Log:
---------------------
1 - 1354 : 02.img + 03.img + 04.img
1355 - 2245 : 02.img + 03.img + 05.img
```

We need to use for sector 1 - 1354 the date from `04.img` and fro sector 1355 - 2245 the data of `05.img`!
