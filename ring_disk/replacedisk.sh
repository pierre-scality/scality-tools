#!/bin/bash

function usage () {
cat << fin
$0 [ -d backupdir ]  <operation> <slot> <target disk path> <disk name1> <disk name2 ...>
example : $0 backup 1 scality g1disk01 
Args are : 
prepare   -> stop and get the disk ready to be replaced 
backup    -> backup the disk content to this directory. Default is ssd[slot number]
rebuild   -> Rebuild the disk 
restore   -> Restore disk content
all       -> run all the steps
The disk must be behind the slot of the controler, you can check with 
$0 pd <slot> <path> <disk>
The slot is only used for hpe servers. For lab it is ignored.

BACKUP DIR : default is slot number on ssd. slot=1 -> /scality/ssd01
The backup directory can be set as argument with -b <directory>.
To be specified before other args  :
example : $0 -d /scality/disk02 backup 1 scality disk01

fin
}

while getopts b:hs sarg
do
case $sarg in
  b)  DUMPDIR=$OPTARG ;;
  h)  usage
    exit 0 ;;
  s)  PRG=$(basename $0)
      ps -edf | grep $PRG | grep -v grep
      exit 0 ;;
  *)  echo "Arg error"
    usage
    exit 9
    ;;
esac
done
shift $(($OPTIND - 1))

# VM is to enable testing on VM (replacing ssacli part)
HW=hpe             # can be hpe or vm
P1=no              # if set to yes it will assume the partition are created as p1 and not 1 (device /dev/nvme3n1 partition 1  /dev/nvme3n1p1)
RING=DATA
STEP=no           # It will pause and ask for confirmation to continue. Must be set to no to be skipped
REMOVEBACKUP=yes    # automatically remove tar file after disk is done
VERBOSE=no
INFO=yes
TARCPSIZE=50000    # obsolete # checkpoint size for tar output (if pv not used)
PVINT=1            # pv display interval for tar task monitoring 
TIMER=5            # sleep time between biziod ops
PD=none     # this is in insternal variable do not modify 
WITNESSFILE=/var/tmp/witness
TODO=$1
shift
# This variable will manage ssacli command AND dumpdir which will be /scality/ssd${SLOT}
SLOT=$1
shift

if [ ${DUMPDIR:=none} == "none" ]; then
  DUMPDIR=/scality/ssd0${SLOT}/dumpdisk/
fi

# this function will just stop and wait for keyb input to go on if $STEP is not set to no
function confirm () {
DD=$(date '+%y%m%d:%H%M%S')
if [ ${STEP:=no} == 'yes' ]; then
  echo "$DD : INFO : $@ [any key to continue]"
read dummy
fi
}

function info () {
DD=$(date '+%y%m%d:%H%M%S')
if [ ${INFO:=no} == 'yes' ]; then
  echo "$DD : INFO : $@" 1>&2
fi
}

function error () {
echo "ERROR : $@"
exit
}


