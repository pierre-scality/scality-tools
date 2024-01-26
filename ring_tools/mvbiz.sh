#!/bin/bash

# Simple script to move bizob to SSD after initial install

SSD=6
DIR=/etc/biziod/
#DIR=/root/biziod/
RING=DATA_PRD
DRUN=0

service scality-node status > /dev/null 2>&1



if [ $? -eq 0 ] ; 
then
	echo "nodes are running, aborting"
	[[ DRUN -ne 1 ]] && exit
fi


if [ ! -f $DIR/biziod.tar ];
then
	tar czf biziod.tar.gz -C $DIR $(ls $DIR)
else	
	echo 'Backup file exist'
fi

COUNT=1
for d in $(ls $DIR/bizobj.$RING.disk*) ; 
do
echo $d
i=$(basename $d) 
DISK=$( echo $i | cut -d '.' -f 3); 
NB=$(echo $DISK | cut -c 5,6) 
NVP=/scality/ssd${COUNT}/bizobj-disk${NB}
echo $DISK $NVP
if [ $(grep nvp  $DIR/bizobj.$RING.$DISK) ] ; 
then 
	echo "NVP already set in $DIR/bizobj.$RING.$DISK, skipping"
else
	[[ $DRUN -ne 0 ]] && echo  "nvp=$NVP >> $DIR/bizobj.$RING.$DISK"
	[[ $DRUN -eq 0 ]] && echo  "nvp=$NVP" >> $DIR/bizobj.$RING.$DISK
	
	[[ $DRUN -ne 0 ]] && echo  "mv /scality/$DISK/$RING/0/bizobj.bin $NVP/$RING/0/"
	if [ $DRUN -eq 0 ]; then 
		if [ ! -d $NVP/$RING/0/ ]; then
			echo "mkdir $NVP/$RING/0/"
			mkdir -p $NVP/$RING/0/
		fi
		echo mv /scality/$DISK/$RING/0/bizobj.bin $NVP/$RING/0/
		mv /scality/$DISK/$RING/0/bizobj.bin $NVP/$RING/0/
		if [ $? -ne 0 ]; then
			echo "error moving /scality/$DISK/$RING/0/bizobj.bin" 
		fi
		if [ ! -f $NVP/$RING/0/bizobj.bin ] ; then 
			echo "ERROR : no $NVP/$RING/0/bizobj.bin" 
			exit 
		fi
		grep -q $NVP $d 
		if [ $? -ne 0 ]; then
			echo "ERROR : NVP missing in $d"
			exit
		fi
	fi
		
fi
if [ $COUNT -eq $SSD ] ; then
COUNT=1
else
COUNT=$((COUNT + 1))
fi
done
