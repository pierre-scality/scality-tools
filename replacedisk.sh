for i in $(find /scality/ -maxdepth 2 -name ".ok*") ; 
do
part=$(dirname $i)
disk=$(basename $part)
longtarget=$(lsblk -l|grep part | grep -v /scality | grep 7.3| awk '{print $1}' | head -1)
target=$(echo $longtarget | sed s/1//)
uuid=$(uuidgen)
echo "=> Proposed fix : "
cat  << fin

# Added by scaldiskadd
UUID=$uuid	/scality/$disk ext4  noauto,noatime,data=ordered,barrier=1 	0	0
fin
echo parted /dev/$target rm 1
echo scaldiskreplace --partition --fstab --mkfs $disk /dev/$target

# check 
echo "=> Check : "
lsblk -ln /dev/$target
df /scality/$disk
for i in /scality/$disk $uuid ; do
grep -q $i /etc/fstab
if [ $? -eq 0 ] ; 
then
	echo "ERRROR : /scality/$disk already in fstab"
	exit 9
fi
done
echo "=> Apply  ? : " 
read dummy
cat >> /etc/fstab  << fin

# Added by scaldiskadd
UUID=$uuid      /scality/$disk ext4  noauto,noatime,data=ordered,barrier=1      0       0
fin
parted /dev/$target rm 1
scaldiskreplace --partition --fstab --mkfs $disk /dev/$target
echo "=> Done,  going next" 
done
