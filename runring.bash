#!/bin/bash

RING=OWRING

N=None
SUB=supervisor 
CAT=
CHECK=1
TYPE=null
ONCE=0
LAZY=0
PART=none

function disp() { 
MSG=$1 
shift 
ALL=$*
if [ ${SILENT:=0} -eq 0 ] ; 
then
	MSG=$(echo $MSG | tr [[:lower:]] [[:upper:]])
	echo "$MSG :	$ALL"
fi
}

function end () {
echo toto > /dev/null
exit
}

trap end 9 15 


function usage() {
cat << fin
	Syntax 	: $(basename $0) OPTION type command arg
	type 	: is either node or rest 
	command : is either get or set 
	arg is the argument to run

	OPTION 
	-d 	:	shell debug mode
	-f	:	By default script is displaying command use -f to force the command to run
	-r	:	ring name
	-s 	:	Silent mode (do not show info commands)
	-1	:	Run the command 1 time and exit (useful to just check 1 parameter)

	By default script shows command (NOT EXECUTION).
	To execute command use the above -f option or set variable export RRUN=0 from your shell.
	At execution time component name is shows at each execution line	

	Sample :
	Get node log setting :	$(basename $0) -1 node get log ( "log" must be a part of ov_XXXXX_YYYY of ringsh)
	Set rs2  log setting :	$(basename $0) -f rest set msgstore_protocol_chord chordhttpsockettimeout 15
fin
}

if [ $# -eq 0 ] ; 
then
	usage
	exit 0 
fi


while getopts dflr:s1 sarg
do
case $sarg in
	f)	CHECK=0 ;; 
	d)	set -x ;;
	h)	usage 
		exit 0 ;;
	l)	LAZY=1 ;;
	r)	RING=$OPTARG ;;
	s)	SILENT=1 ;;
	1)	ONCE=1 ;;
	*)	disp error "Arg error"
		usage
		exit 9
		;;
esac
done
shift $(($OPTIND - 1))

TYPE=$1 ; shift
OP=$1 ; shift
CMD=$*

if [ ${RRUN:=1} -eq 0 ];
then
	disp INFO "Running mode from RRUN env variable"
	CHECK=-1
fi

TYPE=$(echo $TYPE|tr [[:upper:]] [[:lower:]])
OP=$(echo $OP|tr [[:upper:]] [[:lower:]])


case $TYPE in
	node) 
		GREP=Node:
		SUB=node ;; 
	rest|accessor|connector)			
		GREP=Connector:
		SUB=accessor ;;
	*)
		disp ERROR "Type unknown"
		usage
		exit
		;;
esac


CMD_LEN=$(echo $CMD | wc -w) 
case $OP in 
	get) REAL_OP=configGet
		case $CMD_LEN in
			0)	ONCE=1 ;; 
			2)	PART=$(echo $CMD|cut -d ' ' -f 2) 
				CMD=$(echo $CMD|cut -d ' ' -f 1);;
		esac
		;;	
	set) REAL_OP=configSet 	
		if [ $CMD_LEN -le 1 ];
		then
			echo "Missing parameter for Set"
			usage
			exit 2
		fi
		;;
	*)   DISP "ERROR" "unknow operator $OP"
	     usage
	     exit 1  ;;	
esac

for i in $(ringsh supervisor ringStatus $RING | grep $GREP | awk '{print $2}');
do
if [ $PART == "none" ];
then
	RUN="/usr/local/bin/ringsh -r $RING -u $i $SUB $REAL_OP $CMD"
else

	RUN="/usr/local/bin/ringsh -r $RING -u $i $SUB $REAL_OP $CMD | grep $PART"
fi
if [ ${CHECK:=1} -eq 1 ];
then
	echo "$i : $RUN"
else
	eval $RUN | sed s/^/$i:\\t/
fi
if [ $ONCE -eq 1 ] ;
then
	disp INFO "exit due to option"
	exit 0
fi
done



#for i in $(ringsh -r OWRING supervisor ringStatus OWRING |grep 8184 | sed s/:8184// | awk '{print $3}' ) ;  do sed -i s/.*pierre.*/$i\\tpierre.dlx1.msg.in.telstra.com.au\\tdlx1.msg.in.telstra.com.au/ /etc/hosts ; echo getent hosts pierre.dlx1.msg.in.telstra.com.au; ping -c 1 pierre.dlx1.msg.in.telstra.com.au ; s3cmd put /etc/hosts  S3://pierre/ ; sleep 1  ; done
