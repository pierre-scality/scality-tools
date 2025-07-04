#!/bin/bash

VERBOSE=no
CONFIRM=yes

usage () { 
cat << fin
This script automate operations to move a PD passthrough to LD RAID0.
Operations must be run in order and 1 free pd must be available
search  <slot> <mountpoint full path> -> return PD detail for the mount point
build   <slot> <physical device id>   -> Create a raid0 on the device (fail if already mounted)
buildmp <slot> <mount point>   	      -> Create a raid0 from a mountpoint
prepare <slot> <mountpoint full path> -> Take a free device and format/mount it
dispose <slot> <device>               -> Destroy the RAID0 device from the logical volume
pd/ld   <slot> <mountpoint>	      -> utility to get pd or ld matching the disk parttern
status	<slot> done|notdone           -> if done will show ld on the slot otherwise pd (which means needs to be done)	
fin
}


if [ $# -eq 0 ] ; then
usage
exit
fi


if [ $# -ne 3 ]; then
usage
exit
else
echo "INFO : operation $1 slot $2 argument $3"
fi

TODO=$1
SLOT=$2
DISK=$3

case ${TODO:=null} in
  buildmp)
  #FORCE=forced
  MNTCOUNT=$(df | grep -w $DISK | wc -l)
  if [ ${MNTCOUNT:=0} -ne 1 ]; then echo "issue in $DISK mountpoint got $MNTCOUNT need exactly 1" ; fi 
  CUR=/dev/$(lsblk -no pkname $(findmnt --target $DISK -o SOURCE -n)) 
	SSACLI=$(ssacli ctrl slot=$SLOT pd all show detail | awk -v dev=$CUR '/physicaldrive/ { pd=$2 }  /Disk Name:/ {disk=$NF} /Mount Points:/ {if ( disk == dev) {print pd,disk,$NF}}')
  PD=$(echo $SSACLI | awk '{print $1}')
  SSADEV=$(echo $SSACLI | awk '{print $2}')
  if [ ${SSADEV:=NotFound} != ${CUR:=current} ] ; then  echo "Devices from ssacli $SSADEV doesn't match mount point $CUR" ; exit ; fi
  umount $DISK
  if [ $? -ne 0 ] ; then
    echo "error umounting $DISK" 
  else
    echo "$DISK umounted"
  fi
  echo "Creating ld on $PD for disk $DISK on dev $SSADEV"
  ssacli ctrl slot=$SLOT create type=ld drives=$PD  raid=0 $FORCE
  ;;
  search )
	partition=$(findmnt $DISK -t ext4 -o source -n)
	if [ $? -ne 0 ]; then
		echo "ERROR : $DISK not mounted as ext4"
		exit
	fi
	pdentry=$(ssacli ctrl slot=$SLOT pd all show detail | awk '/physicaldrive/ { pd=$2 } ;  /Mount Points:/ {print(pd,$NF)}'| grep -w $DISK)
	# output should be like 1I:1:52 /scality/disk2 -> 2 strings only. if multiple match or no match != 2
	if [ $( echo $pdentry | wc -w) -ne 2 ] ; then
		echo "ERROR : PD not found for $DISK"
		exit
	fi
	PD=$(echo $pdentry | awk '{print $1}')	
	if [ $VERBOSE == yes ] ; then ssacli ctrl slot=$SLOT pd $PD show ; fi
	echo $pdentry
	exit ;; 
  build )
	PD=$DISK
	mount=$(ssacli ctrl slot=$SLOT pd $PD show|grep 'Mount Points')
	if [ $? -ne 0 ] ; then 
		echo "ERROR in ssacli slot=$SLOT pd $PD"
		exit
	fi
	mount=$( echo $mount |awk  '{print $NF}' )
	if [ "$mount" != 'None' ]; then
		echo "ERROR : PD $PD mounted on $mount"
		exit	
	else
		echo "Mount point set to None: $mount"
		ssacli ctrl slot=$SLOT pd $PD show|grep -e 'Mount Points' -e 'physical' -e 'Disk Name' | sed -e 's/^\ *//g'
		cmd="ssacli ctrl slot=$SLOT create type=ld drives=$PD  raid=0" 
		read -p "Run : $cmd ?"
		$cmd
		
	fi
	;;
  prepare)
	DIR=$DISK 
	if [ ! -d $DIR ]; then echo "ERROR directory $DIR does not exists" ; exit ;  fi 
        partition=$(findmnt $DIR -o source -n)
        if [ $? -eq 0 ]; then
                echo "ERROR : $DIR is already mounted"
                exit
	else
		echo "device not mounted $DIR"
        fi
	freeld=$(ssacli ctrl slot=$SLOT ld all show detail | awk -F ':' '/Logical Drive:/ { ld=$2 } ;  /Disk Name:/ {dev=$2}; /Mount Points: None/ {print(ld,dev)}')
	if [ $( echo $freeld | wc -w ) != 2 ] ; then 
		echo "ERROR : Need strictly 1 id and 1 device. ld prepare error $freeld"
		exit	
	fi
	id=$(echo $freeld | awk '{print $1}')
	ROOT_DEVICE=$(echo $freeld | awk '{print $2}')
	NEW_DEVICE=${ROOT_DEVICE}1
	echo "selected device $ROOT_DEVICE (id = $id)"
	ssacli ctrl slot=$SLOT ld $id show detail
	read -p "Format and mount the device  ${ROOT_DEVICE} (part = ${NEW_DEVICE}) ?"
	parted -s ${ROOT_DEVICE} mklabel gpt
	parted -s ${ROOT_DEVICE} mkpart primary 1 100%
	mkfs.ext4 -m 0 ${NEW_DEVICE}
	tune2fs -c0 -C0 -m0 -i0 ${NEW_DEVICE}
	NEWUUID=$(lsblk -n -o UUID $NEW_DEVICE)
	DEVICE_CHECK=$(blkid -U $NEWUUID)	
	mount UUID=$NEWUUID $DIR
	echo -n "Mount : "
	findmnt -n $DIR
	;;	
  dispose) 
	DEVICE=$DISK
        PARTITION=${DEVICE}1
        dir=$(findmnt $PARTITION -o target -n)
        if [ $? -eq 0 ]; then
                echo "ERROR : $PARTITION is still mounted on $dir"
                exit
        fi
	targetvol=$(ssacli ctrl slot=$SLOT ld all show detail | awk -F ':' '/Logical Drive:/ { ld=$2 } ;  /Disk Name:/ {dev=$2}; /Mount Points:/ {print(ld,dev,$NF)}'|grep -w $DEVICE)
	if [ $( echo $targetvol | wc -w ) != 3 ] ; then
		echo "ERROR : Need strictly 1 id and 1 device. ld prepare error $targetvol"
		exit	
	fi
	ld=$(echo $targetvol|awk '{print $1}')
	dev=$(echo $targetvol|awk '{print $2}')
	mnt=$(echo $targetvol|awk '{print $3}')
	read -p  "removing volume $ld device $dev mounted on $mnt ?"
	ssacli ctrl slot=$SLOT ld $ld delete
	echo "Cheking free pd slot"
	free=$(ssacli ctrl slot=$SLOT pd all show detail | awk '/physicaldrive/ { pd=$2 } ; /Disk Name:/ { dn=$3 } ;  /Mount Points:/ {print(pd,dn,$NF)}'| grep None)
 	if [ $( echo $targetvol | wc -w ) != 3 ] ; then
                echo "ERROR : Need strictly 1 id, 1 devicei and mountpoint/None. Got $free"
                exit
        fi
	ROOT_DEVICE=$(echo $free | awk '{print $2}')
	NEW_DEVICE=${ROOT_DEVICE}1
	read -p "Format and mount the device  ${ROOT_DEVICE} (part = ${NEW_DEVICE}) ?"
	read "really ?"	
	parted -s ${ROOT_DEVICE} mklabel gpt
	parted -s ${ROOT_DEVICE} mkpart primary 1 100%
	mkfs.ext4 -m 0 ${NEW_DEVICE}
	tune2fs -c0 -C0 -m0 -i0 ${NEW_DEVICE}
	NEWUUID=$(lsblk -n -o UUID $NEW_DEVICE)
	DEVICE_CHECK=$(blkid -U $NEWUUID)	
	echo "You need to : mount UUID=$NEWUUID /your/dir "
	;;
  ld ) # quick search for test 
	ssacli ctrl slot=$SLOT ld all show detail | awk -F ':' '/Logical Drive:/ { ld=$2 } ;  /Disk Name:/ {dev=$2}; /Mount Points:/ {print(ld,dev,$NF)}' | grep -w $DISK ;;
  pd ) # quick search for test 
	ssacli ctrl slot=$SLOT pd all show detail | awk '/physicaldrive/ { pd=$2 } ;  /Mount Points:/ {print(pd,$NF)}'| grep -w $DISK ;;
  status ) 
       if [ ${DISK:=done} == "done" ] ; then 
          ssacli ctrl slot=$SLOT ld all show detail | awk -F ':' '/Logical Drive:/ { ld=$2 } ;  /Disk Name:/ {dev=$2}; /Mount Points:/ {split($NF,o," ") ; print(ld,dev,o[5])}'
       else
          ssacli ctrl slot=$SLOT pd all show detail | awk '/physicaldrive/ { pd=$2 } ;  /Mount Points:/ {print(pd,$NF)}'
       fi        

  ;;
  *) echo "ERROR unexpected input"
     usage
     exit ;;
esac