function prepare_system () {
if [ -f /etc/sysconfig/scality-node ] ; then 
  retention=$(grep BACKUP_RETENTION_DAYS /etc/sysconfig/scality-node| cut -d = -f 2)
else
  echo "WARNING file /etc/sysconfig/scality-node not found" 
fi
echo ${HW:=null} | grep -wq -e hpe -e vm
if [ $? -ne 0 ]; then 
  error "HW $HW not supported"
fi 
info "Preparing system, slot $SLOT will be used, backup dir $DUMPDIR. Bizobj retention set to $retention"
if [ ! -d $DUMPDIR ] ; then 
  mkdir $DUMPDIR
  if [ $? -ne 0 ] ; then 
    error "Cant  create backup dir $DUMPDIR" 
  fi
fi
ls $DUMPDIR/*.tar > /dev/null 2>&1 
if [ $? -eq 0 ]; then 
info "There are backup files in  $DUMPDIR/"
fi
}



function prepare_disk () {
if [ $# -ne 2 ] ; then error "ERROR prepare_disk args" ; fi
SCAL_MP=$1
TARGET=$2

TARGET_MP=/${SCAL_MP}/${TARGET}
if [ ! -d ${TARGET_MP:=nothing} ]; then echo "ERROR $TARGET_MP does not exist" ; exit ; fi 
FSTAB=$DUMPDIR/${TARGET}.fstab
SRC=$(df -k ${TARGET_MP}| grep -v Filesystem |  awk '{print $3}') 
DST=$(df -k $DUMPDIR| grep -v Filesystem |  awk '{print $4}')
DSTLIMIT=$(echo "${DST:=0} / 10 * 8"|bc) # limit is 80% of target
if [ ${SRC:=10^100} -gt $DSTLIMIT ] ; then 
  error "Not enough space to backup. Source disk ${SRC:=10^20} target disk $DST limit $DSTLIMIT result $(( $DSTLIMIT - $SRC ))"
else
  if  [[ $VERBOSE == yes ]]; then info "Backup space check ${SRC:=10^20} target disk $DST limit $DSTLIMIT result $(( $DSTLIMIT - $SRC ))" ; fi
fi
if [ -f $WITNESSFILE.$TARGET ] ; then
  error "WARNING : witness file already exists  $WITNESSFILE.$TARGET. Make sure this is not an error and remove the file to restart"
  read -p  "WARNING : witness file already exists  $WITNESSFILE.$TARGET. Press enter to continue"
else
  echo "START : $(date '+%Y%m%d-%H%M%S')" > $WITNESSFILE.$TARGET
fi

# get the ftab entry
grep -w ${TARGET_MP} /etc/fstab > $FSTAB 
if [ $? -ne 0 ]; then
  echo "disk ${TARGET} not in fstab"
  exit
fi

# Getting disk mountpoint device and uuid
DEVICE=$(findmnt --target ${TARGET_MP} -o SOURCE -n)
if [ $? != 0 ]; then
  echo "Error getting mountpoint ${TARGET_MP}"
  exit
fi

UUID=$(lsblk $DEVICE -o UUID -n)
info "Verifying fstab $UUID  ${TARGET}"
if [ $? -ne 0 ]; then
  error "error verif fstab"
fi
if [ ! -f ${TARGET_MP}/.${TARGET} ] ; then
  echo ${TARGET} >>  ${TARGET_MP}/.${TARGET}
  grep $UUID /etc/fstab | grep -w ${TARGET_MP} >> ${TARGET_MP}/.${TARGET}
fi

echo "Start operation $(date '+%y%m%d-%H%M%S')" >> ${TARGET_MP}/.${TARGET}
if [ ${HW:=None} == "hpe" ] ; then 
  getpd=$(ssacli ctrl slot=$SLOT pd all show detail | awk '/physicaldrive/ { pd=$2 } ;  /Mount Points:/ {print(pd,$NF)}' | grep $TARGET)
  if [ "${getpd:=empty}" == empty ] ;  then
    error "Cant get PD for  ${TARGET_MP} on slot $SLOT"
  fi
  info "Writing PD name $getpd into ${TARGET_MP}/.${TARGET}"
  echo "Dev $DEVICE PD : $getpd" >>  ${TARGET_MP}/.${TARGET} 
  unset getpd
fi
}

function hpe_get_pd () {
if [ ${HW:=none} != 'hpe' ] ; then
  return
fi 
if [ $# -ne 2 ] ; then error "ERROR prepare_disk args" ; fi
SCAL_MP=$1
TARGET=$2
TARGET_MP=/${SCAL_MP}/${TARGET}
partition=$(findmnt $TARGET_MP -t ext4 -o source -n)
if [ $? -ne 0 ]; then
  error "$TARGET_MP not mounted as ext4"
fi
pdentry=$(ssacli ctrl slot=$SLOT pd all show detail | awk '/physicaldrive/ { pd=$2 } ;  /Mount Points:/ {print(pd,$NF)}'| grep -w $TARGET_MP)
if [ $( echo $pdentry | wc -w) -ne 2 ] ; then
  error "ERROR : PD not found for $DISK exiting"
fi
PD=$(echo $pdentry | awk '{print $1}')
if [ $VERBOSE == yes ] ; then ssacli ctrl slot=$SLOT pd $PD show ; fi
}

function hpe_build_ld () { 
if [ ${HW:=none} != 'hpe' ] ; then
  return
fi 
if [ $# -ne 1 ] ; then error "Need physical id" ; fi
PHYSID=$1
echo "Rebuild device with : ssacli ctrl slot=$SLOT create type=ld drives=$PHYSID  raid=0 forced"
}

function stop_disk () { 
if [ $# -ne 2 ] ; then echo "ERROR stop_disk args" ; exit ; fi
SCAL_MP=$1
TARGET=$2
#TARGET_MP=/${SCAL_MP}/${TARGET}

confirm "Stopping ${TARGET}"

FLAG=$(bizioctl -N ${TARGET} -c  get_mflags bizobj://$RING:0)
if [ $? -ne 0 ]; then
  echo "error getting flag ${TARGET}"
  exit
fi
if [ $FLAG == "0x0" ]; then
  info "disk ${TARGET} has no flag"
else
  error "disk ${TARGET} has flag $FLAG, aborting"
  exit
fi
scaldisk iods set ${TARGET} OOS_TEMP
#bizioctl -N ${TARGET} -c set_mflags -a 0x1 bizobj://$RING:0
FLAG=$(bizioctl -N ${TARGET} -c  get_mflags bizobj://$RING:0)
if [ $FLAG == "0x1" ]; then
  info "disk ${TARGET} has 0x1 flag"
else
  error "disk ${TARGET} has not flag 0x1 \($FLAG\), aborting"
  exit
fi
sleep $TIMER
echo "Stopping ${TARGET} iod"
scality-iod stop ${TARGET}
sleep $TIMER
scality-iod status ${TARGET}
if [ $? -eq  0 ]; then
  error "scality-iod on ${TARGET} is running, aborting"
  exit
else
  info "scality-iod stopped on ${TARGET}"
fi
}

function dump_disk_out () { 
if [ $# -ne 2 ] ; then echo "ERROR dump_disk_out args" ; exit ; fi
SCAL_MP=$1
TARGET=$2
TARGET_MP=/${SCAL_MP}/${TARGET}

info "backing up $TARGET to $DUMPDIR"

t1=$(date '+%s')
cd $TARGET_MP
confirm "Taring disk with tar cf $DUMPDIR/${TARGET}.tar from $(pwd)"
if [ $(pwd) != ${TARGET_MP} ]; then
  echo "error moving in ${TARGET_MP}"
  exit
else
  tar cf - . | pv -i $PVINT -barte -s $(df . | awk 'END {print $3*1024}') > $DUMPDIR/${TARGET}.tar
  #tar cf $DUMPDIR/${TARGET}.tar --checkpoint=$TARCPSIZE --checkpoint-action=echo="%s %u" .
fi
if [ $? -ne 0 ] ; then
  echo "error taring tar cf $DUMPDIR/${TARGET}.tar"
  exit
else
  t2=$(date '+%s')
  echo tar completed in $(( $t2 - $t1 )) seconds
fi

cd
du -sh $DUMPDIR/${TARGET}.tar
}

function rebuild_device () {
if [ $# -ne 2 ] ; then echo "ERROR rebuild_device args" ; exit ; fi
SCAL_MP=$1
TARGET=$2
TARGET_MP=/${SCAL_MP}/${TARGET}
# test
hpe_get_pd $SCAL_MP $TARGET
# rebuilding device
fuser ${TARGET_MP}
if [ $? == 0 ]; then
  echo "device ${TARGET_MP} is busy"
  exit
fi
DEVICE=$(findmnt --target ${TARGET_MP} -o SOURCE -n)
ROOT=$(findmnt --target / -o SOURCE -n)
if [ ${DEVICE} == ${ROOT} ]; then
  echo "Device ${DEVICE} is same than root device ${ROOT}"
  echo "If the disk is umounted remount : mount ${TARGET_MP}"
  echo "then run command again"
  exit
fi
UUID=$(lsblk $DEVICE -o UUID -n)
# manage rebuild steps
info "Umounting device $DEVICE mounted on ${TARGET_MP} disk ${TARGET} UUID $UUID"
umount ${TARGET_MP}
info "Umount done for ${TARGET_MP}"
findmnt ${TARGET_MP} 
A=$? 
if [ $A -eq 0 ] ; then 
  echo "Error umounting ${TARGET_MP} exiting $A"
  exit
fi

info "Current device $DEVICE mounted on ${TARGET_MP} disk ${TARGET} UUID $UUID"
if [ ${HW:=none} == 'hpe' ] ; then
  if [ ${PD} == "none" ] ; then 
    echo "Physical ID seems bad, build the device manually" 
    read -p "press enter when done or ctrl C to abort"
  else
    PHYSID=$PD
    echo "Rebuild device with : ssacli ctrl slot=$SLOT create type=ld drives=$PHYSID  raid=0 forced"
  fi
else 
  info "Unknow HW, You need to rebuild the device manually"
  read -p "For lab use : dd if=/dev/zero of=$ROOT_DEVICE bs=256k count=1" dummy

fi


confirm "disk umounted, Rebuild the device and press enter"
# This is the critical part --> replace disk
if [ $P1 == "yes" ] ; then
    PARTID=p1
    ROOT_DEVICE=$(echo $DEVICE | sed "s/${PARTID}$//")
else
    PARTID=1
    ROOT_DEVICE=$(echo $DEVICE | sed "s/1$//")
fi


# new code auto if issue go to manul
# expect same device
VERIF=$(ssacli ctrl slot=$SLOT pd $PHYSID show| awk -F ':' '/  Size:/ {s=$2} ; /Mount Points:/ {mp=$2} ; /Disk Name:/ {d=$2} ; END {printf "%s:%s:%s",d,mp,s}'| sed 's/\ *//g')
info "Device to build from $VERIF"
VERIF_MP=$(echo $VERIF | awk -F ':' '{print $2}')
if [ ${VERIF_MP:=NotFound} != None ] ; then
  info "ERROR cant verify PD :  $VERIF_MP" ; 
  read -p  "Please check out the  PD $PHYSID and hit enter when ready" DUMMY
else 
  info "PD $PHYSID has mount status $VERIF_MP ($VERIF)"
  # paranoid mode to remove
  #read -p "TESTING ready to run ssacli ctrl slot=$SLOT create type=ld drives=$PHYSID  raid=0 forced ?" 
  ssacli ctrl slot=$SLOT create type=ld drives=$PHYSID  raid=0 forced 
  if [ $? -ne 0 ] ; then 
    error "ssacli create ld ends with non 0 status"
  fi
fi

MANUAL=no
# verif device and then make fs
# we assume device name doesn't change
# DEVICE is the device used for the fs /dev/sda1
# ROOT_DEVICE = root device of the used part /dev/sda for /dev/sda1
# NEWDEV is the dev to be used to rebuild the par and will be assigned to ROOT_DEVICE
# NEW_DEVICE will be the partition to be used to creaate the FS
if [ -b ${DEVICE:=dummy} ] ; then
  echo "WARNING device $DEVICE still exists. Going manual"
  MANUAL=yes
else
  lsblk $ROOT_DEVICE  -n 
  if [ $(lsblk $ROOT_DEVICE  -n | wc -l) -ne 1 ] ; then i
    echo "WARNING lsblk on $ROOT_DEVICE did not return expected value. Going manual"
    MANUAL=yes
  fi
fi


if [ $MANUAL == "yes" ] ; then  
info "please input your new device when done"
while [ ${A:=n} != y ] ; do 
  read -p "QUERY : input your device : (old device $ROOT_DEVICE, enter to keep) " NEWDEV
  if [ -b ${NEWDEV:=$ROOT_DEVICE} ]; then
    info "device ${NEWDEV} found"
  else
    info "device ${NEWDEV} not found or not block device"
    continue
  fi
  read -p "Are you ok with device ${NEWDEV} (enter y or it will ask again) ? " A
done
ROOT_DEVICE=$NEWDEV
fi 

# Destroying the partition table
NEW_DEVICE=${ROOT_DEVICE}${PARTID}
#read -p  "TESTING create part on $ROOT_DEVICE and format part  $NEW_DEVICE" dummy
confirm "create part on $ROOT_DEVICE and format part  $NEW_DEVICE ?"
info "Creating partition on  ${ROOT_DEVICE} and filsystem on  ${NEW_DEVICE}"
parted -s ${ROOT_DEVICE} mklabel gpt
parted -s ${ROOT_DEVICE} mkpart primary 1 100%
echo y | mkfs.ext4 -qm 0 ${NEW_DEVICE}
if [ $? -ne 0 ]; then
  error "Creation error on ${NEW_DEVICE}"
  exit
fi
tune2fs -c0 -C0 -m0 -i0 ${NEW_DEVICE}

info "Build done reloading systemd"
systemctl daemon-reload
sleep 2
NEWUUID=$(lsblk -n -o UUID $NEW_DEVICE)
DEVICE_CHECK=$(blkid -U $NEWUUID)

if [ ${NEWUUID:=empty} == empty ]; then echo "ERROR : no UUID found" ; exit ; fi

if [ ${NEWUUID:=empty} == ${UUID} ]; then 
  echo "old $UUID and new ${NEWUUID} are identical"
  echo "fix the issue, change fstab with proper uuid and run mount ${TARGET_MP}"
  echo "Restart the script at the rebuild state then restore manually to restart operation"
  error "Identical UUID" 
fi

if [ ${NEW_DEVICE} != ${DEVICE_CHECK} ]; then
  echo "error matching device ${NEW_DEVICE} for UUID ${NEWUUID}"
  exit
else
  info "New device ${NEW_DEVICE} UUID ${NEWUUID}"
fi
info "Changing fstab with ${UUID} to ${NEWUUID}"
sed -i "s/${UUID}/${NEWUUID}/" /etc/fstab
grep -s $NEWUUID /etc/fstab
if [ $? -ne 0 ]; then
  error "Entry not in fstab"
  exit
fi

info "fstab modified reloading systemd"
systemctl daemon-reload
sleep 2

# systemd will probably load the FS but in case 
mount ${TARGET_MP}
MOUNT_ON=$(findmnt ${TARGET_MP} -o SOURCE -n)
if [ $? -ne 0 ]; then
  echo "Error mounting ${TARGET_MP} after replacement."
  exit
else
  info "Disk $TARGET mounted on $MOUNT_ON"
fi

}

