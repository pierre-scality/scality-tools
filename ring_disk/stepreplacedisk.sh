#!/bin/bash

# VM is to enable testing on VM (replacing ssacli part)
VM=yes   	# If it is a VM is will remove the partitionand recreate it assuming it is /dev/nvmX2n1p1 
RING=DATA	
STEP=yes	# It will pause and ask for confirmation to continue. Must be set to no to be skipped
SCAL_MP=/scality	# scality mount point
REMOVEBACKUP=no  	# automatically remove tar file after disk is done
# simple dry run to escape long cmd for testing
RUN=
#RUN=echo

usage () { 
if [ $# -ne 1 ]; then
echo "INFO : you need to specify the disk name (the path $SCAL_MP will be used)"
exit
else
echo "INFO : disk chosen $1"
fi 
}

if [ $1 == help ] ; then
usage
exit
fi


if [ $# -ne 1 ]; then
usage
exit
fi


TARGET=$1
TARGET_MP=${SCAL_MP}/${TARGET}
LOG=/tmp/diskreplace.out
DUMPDIR=/var/tmp/dumpdisk/
FSTAB=$DUMPDIR/${TARGET}.fstab
TIMER=3

# this function will just stop and wait for keyb input to go on if $STEP is not set to no
function confirm () {
if [ ${STEP:=no} == 'yes' ]; then
  echo "INFO : $@ [any key to continue]"
read dummy
fi
}

function prepare_system () { 
if [ ! -d $DUMPDIR ] ; then 
  mkdir $DUMPDIR
fi
# add df on target
}

function prepare_disk () {
# get the ftab entry
grep -w ${SCAL_MP}/${TARGET} /etc/fstab > $FSTAB 
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
echo "INFO : Verifying fstab $UUID  ${TARGET}"
grep $UUID /etc/fstab | grep -w ${SCAL_MP}/${TARGET}
if [ $? -ne 0 ]; then
  echo "error verif fstab"
  exit
fi
if [ -f ${SCAL_MP}/${TARGET}/.${TARGET} ] ; then
  echo "witness file ${SCAL_MP}/${TARGET}/.${TARGET} found"
  echo "start operation $(date '+%y%m%d-%H%M%S')" >> ${SCAL_MP}/${TARGET}/.${TARGET}
else
  echo "Need witness files ${SCAL_MP}/${TARGET}/.${TARGET}"
  echo 'for i in $(ls -d /${SCAL_MP}/*disk* ) ; do touch $i/.$(basename $i) ; done'
  echo "where SCAL_MP=${SCAL_MP}"
  exit
fi
}

function iod_stop_disk () { 
confirm "In test mode for ${TARGET} $DEVICE $UUID"

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
t1=$(date '+%s')
cd ${SCAL_MP}/${TARGET}
confirm "Taring disk with tar cf $DUMPDIR/${TARGET}.tar from $(pwd)"
if [ $(pwd) != ${SCAL_MP}/${TARGET} ]; then
  echo "error moving in ${SCAL_MP}/${TARGET}"
  exit
else
  tar cf $DUMPDIR/${TARGET}.tar .
fi
t2=$(date '+%s')
if [ $? -ne 0 ] ; then
  echo "error taring tar cf $DUMPDIR/${TARGET}.tar"
  exit
else
  echo INFO tar completed in $(( $t2 - $t1 )) seconds
fi

cd
du -sh $DUMPDIR/${TARGET}.tar
}

function rebuild_device () {
# rebuilding device
fuser ${SCAL_MP}/${TARGET}
if [ $? == 0 ]; then
  echo "ERROR device ${SCAL_MP}/${TARGET} is busy"
  exit
fi
echo "INFO Rebuilding device $DEVICE mounted on ${TARGET_MP} disk ${TARGET} UUID $UUID"
umount ${TARGET_MP}
findmnt ${TARGET_MP} 
A=$? 
if [ $A -eq 0 ] ; then 
  echo "Error umounting ${TARGET_MP} exiting $A"
  exit
fi

confirm "disk umounted, do you want to continue to rebuild device $DEVICE"
# This is the critical part --> replace disk
if [ $VM == "yes" ] ; then
    PARTID=p1
    # Device does not change
    ROOT_DEVICE=$(echo $DEVICE | sed "s/${PARTID}$//")
    # Destroying the partition table
    $RUN dd if=/dev/zero of=ROOT_DEVICE bs=256k count=1
    NEW_DEVICE=$DEVICE
else
    PARTID=1
    echo "need to put cli"
fi 

$RUN parted -s ${ROOT_DEVICE} mklabel gpt
$RUN parted -s ${ROOT_DEVICE} mkpart primary 1 100%
$RUN mkfs.ext4 -m 0 ${NEW_DEVICE}
$RUN tune2fs -c0 -C0 -m0 -i0 ${NEW_DEVICE}
NEWUUID=$(lsblk -n -o UUID $NEW_DEVICE)
DEVICE_CHECK=$(blkid -U $NEWUUID)

if [ ${DEVICE} != ${DEVICE_CHECK} ]; then
  echo "error matching device ${ROOT_DEVICE} for UUID ${NEWUUID} from ${UUID}"
else
  echo "New device ${ROOT_DEVICE} UUID ${NEWUUID}"
fi
echo "Changing fstab with ${UUID} to ${NEWUUID}"
sed -i "s/${UUID}/${NEWUUID}/" /etc/fstab
grep -s $NEWUUID /etc/fstab
if [ $? -ne 0 ]; then
  echo "ERROR entry not in fstab"
  exit
fi
}

function restore_data () {
if [ $STEP == 'yes' ]; then 
echo 'disk rebuild and mounted, do you want to continue to mount and enable service ? '
read dummy
fi
# sed old uuid to new uuid
systemctl daemon-reload
mount ${TARGET_MP}
MOUNT_ON=$(findmnt ${TARGET_MP} -o SOURCE -n)
#if [ $? -ne 0 ]; then
if [ $MOUNT_ON != $DEVICE ]; then
  echo "Error umounting ${TARGET_MP} after replacement"
  exit
else
  echo "INFO : disk mounted on $MOUNT_ON"
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
confirm "restore tar from $(pwd)"
tar xf $DUMPDIR/${TARGET}.tar
if [ ! -f .${TARGET} ] ; then 
  echo "ERROR witness file missing. Check disk restore data"
  exit
fi
}

function start_disk () {
scality-iod start ${TARGET}
bizioctl -N ${TARGET} -c del_mflags -a 0x1  bizobj://$RING:0
FLAG=$(bizioctl -N ${TARGET} -c  get_mflags bizobj://$RING:0)
if [ $FLAG == "0x0" ]; then
  echo "disk ${TARGET} flag clear"
else
  echo "disk ${TARGET} has flag $FLAG error"
  exit
fi
echo "done $(date '+%y%m%d-%H%M%S')" >> ${SCAL_MP}/${TARGET}/.${TARGET}
}

function finish_task () {
#cat ${SCAL_MP}/${TARGET}/.${TARGET}
cd
if [ $REMOVEBACKUP == yes ]; then
confirm "Do you want to remove backup $DUMPDIR/${TARGET}.tar"
rm $DUMPDIR/${TARGET}.tar
fi
}

end_up () {
if [ -f /var/tmp/dumpdisk/${TARGET}.tar ] ; then
echo "you must remove /var/tmp/dumpdisk/${TARGET}.tar"
fi
}

# Main 
## do 1 time 
prepare_system

## start loop
start=$(date '+%s')
prepare_disk
iod_stop_disk
dump_disk_out
rebuild_device
restore_data
start_disk
end=$(date '+%s')
echo "disk $TARGET done in $(( $end - $start)) second"
finish_task

## close everything
end_up
