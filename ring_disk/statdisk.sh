RING=DATA
echo "disk mountpoint"
findmnt --target /scality/$1 -n
if [ $? -ne 0 ]; then
echo "ERROR disk /scality/$1 not mounted"
exit
fi
echo -n "iod status $1 : "
scality-iod status $1
echo -n "disk flag $1 : "
bizioctl -N $1 -c get_mflags bizobj://$RING:0