fail_root_dev () { 
ROOTDEV=$(findmnt / -o SOURCE -n)
MOUNT_ON=$(findmnt --target ${TARGET_MP} -o SOURCE -n)
if [ ${ROOTDEV} == ${MOUNT_ON} ] ; then echo "ERROR : ${TARGET_MP} is on root dir" ; exit ; fi
info "new dev ${MOUNT_ON} (root dev ${ROOTDEV})"
}

function restore_data () {
if [ $# -ne 2 ] ; then echo "ERROR restore_data args" ; exit ; fi
SCAL_MP=$1
TARGET=$2
TARGET_MP=/${SCAL_MP}/${TARGET}

fail_root_dev ${TARGET_MP}
scality-iod status $TARGET 
if [ $? -eq 0 ]; then 
  error "Disk $TARGET is running when we want to restore"
fi

# Restore data
if [ ! -f $DUMPDIR/${TARGET}.tar ] ; then
  echo "ERROR can't find back $DUMPDIR/${TARGET}.tar"
  exit
else
  cd ${TARGET_MP}
  if [ $(pwd) != ${TARGET_MP} ] ; then
    echo "ERROR changing dir to ${TARGET_MP}"
    exit
  fi
fi
confirm "restore tar to $(pwd) from  $DUMPDIR/${TARGET}.tar"
pv -i $PVINT -barte $DUMPDIR/${TARGET}.tar | tar xf -
#tar xf $DUMPDIR/${TARGET}.tar --checkpoint=$TARCPSIZE --checkpoint-action=echo="%s %u"
if [ ! -f .${TARGET} ] ; then 
  echo "ERROR witness file missing. Check disk restore data"
  exit
fi
U=$(stat -c '%U'  ${TARGET_MP}/DATA/)
if [ ${U:=empty} != 'scality' ] ; then 
  echo "ERROR ${TARGET_MP} doesnt not belong to scality (show $U). Check disk restore data"
  exit
fi
}

function start_disk () {
if [ $# -ne 2 ] ; then echo "ERROR start disk args" ; exit ; fi
SCAL_MP=$1
TARGET=$2
TARGET_MP=/${SCAL_MP}/${TARGET}

scality-iod start ${TARGET}
bizioctl -N ${TARGET} -c del_mflags -a 0x1  bizobj://$RING:0
if [ $? -ne 0 ]; then error "Cannot get flag on biziod. isbiziod running ?" ; exit ; fi 
FLAG=$(bizioctl -N ${TARGET} -c  get_mflags bizobj://$RING:0)
if [ $FLAG == "0x0" ]; then
  echo "disk ${TARGET} flag clear"
else
  echo "disk ${TARGET} has flag $FLAG error"
  exit
fi
echo "done $(date '+%y%m%d-%H%M%S')" >> ${TARGET_MP}/.${TARGET}
}

function finish_task () {
cd
TARGET=$1
FLAG=$(bizioctl -N $TARGET -c get_mflags bizobj://DATA:0)
if [ ${FLAG:=none} != "0x0" ] ; then
  info "Warning : Disk $TARGET has not flag $FLAG. Not removing backup"
  REMOVEBACKUP=no
else
  info "Disk $TARGET has flag $FLAG"
fi
if [ $REMOVEBACKUP == yes ]; then
confirm "Do you want to remove backup $DUMPDIR/${TARGET}.tar"
info "Removing $DUMPDIR/${TARGET}.tar"
rm $DUMPDIR/${TARGET}.tar
else 
echo "Manually remove backup : $DUMPDIR/${TARGET}.tar"
fi
if [ ! -f $WITNESSFILE.$TARGET ] ; then 
  info "Witness file $WITNESSFILE.$TARGET not found"
else
  info "updating witness file $WITNESSFILE.$TARGET"
  echo "END : $(date '+%Y%m%d-%H%M%S')" >> $WITNESSFILE.$TARGET
fi               
}

end_up () {
if [ -f /var/tmp/dumpdisk/${TARGET}.tar ] ; then
echo "you must remove /var/tmp/dumpdisk/${TARGET}.tar"
fi
}


P=$1
shift

if [ $# -lt 1 ] ; then usage ; error "No disk spectified" ; exit; fi
if [ ${TODO:=null} != 'all' ] ;then 
  if [ $# -ne 1 ] ; then 
    error "multidisk available only for : all operation"
  fi
fi 

DISKLIST=$*
if [ $(echo $DISKLIST | wc -w) > 1 ] ; then
info "Starting with disk list $*"
fi 

for D in ${DISKLIST} ; do 
#D=$2
info "Starting with disk : $D"

case ${TODO:=null} in
  prepare) 
    prepare_system
    prepare_disk $P $D
    stop_disk $P $D
    ;; 
  backup)
    dump_disk_out $P $D ;; 
  rebuild)
    rebuild_device $P $D;;
  restore) 
    start=$(date '+%s')
    restore_data $P $D
    end=$(date '+%s')
    info "disk $2 done in $(( $end - $start)) second"
    start_disk $P $D
    finish_task $D
    ;;
  all)
    prepare_system
    prepare_disk $P $D
    stop_disk $P $D
    dump_disk_out $P $D 
    # comment below line if non hpe
    # moved to rebuidld_device directly # hpe_get_pd $P $D
    #hpe_build_ld $PD
    rebuild_device $P $D
    start=$(date '+%s')
    restore_data $P $D
    end=$(date '+%s')
    info "disk $2 done in $(( $end - $start)) second"
    start_disk $P $D
    finish_task $D
    ;;
  pd) 
    info "Verifying PD for $P/$D on slot $SLOT"
    hpe_get_pd $P $D
    echo "PD for $P/$D is $PD"
    ;;
  *) 
    echo "unexpected input"
    usage
    exit
    ;;
esac

done
