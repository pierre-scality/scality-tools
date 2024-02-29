RING=DATA
D=$1
mount /scality/$D
scality-iod start $D
bizioctl -N $D -c del_mflags -a 0x1  bizobj://$RING:0
bizioctl -N $D -c get_mflags bizobj://$RING:0
