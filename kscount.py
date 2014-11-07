#!/usr/bin/python2

""" count the number of keys per range of keyspace """
""" kscount.py <file> where file is result of supervisor ringstatus"""

import os 
import sys 

file=sys.argv[1]
f=open(file)
keyspace=[]
node={}
FF='F'*40
while True:
	l=f.readline()
	if not l:
		#print 'end'
		break
	line=l.split()
        if line[0] == "Node:" :
            node[line[3]]=line[1]
            key=line[3]
            #print key
            keyspace=keyspace+[key]
            #print keyspace
keyspace.sort()
#print len(keyspace)
#exit()
for i in range(len(keyspace)):
    if i == len(keyspace)-1:
        succ=keyspace[0]
        nb=int(FF,16)-int(keyspace[i],16)+int(keyspace[0],16)
    else:
        succ=keyspace[i+1]
        nb=int(succ,16)-int(keyspace[i],16)

    print node[keyspace[i]],"\t",keyspace[i],succ,nb
