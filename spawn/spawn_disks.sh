#!/bin/bash
VDISKS_FOLDER="/opt/vdisks"
VDISKS_HDD_SIZE_GB=(10 10 10 10)
VDISKS_SSD_SIZE_GB=(5 5)

set -e

DBG=""
# Uncomment the following to debug
# DBG=echo

# create vdisks folders if it is not already
$DBG mkdir -p "$VDISKS_FOLDER"/{hdd,ssd}

if [ -f /etc/redhat-release ]
then
    # If centos/rhel 6 then produce loop devices as losetup does not create them
    # the following command will create 256 loop device
    release_pkg=$(rpm -qa | grep -iE '(centos|oracle|redhat|rocky)-release.*')
    major_version=$(rpm -q --queryformat '%{version}\n' \
        "$release_pkg" | cut -d '.' -f 1)
    if [ "$major_version" = "6" ]; then
        $DBG /sbin/MAKEDEV -v /dev/loop
    fi
else
    for ((i=1; i <= $((${#VDISKS_HDD_SIZE_GB[@]} + ${#VDISKS_SSD_SIZE_GB[@]})); ++i))
    do
        $DBG mknod -m0660 /dev/loop$i b 7 $i
    done
fi

# create virtual hard disk files
for ((idx=1; idx <= ${#VDISKS_HDD_SIZE_GB[@]}; ++idx))
do
    if [ ! -f "$VDISKS_FOLDER/hdd/vdisk-$idx" ]
    then
        HDD_SIZE_GB=${VDISKS_HDD_SIZE_GB[((idx - 1))]}
        $DBG truncate -s "${HDD_SIZE_GB}G" "$VDISKS_FOLDER/hdd/vdisk-$idx"
    fi
        loop_dev=$(losetup -f)
        $DBG losetup -f --show "$VDISKS_FOLDER/hdd/vdisk-$idx"

    # Mark disk as rotational (required on aws)
    loop_dev_name=${loop_dev#/dev/*}
    rota="/sys/block/$loop_dev_name/queue/rotational"
    if [ -z "$DBG" ]
    then
        echo 1 > "$rota"
    else
        $DBG "Setting $rota to 1"
    fi
done

# create virtual ssd disk files
for ((idx=1; idx <= ${#VDISKS_SSD_SIZE_GB[@]}; ++idx))
do
    if [ ! -f "$VDISKS_FOLDER/ssd/vdisk-$idx" ]
    then
        SSD_SIZE_GB=${VDISKS_SSD_SIZE_GB[((idx - 1))]}
        $DBG truncate -s "${SSD_SIZE_GB}G" "$VDISKS_FOLDER/ssd/vdisk-$idx"
    fi
    loop_dev=$(losetup -f)
    $DBG losetup -f --show "$VDISKS_FOLDER/ssd/vdisk-$idx"

    # Mark the disk as ssd (required on p9)
    loop_dev_name=${loop_dev#/dev/*}
    rota="/sys/block/$loop_dev_name/queue/rotational"
    if [ -z "$DBG" ]
    then
        echo 0 > "$rota"
    else
        $DBG "Setting $rota to 0"
    fi
done

# Setup systemd service
if [ -f /etc/redhat-release ]
then
    MYDIR=$(dirname "$0")
    if [ "$major_version" != "6" ]
    then
        cp "$MYDIR/spawn_disks.service" /usr/lib/systemd/system/
        systemctl enable spawn_disks.service
    fi
fi
