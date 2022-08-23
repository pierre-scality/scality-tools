echo "Checking cpu info should have all 4 : sse4_1 sse4_2 movbe pclmulqdq"
egrep --color 'sse4_1|sse4_2|movbe|pclmulqdq' /proc/cpuinfo
echo "OK to continue ? (if you have not you may have hectic behaviour)"
read dummy

U=pierre.merle@scality.com
VGOS=300G
VGART=960G

echo "registaring with $U"
subscription-manager register --username $U
subscription-manager attach
subscription-manager repos --enable=rhel-8-for-x86_64-baseos-rpms --enable=rhel-8-for-x86_64-appstream-rpms


echo "OK to continue ?"
read dummy

echo "Installing needed pkg"
yum -y install --assumeyes lvm2 isomd5sum python3 tmux 

echo "pkg done, continue ?"
read dummy

lsblk
DEV=$(lsblk |grep $VGOS | awk '{print $1}')
DEV=/dev/$DEV
echo "Device for OS exention $DEV, ok ? "
read dummy

pvcreate $DEV
vgcreate vgos $DEV
lvcreate -n scality_releases -L 70G vgos
mkfs.xfs /dev/vgos/scality_releases
mkdir -p /srv/scality/releases
echo "/dev/vgos/scality_releases              /srv/scality/releases/             xfs      defaults       0 0" >> /etc/fstab
#mount /dev/vgos/scality_releases /srv/scality/releases
mount /srv/scality/releases

df | grep /srv/scality/releases

lsblk
DEV=$(lsblk |grep $VGART | awk '{print $1}')
DEV=/dev/$DEV

echo "creating vgartesca on : $DEV, ok ?"
read dummy
pvcreate $DEV
vgcreate vgartesca $DEV

echo "OK ? will do a full upgrade"
read dummy
yum -y upgrade

 


