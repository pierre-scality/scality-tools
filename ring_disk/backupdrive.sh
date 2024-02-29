#!/bin/bash

# VM is to enable testing on VM (replacing ssacli part)
VM=yes 
RING=DATA
STEP=yes
SCALDIR=/scality/
DUMPDISK=yes

if [ $# -ne 1 ]; then
echo "INFO : you need to specify the disk name (the path $SCALDIR will be used)"
exit
else
echo "INFO : disk chosen $1"
fi 


# simple dry run to escape long cmd for testing
RUN=
#RUN=echo


TARGET=$1
TARGETMP=/scality/$TARGET
LOG=/tmp/diskreplace.out
DUMPDIR=/var/tmp/dumpdisk/
FSTAB=$DUMPDIR/$TARGET.fstab
TIMER=3

function confirm () {
if [ ${STEP:=no} == 'yes' ]; then
  echo "INFO : $@ [any key to continue]"
read dummy
fi
}


if [ ! -d $DUMPDIR ] ; then 
  mkdir $DUMPDIR
fi

# get the ftab entry
grep -w /scality/$TARGET /etc/fstab > $FSTAB 
if [ $? -ne 0 ]; then
	echo "disk $TARGET not in fstab"
	exit
fi
# Getting disk mountpoint device and uuid
DEVICE=$(findmnt --target $TARGETMP -o SOURCE -n)
if [ $? != 0 ]; then
  echo "Error getting mountpoint $TARGETMP"
  exit
fi

UUID=$(lsblk $DEVICE -o UUID -n)
echo "INFO : Verifying fstab $UUID  $TARGET"
grep $UUID /etc/fstab | grep -w /scality/$TARGET
if [ $? -ne 0 ]; then
  echo "error verif fstab"
  exit
fi
if [ -f /scality/$TARGET/.$TARGET ] ; then
  echo "witness file /scality/$TARGET/.$TARGET found"
else
  echo "Need witness files /scality/$TARGET/.$TARGET"
  exit
fi

confirm "In test mode for $TARGET $DEVICE $UUID"

FLAG=$(bizioctl -N $TARGET -c  get_mflags bizobj://$RING:0)
if [ $? -ne 0 ]; then
  echo "error getting flag"
  exit
fi
if [ $FLAG == "0x0" ]; then
  echo "disk $TARGET has no flag"
else
  echo "disk $TARGET has flag $FLAG, aborting"
  exit
fi

bizioctl -N $TARGET -c set_mflags -a 0x1 bizobj://$RING:0
FLAG=$(bizioctl -N $TARGET -c  get_mflags bizobj://$RING:0)
if [ $FLAG == "0x1" ]; then
  echo "disk $TARGET has 0x1 flag"
else
  echo "disk $TARGET has not flag 0x1 \($FLAG\), aborting"
  exit
fi

echo "Stopping $TARGET iod"
scality-iod stop $TARGET
sleep $TIMER
scality-iod status $TARGET
if [ $? -eq  0 ]; then
  echo "scality-iod on $TARGET is running, aborting"
  exit
else
  echo "scality-iod stopped on $TARGET"
fi

t1=$(date '+%s')
cd /scality/$TARGET
confirm "Taring disk with tar cf $DUMPDIR/$TARGET.tar from $(pwd)"
if [ $(pwd) != /scality/$TARGET ]; then
  echo "error moving in /scality/$TARGET"
  exit
else
  tar cf $DUMPDIR/$TARGET.tar .
fi
t2=$(date '+%s')
if [ $? -ne 0 ] ; then
  echo "error taring tar cf $DUMPDIR/$TARGET.tar"
  exit
else
  echo tar completed in $(( $t2 - $t1 )) seconds
fi

cd
du -sh $DUMPDIR/$TARGET.tar

# rebuilding device
echo "Rebuilding device $DEVICE mounted on $TARGETMP disk $TARGET UUID $UUID"
umount $TARGETMP
findmnt $TARGETMP 
A=$? 
if [ $A -eq 0 ] ; then 
  echo "Error umounting $TARGETMP exiting $A"
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

if [ $STEP == 'yes' ]; then 
echo 'disk rebuild and mounted, do you want to continue to mount and enable service ? '
read dummy
fi
# sed old uuid to new uuid
systemctl daemon-reload
mount $TARGETMP
MOUNT_ON=$(findmnt $TARGETMP -o SOURCE -n)
#if [ $? -ne 0 ]; then
if [ $MOUNT_ON != $DEVICE ]; then
  echo "Error umounting $TARGETMP after replacement"
  exit
else
  echo "INFO : disk mounted on $MOUNT_ON"
fi

# Restore data
if [ ! -f $DUMPDIR/$TARGET.tar ] ; then
  echo "ERROR can't find back $DUMPDIR/$TARGET.tar"
  exit
else
  cd $TARGETMP
  if [ $(pwd) != $TARGETMP ] ; then
    echo "ERROR changing dir to $TARGETMP"
    exit
  fi
fi
confirm "restore tar from $(pwd)"
tar xf $DUMPDIR/$TARGET.tar
if [ ! -f .$TARGET ] ; then 
  echo "ERROR witness file missing. Check disk restore data"
  exit
fi

scality-iod start $TARGET
bizioctl -N $TARGET -c del_mflags -a 0x1  bizobj://$RING:0
FLAG=$(bizioctl -N $TARGET -c  get_mflags bizobj://$RING:0)
if [ $FLAG == "0x0" ]; then
  echo "disk $TARGET flag clear"
else
  echo "disk $TARGET has flag $FLAG error"
  exit
fi
echo "done : $(date '+%y%m%d-%H%M%S')" > /scality/$TARGET/.$TARGET
cat /scality/$TARGET/.$TARGET
cd
echo "you mut remove /var/tmp/dumpdisk/$TARGET.tar"
