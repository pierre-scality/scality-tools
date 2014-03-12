#!/usr/bin/python2

import sys
import os
import time
import getopt
 
sys.path.insert(0,'/usr/local/scality-ringsh/ringsh/modules')
from scality.supervisor import Supervisor
from scality.node import Node
from scality.key import Key
from scality.key import KeyRandom

PRGNAME=os.path.basename(sys.argv[0])
LENKEY=40
COS='20'
keylist=[]

def usage():
	message="usage : "+PRGNAME
	add="""
	KEY
	or 
	-r (random key number)
"""
	print(message+add)

def parseargs(argv):
	if len(argv)==0:
		usage()
		sys.exit(1)
	if len(argv)==1:
		k=sys.argv[1] 
	try:
		opts, args = getopt.getopt(argv, "r:", ["help"])
	except getopt.GetoptError:
		print "Argument error"
		usage()
		sys.exit(0)
	for i,el in enumerate(opts):
		if '-d' in el:
			opts.pop(i)
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			usage()
			end(0)
		elif opt == '-r':
			for i in range(int(arg)):
				k=KeyRandom(COS).getHexPadded()
				keylist.append(k)
				
	if len(args) > 0:
		for i in args:
                        keylist.append(i)
	return keylist 

def printreplica(key):
	local=[]
	for i in k.getReplicas():
		local.append(i.getHexPadded())
	return local

#print sys.argv[1:]
parseargs(sys.argv[1:])
rez=[]
for i in keylist :
	#print 'debut %s' % i
	try: 
		k=Key(i) 
	except ValueError:
		print "%s is not a valid Key" % i
		continue
	if len(i) != LENKEY :
		print "%s is not a valid Key length" % i
		continue
	rez=printreplica(k)
	rez.append(i)
	rez=sorted(rez,key=lambda d: d[38:])
	for j in rez:
		print j,
	print

#print rez		
