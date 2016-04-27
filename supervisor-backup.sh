#!/bin/sh


PRG=$(basename $0)
#DESTDIR=/var/lib/scality-supervisor/tmp/backup/
DESTDIR=/backup
DATE=$(date '+%Y%m%d')
LOGFILE=$DESTDIR/$PRG.log
SOURCE=9
DEST=1
LOGF=local0
LOGL=notice
LOG=0
RSYNCV=1 
# Retention in days
RETENTION=7
# Minimum of log file to keep 
MINRET=7

function usage() {
cat << fin
	Syntax  : $PRG OPTION 
	Sync the supervisor file to $DESTDIR
	Option are 
	-h : This help
	-l : log to syslog
	-s : Silent option 
	-S : Run the script as source (copy TO archive)
	-D : Run the script as destination (copy FROM archive)
fin
}


function disp() {
MSG=$1 
shift 
LOG=$1
shift
ALL=$*
if [ ${SILENT:=0} -eq 0 ] ; 
then
        MSG=$(echo $MSG | tr [:lower:] [:upper:])
        echo "$MSG :    $ALL"
fi
if [ ${LOG:=0} -ne 0 ] ; 
then
	#logger -p local0.notice -t "Scality" "$ALL"
	logger -p $LOGF.$LOGL -t "scality.supbackup" "$MSG $ALL"
fi
}

while getopts hDlsS sarg 
do
case $sarg in
	h) usage ; exit 0 ;;
	D) SOURCE=0 ;;
	l) LOG=1 ;;
	s) SILENT=0
	   RSYNCV=0 
	   LOG=1 ;;
	S) SOURCE=1 ;;
	*) disp ERROR $LOG "Bad option"
	   usage
	   exit 1
esac
done

if [ ${SOURCE:=9} -eq 9 ]; 
then
	disp ERROR $LOG "You must specify source or destination" 
	usage
	exit 2
fi
if [ ! -d $DESTDIR ] ; 
then
	disp ERROR $LOG "Archive dir do not exist : $DESTDIR"
	exit 9
fi 


archive_to () {
RET=0
RSOPS='av --relative'
if [ ${RSYNCV:=0} -eq 0 ] ; 
then
	RSOPS='a --relative'
fi
disp INFO $LOG "Starting copy at $(date '+%Y%m%d-%H%M%S') to $DESTDIR"
rsync -$RSOPS /etc/scality-supervisor/ $DESTDIR/$DATE/ 
[[ $? -ne 0 ]] && RET=1
rsync -$RSOPS /var/www/scality-supervisor/ $DESTDIR/$DATE/
[[ $? -ne 0 ]] && RET=1
rsync -$RSOPS /var/lib/scality-supervisor $DESTDIR/$DATE/
[[ $? -ne 0 ]] && RET=1
rsync -$RSOPS /srv/scality $DESTDIR/$DATE/
[[ $? -ne 0 ]] && RET=1
if [ -L $DESTDIR/last ] ; 
then
	rm -f $DESTDIR/last
fi
ln -s $DESTDIR/$DATE $DESTDIR/last
if [ $RET -eq 0 ] ;
then
	disp INFO $LOG "Ending copy at $(date '+%Y%m%d-%H%M%S')"
else
	disp WARN 1 "All files may have not been copied properly, ending at $(date '+%Y%m%d-%H%M%S')"
fi
}

archive_from () {
if [ ! -h $DESTDIR/last ] ; 
then
	disp ERR $LOG "No last file found please fix and re run"
	exit 9
fi
service scality-supervisor status 2&>1 
if [ $? -eq  0 ]; 
then
	disp WARNING $LOG "Supervisor was running on backup server, shutting down"
	service scality-supervisor stop
fi
disp INFO $LOG "Starting copy at $(date '+%Y%m%d-%H%M%S')"
RET=0
RSOPS='av'
if [ ${RSYNCV:=0} -eq 0 ] ;
then
        RSOPS='a'
fi
for i in etc srv/scality var ; 
do
rsync -$RSOPS $DESTDIR/last/$i/ /$i/ 
[[ $? -ne 0 ]] && RET=1
done
if [ $RET -eq 0 ] ;
then
        disp INFO $LOG "Ending copy at $(date '+%Y%m%d-%H%M%S')"
        return 0
else
        disp WARN 1 "All files may have not been copied properly, ending at $(date '+%Y%m%d-%H%M%S')"
        return 1
fi

}

remove_old_files () {
OLDDATE=$(date -d "-${RETENTION}days" '+%Y%m%d')
COUNT=$(ls -ld $DESTDIR/2*|wc -l)
if [ $COUNT -le $MINRET ];
then
	disp INFO $LOG "Not enough history to purge old files"
	return 0
fi
L=""
for i in $(ls -d $DESTDIR/2*) ; 
do
	if [ $(basename $i) -le $OLDDATE ]; 
	then
		rm -rf $i
		L="$L $(basename $i)"			
	fi
done 
disp INFO $LOG "$(echo $L| wc -w) dir removed : $L"
}


if [ $SOURCE -eq 1 ]; 
then
	if [ -d $DESTDIR/$DATE ] ;
	then
		disp WARN $LOG "Directory $DESTDIR/$DATE already exist"
	fi
	archive_to
else
	archive_from
fi
remove_old_files
