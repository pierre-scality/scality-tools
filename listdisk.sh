#!/bin/bash
RING=$1

function listdisk () {
for line in $(grep nvp /etc/biziod/bizobj.$RING.disk*) ; do
disk=$(echo $line|cut -d ':' -f 1|awk -F '.' '{print $NF}'); nvp=$(echo $line|cut -d ':' -f 2|cut -d '/' -f 3);
disk=$( echo $disk | sort -n);
 echo $disk $nvp ;
done | awk '{d[$2]=d[$2] " " $1} END { for (i in d)  {printf "%s : %s\n",i,d[i]}}'
}

function listts () {
for line in $(grep ts /etc/biziod/bizobj.$RING.disk*) ; do
disk=$(echo $line|cut -d ':' -f 1|awk -F '.' '{print $NF}'); ts=$(echo $line|cut -d ':' -f 2|cut -d '=' -f 2);
disk=$( echo $disk | sort -n);
 echo $disk $ts ;
done | awk '{d[$2]=d[$2] " " $1} END { for (i in d)  {printf "%s : %s\n",i,d[i]}}'
}
 
listdisk
listts
