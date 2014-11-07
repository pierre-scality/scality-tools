#!/usr/bin/python2
import os 
import sys 

file=sys.argv[1]
f=open(file)
keyspace=[]
node={}
FF='F'*40

"""
ringStatus 
Node: node1-n4 192.177.1.11:8087 0000000000000000000000000000000000000000 RUN
ringsh.tx
supervisor nodeAssignId RING Server10 8085 CE38E38EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA40

"""

while True:
	l=f.readline()
        if not l:
		#print 'end'
		break
	line=l.split()
	#print line
        if file=="ringsh.txt":
            node[line[5]]=line[3]
            key=line[5]
            #print 'ringsh '+key
        else:
            #print 'node '+str(line)
            #if line[0] == "Node:" :
            node[line[2]]=line[0].split('-')[0]
            key=line[2]
            #print 'ringstatus '+key
        keyspace=keyspace+[key]
        #print keyspace
keyspace.sort()
#print node
#print len(keyspace)
#exit()
serverkey={}
for i in range(len(keyspace)):
    if i == len(keyspace)-1:
        succ=keyspace[0]
        nb=int(FF,16)-int(keyspace[i],16)+int(keyspace[0],16)
    else:
        succ=keyspace[i+1]
        nb=int(succ,16)-int(keyspace[i],16)
    if node[keyspace[i]] not in serverkey.keys():
        serverkey[node[keyspace[i]]]=nb
    else:
        serverkey[node[keyspace[i]]]=serverkey[node[keyspace[i]]]+nb
    print node[keyspace[i]],"\t",keyspace[i],succ,nb

print "server total keys count"
for server in serverkey.keys():
    print server,"\t",serverkey[server]
