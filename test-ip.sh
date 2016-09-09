TIMER=1
MIN=1
MAX=6
function bump () {
CUR=$1
if [ $CUR -gt 5 ]  ; 
then 
	i=1
else 
	i=$(( $CUR + 1 ))
fi
}
function op () { 
OP=$2 ; K=$1 ; 
if [ $2 == 'PUT' ] ; 
then 
PL='--data-binary @/etc/hosts' 
else 
PL=''
fi 
while true ; do /usr/bin/time -f " ${OP:0:3} $IP $K \t%e" curl -f -s -o /dev/null -w "%{http_code}" -X${OP} http://$IP:81/proxy/chord/$K ${PL}
if [ $? -eq 0 ] ; then return  ; fi 
bump $i
IP=${MASK}$i
sleep 1
done
}
i=1
MASK=192.208.1.10
IP=$MASK$i
while true ; do 
IP=$MASK${i}
K=$(ringsh key random | sed s/00$/20/)
for OP in PUT GET DELETE;
do
op $K $OP 
sleep $TIMER 
done 
done 

