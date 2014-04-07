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
from scality.daemon import DaemonFactory , ScalFactoryExceptionTypeNotFound

PRGNAME=os.path.basename(sys.argv[0])
LENKEY=40
COS='20'
keylist=[]
option={}
sup ='http://127.0.0.1:5580'
#ring='ring1'
dummy=[]
file=None

def usage():
	message="""
	Check for key is exist or not and print version
	Replicas can be checked as well (-R option)


	usage : """+PRGNAME
	add="""
	KEY
	or
	
	-f file with a list of keys 	
	-r ringname
"""
	print(message+add)

def parseargs(argv):
	if len(argv)==0:
		usage()
		sys.exit(1)
	if len(argv)==1:
		k=sys.argv[1] 
	try:
		opts, args = getopt.getopt(argv, "r:f:", ["help"])
	except getopt.GetoptError:
		print "Argument error"
		usage()
		sys.exit(9)
	for i,el in enumerate(opts):
		if '-d' in el:
			opts.pop(i)
	
	for opt, arg in opts:
		dummy.append(opt)
		if opt in ("-h", "--help"):
			usage()
			end(0)
		elif opt == '-x':
			for i in range(int(arg)):
				k=KeyRandom(COS).getHexPadded()
				keylist.append(k)
		elif opt == '-r':
			option.update(ring=arg)
		elif opt == '-f':
			file=arg 
			try:
                    		fp = open(arg,"r")
            		except IOError as e :
                        	print e
				print 'impossible to open %s for read' % file
				exit(9)	
			fp.close()
			option.update(file=arg)			
	if len(args) > 0:
		for i in args:
                        keylist.append(i)
	return keylist 

def printreplica(k):
	local=[]
	for i in k.getReplicas():
		local.append(i.getHexPadded())
	return local

parseargs(sys.argv[1:])
if "ring" in option :
	ring=option['ring']
else:
	ring='ring'

nodes={}
nodestatus={}
names={}
status={}
rez=[]
#rez={}
node=""
s = Supervisor(url=sup)
ringstat=s.supervisorConfigDso(action="view", dsoname=ring)
for n in ringstat['nodes']:
	nid = '%s:%s' % (n['ip'], n['chordport'])
	nodes[nid] = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=ring)
	names[nid]=n['name']
	nodestatus[nid]=nodes[nid].nodeGetStatus()[0]
	if not node: node = nodes[nid]

def main(key):
	rez=[]
	K=key
	try: 
		k=Key(key) 
	except ValueError:
		print "%s is not a valid Key" % key
		return()
	if len(key) != LENKEY :
		print "%s is not a valid Key length" % key
		return()
	if 'replica' in option:
		rez=printreplica(k)
	rez.append(key)
	d={}
	COS=K[38:]
	rez=printreplica(k)	
	rez.append(K)
	for i in rez:
		d[i[38:]]=i
	if COS=='70':
		pred=d[max(d.keys())]
	elif COS=='75':
		pred=d['70']
	else:	
		j=int(COS)-1
		j=str(j)
		pred=d[j]	
	original=node.findSuccessor(K)['address']
	predecessor=node.findSuccessor(pred)['address']
	print "original %s %s : pred %s %s" % (K,original,pred,predecessor)
	node_o=nodes[original]
	node_p=nodes[predecessor]
	dummy=node_o.checkLocal(K)['status']
	print "key status %s : %s " % (K,dummy)
	if dummy == 'free' :
		print "Original key %s does not exist" % K
		return "KeyNotFound"
	print "deleting original key"
	node_o.chunkapiStoreOpPhysDelete(K)	
	dummy=node_o.checkLocal(K)['status']
	print "key status %s : %s " % (K,dummy)
	start_rebuild=pred[:38]+'69'
	ITERREB=10
	print "rebuild key"
	node_p.nodeRebuild(start_rebuild,ITERREB)
	print "rebuild done" 
	T=3
	t=0
	while t < T : 	
		dummy=node_o.checkLocal(K)['status']
		if dummy == 'free' :
			print "Status is free, waiting"
			time.sleep(0.5)
			t = t + 1
		else:
			print "key status %s : %s " % (K,dummy)
			break
	print "key status %s : %s " % (K,dummy)
	

	
if 'file' in option:
	file=option['file']

if file == None:
	for key in keylist :
		main(key)
else:
	with open(file, 'r') as fd:
		for key in fd:
			key=key.strip()
			#print key,len(key)
			if len(key) == LENKEY:
				main(key)
	fd.close()
