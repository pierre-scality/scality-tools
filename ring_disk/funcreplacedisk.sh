#!/bin/bash

# VM is to enable testing on VM (replacing ssacli part)
P1=yes     # if set to yes it will assume the partition are created as p1 and not 1 (device /dev/nvme3n1 partition 1  /dev/nvme3n1p1)
RING=DATA
STEP=no  # It will pause and ask for confirmation to continue. Must be set to no to be skipped
REMOVEBACKUP=yes    # automatically remove tar file after disk is done
VERBOSE=no
INFO=yes
TARCPSIZE=50000 # checkpoint size for tar output
TODO=$1
shift

usage () {
cat << fin
$0 <operation> <target disk path> <disk name>
example : $0 backup scality g1disk01 
Args are : 
prepare   -> stop and get the disk ready to be replaced 
backup    -> backup the disk content to $DUMPDIR 
rebuild   -> Rebuild the disk 
restore   -> Restore disk content
all       -> run all the steps
fin
}

# simple dry run to escape long cmd for testing
RUN=
#RUN=echo


LOG=/tmp/diskreplace.out
DUMPDIR=/var/tmp/dumpdisk/
TIMER=3

# this function will just stop and wait for keyb input to go on if $STEP is not set to no
function confirm () {
if [ ${STEP:=no} == 'yes' ]; then
  echo "INFO : $@ [any key to continue]"
read dummy
fi
}

function info () {
if [ ${INFO:=no} == 'yes' ]; then
  echo "INFO : $@" 1>&2
fi
}

function error () {
echo "ERROR : $@"
exit
}


