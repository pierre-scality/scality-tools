#!/usr/bin/python2

import sys
import time
 
sys.path.insert(0,'/usr/local/scality-ringsh/ringsh/modules')
from scality.supervisor import Supervisor
from scality.node import Node
from scality.key import Key

LENKEY=40

def usage():
	message="usage : "+PRGNAME
	add="""
	KEY
"""
	print(message+add)

def parseargs(argv,option):
	if len(argv)==0:
		return option
	try:
		opts, args = getopt.getopt(argv, "AdF:hLoPs:t:T:qvz:", ["help"])
	except getopt.GetoptError:
		Message.fatal(PRGNAME,"Argument error",10)
	for i,el in enumerate(opts):
		if '-d' in el:
			opts.pop(i)
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			usage()
			end(0)
		elif opt == '-A':
			option['ALL']=1

def printreplica(key):
	local=[]
	for i in k.getReplicas():
		local.append(i.getHexPadded())
	return local

#print sys.argv[1:]
list=sys.argv[1:]
rez=[]
for i in list :
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
	for j in rez:
		print j,
	print

#print rez		
