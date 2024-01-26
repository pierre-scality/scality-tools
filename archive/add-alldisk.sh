if [ $# -ne 1 ]; then
echo "need node name"
fi

RING=META
NB_DISKS=1
HOST=$1
DISK=ssd
DRY=0

for node in $(ringsh supervisor ringStatus ${RING} | grep -w ${HOST} | awk '/^Node:/ {print $2}'); do
    if [ $DRY -ne 0 ] ; then
      echo ringsh -r ${RING} -u ${node} node diskConfigSet $(eval echo g{1,2}${DISK}{01..${NB_DISKS}});
    else
      ringsh -r ${RING} -u ${node} node diskConfigSet $(eval echo g{1,2}${DISK}{01..${NB_DISKS}});
    fi
done

