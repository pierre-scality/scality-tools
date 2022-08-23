#!/bin/bash

export t=15
export dummy=/tmp/dummy
R="ROLE_CONN_CDMI ROLE_CONN_CIFS ROLE_CONN_SOFS"

for r in $(ringsh supervisor ringList) ; do 
        echo "Join ring $r"
        ringsh -r $r supervisor nodeJoinAll $r
done

echo "Waiting $t for stablisation"
sleep $t

salt "*"  grains.get roles --out=txt > $dummy

grep -q ROLE_CONN_CDMI $dummy 
if [ $? -eq 0 ] ; then
salt -G roles:ROLE_CONN_CDMI  service.restart scality-dewpoint-fcgi
salt -G roles:ROLE_CONN_CDMI  service.restart httpd
fi

grep -q ROLE_CONN_CIFS $dummy 
if [ $? -eq 0 ] ; then
salt -G roles:ROLE_CONN_CIFS  service.restart scality.sfused
salt -G roles:ROLE_CONN_CIFS  service.restart sernet-samba-smbd
fi

grep -q ROLE_CONN_SOFS $dummy 
if [ $? -eq 0 ] ; then
salt -G roles:ROLE_CONN_SOFS  service.restart scality.sfused
fi

grep -q ROLE_CONN_SVSD $dummy
if [ $? -eq 0 ] ; then
echo "Wait 5s before starting svsd"
salt -G roles:ROLE_CONN_SOFS  service.restart scality.svsd
fi


rm $dummy

