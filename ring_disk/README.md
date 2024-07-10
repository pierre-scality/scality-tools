# Introduction
This tool is to rebuild drives in PD mode to LD mode. 
It backup the drive using tar after stopping scality disk, rebuild the PD to LB and restore the tar.

For 2TB used data it takes around : 
- backup to nvme -> 2h each phase 
- backup to 7.2K rpm -> 4h each phase

''' The default backup place is the SSD based on slot number '''

# Support RAID card
HPE ssacli compatible cards.
Raid cards are defined by slots (ssacli ctrl all show)
Note that some servers have multiple cards hence the slot parameter in the script.

# Usage
```shell
./replacedisk.sh [ -d backupdir ]  <operation> <slot> <target disk path> <disk name1> <disk name2 ...>
example : ./replacedisk.sh backup 1 scality g1disk01 g2disk02
```

Args are : 
prepare   -> stop and get the disk ready to be replaced 
backup    -> backup the disk content to this directory. Default is ssd[slot number]
rebuild   -> Rebuild the disk 
restore   -> Restore disk content
all       -> run all the steps

The disk must be behind the slot of the controler, you can check with 
./replacedisk.sh pd <slot> <path> <disk>
The slot is only used for hpe servers. For lab it is ignored.

BACKUP DIR : default is slot number on ssd. slot=1 -> /scality/ssd01\
The backup directory can be set as argument with -b <directory>.\
To be specified before other args  :\
example : ./replacedisk.sh -d /backup/disk01 backup 1 scality disk01


# Error management 
There are several checks during the script and if any error is found the script will exit.
Typical error is being unable to umount the disk before rebuilding the device.
You can restart from this step using 'rebuild' (do not use multiple disk with individual steps) :
./replacedisk.sh rebuild 1 scality disk01 

# Tunable variables 
HW=hpe             # can be hpe or vm -> used to test on lab (may not work anymore ..)\
P1=no              # if set to yes it will assume the partition are created as p1 and not 1 (device /dev/nvme3n1 partition 1  /dev/nvme3n1p1)\
RING=DATA\
STEP=no            # It will pause and ask for confirmation to continue. Must be set to no to be skipped\
REMOVEBACKUP=yes   # automatically remove tar file after disk is done\
VERBOSE=no         # Add additionnal output\
INFO=yes           # If no there wont be almost any message\
WITNESSFILE        # Directory to store the witness files (see Concurrency)\


# Concurrency 
You can run multiple install. The security is based on the witness files stored in /var/tmp\
This files may be erased. Be careful when running multiple instance of the script.