function prepare_system () { 
if [ ! -d $DUMPDIR ] ; then 
  mkdir $DUMPDIR
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
info "INFO : Verifying fstab $UUID  ${TARGET}"
info $(grep $UUID /etc/fstab | grep -w ${TARGET_MP})
if [ $? -ne 0 ]; then
  echo "error verif fstab"
  exit
fi
if [ ! -f ${TARGET_MP}/.${TARGET} ] ; then
  echo ${TARGET} >>  ${TARGET_MP}/.${TARGET}
fi

echo "start operation $(date '+%y%m%d-%H%M%S')" >> ${TARGET_MP}/.${TARGET}
echo $UUID
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
  echo "disk ${TARGET} has no flag"
else
  echo "disk ${TARGET} has flag $FLAG, aborting"
  exit
fi

bizioctl -N ${TARGET} -c set_mflags -a 0x1 bizobj://$RING:0
FLAG=$(bizioctl -N ${TARGET} -c  get_mflags bizobj://$RING:0)
if [ $FLAG == "0x1" ]; then
  echo "disk ${TARGET} has 0x1 flag"
else
  echo "disk ${TARGET} has not flag 0x1 \($FLAG\), aborting"
  exit
fi

echo "Stopping ${TARGET} iod"
scality-iod stop ${TARGET}
sleep $TIMER
scality-iod status ${TARGET}
if [ $? -eq  0 ]; then
  echo "scality-iod on ${TARGET} is running, aborting"
  exit
else
  echo "scality-iod stopped on ${TARGET}"
fi
}

function dump_disk_out () { 
if [ $# -ne 2 ] ; then echo "ERROR dump_disk_out args" ; exit ; fi
SCAL_MP=$1
TARGET=$2
TARGET_MP=/${SCAL_MP}/${TARGET}

t1=$(date '+%s')
cd $TARGET_MP
confirm "Taring disk with tar cf $DUMPDIR/${TARGET}.tar from $(pwd)"
if [ $(pwd) != ${TARGET_MP} ]; then
  echo "error moving in ${TARGET_MP}"
  exit
else
  tar cf $DUMPDIR/${TARGET}.tar --checkpoint=$TARCPSIZE --checkpoint-action=echo="%s %u" .
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

info "Rebuilding device $DEVICE mounted on ${TARGET_MP} disk ${TARGET} UUID $UUID"
umount ${TARGET_MP}
findmnt ${TARGET_MP} 
A=$? 
if [ $A -eq 0 ] ; then 
  echo "Error umounting ${TARGET_MP} exiting $A"
  exit
fi

confirm "disk umounted, do you want to continue to rebuild device $DEVICE"
# This is the critical part --> replace disk
if [ $P1 == "yes" ] ; then
    PARTID=p1
    ROOT_DEVICE=$(echo $DEVICE | sed "s/${PARTID}$//")
else
    PARTID=1
    ROOT_DEVICE=$(echo $DEVICE | sed "s/1$//")
fi
   
info "You need to rebuild the device manually"
info "For lab use : dd if=/dev/zero of=$ROOT_DEVICE bs=256k count=1"
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
# Destroying the partition table
NEW_DEVICE=${ROOT_DEVICE}${PARTID}

confirm "create part on $ROOT_DEVICE and format part  $NEW_DEVICE"

parted -s ${ROOT_DEVICE} mklabel gpt
parted -s ${ROOT_DEVICE} mkpart primary 1 100%
mkfs.ext4 -m 0 ${NEW_DEVICE}
tune2fs -c0 -C0 -m0 -i0 ${NEW_DEVICE}
NEWUUID=$(lsblk -n -o UUID $NEW_DEVICE)
DEVICE_CHECK=$(blkid -U $NEWUUID)

if [ ${NEWUUID:=empty} == empty ]; then echo "ERROR : no UUID found" ; exit ; fi
if [ ${NEW_DEVICE} != ${DEVICE_CHECK} ]; then
  echo "error matching device ${NEW_DEVICE} for UUID ${NEWUUID}"
  exit
else
  info "New device ${NEW_DEVICE} UUID ${NEWUUID}"
fi
echo "Changing fstab with ${UUID} to ${NEWUUID}"
sed -i "s/${UUID}/${NEWUUID}/" /etc/fstab
grep -s $NEWUUID /etc/fstab
if [ $? -ne 0 ]; then
  echo "ERROR entry not in fstab"
  exit
fi

systemctl daemon-reload
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
confirm "restore tar from $(pwd)"
tar xf $DUMPDIR/${TARGET}.tar --checkpoint=$TARCPSIZE --checkpoint-action=echo="%s %u"
if [ ! -f .${TARGET} ] ; then 
  echo "ERROR witness file missing. Check disk restore data"
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
if [ $REMOVEBACKUP == yes ]; then
confirm "Do you want to remove backup $DUMPDIR/${TARGET}.tar"
info "Removing $DUMPDIR/${TARGET}.tar"
rm $DUMPDIR/${TARGET}.tar
else 
echo "Manually remove backoup : $DUMPDIR/${TARGET}.tar"
fi
}

end_up () {
if [ -f /var/tmp/dumpdisk/${TARGET}.tar ] ; then
echo "you must remove /var/tmp/dumpdisk/${TARGET}.tar"
fi
}



if [ $# -ne 2 ] ; then usage ; error "need mount point and disk" ; exit; fi
D=$2
P=$1

case ${TODO:=null} in
  prepare) 
    prepare_system
    prepare_disk $1 $2
    stop_disk $1 $2
    ;; 
  backup)
    dump_disk_out $1 $2 ;; 
  rebuild)
    rebuild_device $1 $2;;
  restore) 
    start=$(date '+%s')
    restore_data $1 $2
    end=$(date '+%s')
    info "disk $2 done in $(( $end - $start)) second"
    start_disk $1 $2
    finish_task $D
    ;;
  all)
    prepare_system
    prepare_disk $1 $2
    stop_disk $1 $2
    dump_disk_out $1 $2 
    rebuild_device $1 $2
    start=$(date '+%s')
    restore_data $1 $2
    end=$(date '+%s')
    info "disk $2 done in $(( $end - $start)) second"
    start_disk $1 $2
    finish_task $D
    ;;
  *) 
    echo "unexpected input"
    usage
    exit
    ;;
esac
