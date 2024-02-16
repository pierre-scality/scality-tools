RING=DATA
mount /scality/$1
scality-iod start $1
bizioctl -N $1 -c del_mflags -a 0x1  bizobj://$RING:0
bizioctl -N $1 -c get_mflags bizobj://$RING:0
