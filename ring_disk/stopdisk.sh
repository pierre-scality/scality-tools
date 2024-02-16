RING=DATA
findmnt /scality/$1
bizioctl -N $1 -c set_mflags -a 0x1  bizobj://$RING:0
bizioctl -N $1 -c get_mflags bizobj://$RING:0
scality-iod stop $1
umount /scality/$1
ls /scality/$1
