#!/bin/bash

# VM is to enable testing on VM (replacing ssacli part)
VM=yes 
RING=DATA


if [ $# -ne 1 ]; then
echo 'need disk'
exit
else
echo "disk chosen $1"
fi 

# simple dry run to escape long cmd for testing
RUN=
RUN=echo

TARGET=$1
TARGETMP=/scality/$TARGET
LOG=/tmp/diskreplace.out
DUMPDIR=/var/tmp/dumpdisk/
DATA=$DUMPDIR/$TARGET.fstab
TIMER=3

if [ ! -d $DUMPDIR ] ; then 
  mkdir $DUMPDIR
fi

# get the ftab entry
grep -w /scality/$TARGET /etc/fstab > $DATA 
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
echo "Verifying fstab"
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

FLAG=$(bizioctl -N $TARGET -c  get_mflags bizobj://$RING:0)
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

echo "backing up the disk $TARGET"
cd /scality/$TARGET
if [ $(pwd) != /scality/$TARGET ]; then
  echo "error moving in /scality/$TARGET"
  exit
fi


t1=$(date '+%s')
echo tar cf $DUMPDIR/$TARGET.tar .
t2=$(date '+%s')
if [ $? -ne 0 ] ; then
  echo "error taring tar cf $DUMPDIR/$TARGET.tar"
  exit
else
  $RUN tar completed in $(( $t2 - $t1 )) seconds
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

if [ $VM == "yes" ] ; then
    PARTID=p1
else
    PARTID=1
    echo "need to put cli"
fi 

NEW_DEVICE=$(echo $DEVICE | sed "s/${PARTID}$//")
$RUN parted -s ${NEW_DEVICE} mklabel gpt
$RUN parted -s ${NEW_DEVICE} mkpart primary 1 100%
$RUN mkfs.ext4 -m 0 ${NEW_DEVICE}
$RUN tune2fs -c0 -C0 -m0 -i0 ${NEW_DEVICE}

# sed old uuid to new uuid
systemctl daemon-reload
mount $TARGETMP
findmnt $TARGETMP 
if [ $? -ne 0 ]; then
  echo "Error umounting $TARGETMP after replacement"
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
echo "you mut remove /var/tmp/dumpdisk/$TARGET.tar"
