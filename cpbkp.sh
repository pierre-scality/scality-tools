#!/bin/bash

DIR=/var/tmp/ALL
HOST=sydipdsclr10
DRY=1
HOSTLIST=$(salt-key  | grep -v Keys )
MINSIZE=1000000

function usage () {
cat << fin
Copy the backup files from scality servers to $DIR
	-d	bash debug mode
	-D	activate dry run mode
fin
}

function p () {
LVL=$1
shift
MSG=$*
printf "%s : %s\n" $LVL "$MSG"
}

function run () {
if [ $DRY == 0 ]; then
echo "$@"
else
eval "$@"
fi
return $?
}


function mkd () {
D=$1
if [ ! -d $D ] ; then
        p INFO "Creating dir $D"
        run mkdir ${D}
fi
}

while getopts Ddh sarg
do
case $sarg in
        d)      set -x ;;
	D)	DRY=0 ;;
        h)      usage 
                exit 0 ;;
        *)      disp error "Arg error"
                usage
                exit 9
                ;;
esac
done
shift $(($OPTIND - 1))


AVAIL=$(df --output=avail /var/tmp | tail -1)
if [ $AVAIL -lt $MINSIZE ] ; then
p ERROR "Not enough space available on /var/tmp" 
exit
fi

if [ $DRY == 0 ]; then
p INFO "Dry run mode on"
fi
 
run mkd $DIR
run cd $DIR

for THIS in ${HOSTLIST} ;
do
        run mkd ${THIS}
	p INFO "copying files from ${THIS}"
        run scp -qBr ${THIS}:/var/lib/scality/backup/ ${DIR}/${THIS}
done

