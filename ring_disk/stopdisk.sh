RING=DATA
D=1
findmnt -n /scality/$D
bizioctl -N $D -c set_mflags -a 0x1  bizobj://$RING:0
bizioctl -N $D -c get_mflags bizobj://$RING:0
scality-iod stop $D
umount /scality/$D
ls /scality/$1
