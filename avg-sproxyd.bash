#!/bin/bash
 
if [ $# -ne 1 ];
then
        echo "need file"
        exit
else
        FILE=$1
fi
 
if [ ! -f $FILE ];
then
        echo "file $FILE not found"
        exit
fi
 
FILE=$1
awk '
BEGIN{
pnb=0;psum=0;
gnb=0;gsum=0;
dnb=0;dsum=0;
}
/type=\"start/ {next}
#/path_info=\"\.stats/ {next}
/\.stats/ {next}
/method=\"GET/ {gnb+=1 ; split($17,a,/"/); split(a[2],b,/ms/) ; gsum+=b[1] ; }
/method=\"PUT/ {pnb+=1 ; split($17,a,/"/); split(a[2],b,/ms/) ; psum+=b[1] ; }
/method=\"DELETE/ {dnb+=1 ; split($17,a,/"/); split(a[2],b,/ms/) ; dsum+=b[1] }
END {
gave=gsum/gnb ;
pave=psum/pnb ;
dave=dsum/dnb ;
print "average GET " gave ;
print "average PUT " pave ;
print "average DEL " dave ;
}
' $FILE
