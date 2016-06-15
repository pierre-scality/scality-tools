#!/usr/bin/python2

import sys
import os
import time
import getopt
import signal
 
sys.path.insert(0,'/usr/local/scality-ringsh/ringsh/modules')
from scality.supervisor import Supervisor
from scality.node import Node
from scality.key import Key
from scality.key import KeyRandom
from scality.daemon import DaemonFactory , ScalFactoryExceptionTypeNotFound
from scality.common import ScalDaemonException


PRGNAME=os.path.basename(sys.argv[0])
PHYS=False
MXCOS=70
LENKEY=40
keylist=[]
option={}
sup ='https://127.0.0.1:2443'
#ring='ring1'
dummy=[]

def usage():
	message="""
	Check for key is exist or not and print version
	Replicas can be checked as well (-R option)


	usage : """+PRGNAME
	add="""
	-l login (default root)
	-p password
	-r ringname
	-s hostname
	-n node number
        it will delete all keys on node : ringname-hostname-n{node number}
	-c will stop after count deleted file
	-P will do a physdelete instead of delete	
	-v verbose (display keys)
"""
	print(message+add)

def handler(signum, frame):
	print 'Graceful exit'
	exit(0)

signal.signal(signal.SIGINT, handler)

def parseargs(argv):
	if len(argv)==0:
		usage()
		sys.exit(1)
	if len(argv)==1:
		k=sys.argv[1] 
	try:
		opts, args = getopt.getopt(argv, "c:l:n:p:Pr:s:v", ["help"])
	except getopt.GetoptError, e:
		print "Argument error..."+str(e.msg)
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
		elif opt == '-c':
			option.update(count=arg)
		elif opt == '-l':
			option.update(l=arg)
		elif opt == '-p':
			option.update(p=arg)
		elif opt == '-P':
			option.update(phys=True)
		elif opt == '-r':
			option.update(ring=arg)
		elif opt == '-n':
			option.update(node=arg)	
		elif opt == '-s':
			option.update(server=arg)	
		elif opt == '-e':
			option.update(run='yes')	
		elif opt == '-v':
			option.update(verbose=True)	

parseargs(sys.argv[1:])
if "ring" in option :
	ring=option['ring']
else:
	ring='DATA'

if 'login' in option:
	login=option['login']
else:
	login='root'

if 'p' in option:
	password=option['p']
else:
	password='admin'

if 'phys' in option:
	PHYS=True

target=ring+'-'+option['server']+'-n'+option['node']

nodes={}
nodestatus={}
names={}
status={}
rez=[]
#rez={}
node=""
found=False
# for i in ringstat['nodes']:
# 	if i['name']=='DATA-node4-n4':
#		target=i
#	        break 
# node=DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(target['ip'], target['adminport']), chord_addr=target['ip'], chord_port=target['chordport'], dso=ring, login=login, passwd=password)

s = Supervisor(url=sup,login=login,passwd=password)
try:
	ringstat=s.supervisorConfigDso(action="view", dsoname=ring)
except ScalDaemonException:
	print "Invalid login/passwd"
	exit(9)

for n in ringstat['nodes']:
	if n['name'] == target:
		print 'Target found node : '+target
		nid = '%s:%s' % (n['ip'], n['chordport'])
		nodes[nid] = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=ring, login=login, passwd=password)
		targetn=nodes[nid]
		found=True
		node = nodes[nid]
		break
	#names[nid]=n['name']
	#nodestatus[nid]=nodes[nid].nodeGetStatus()[0]

if not found:
	print 'No matching node found '+target

if 'verbose' in option:
	verbose=True
else:
	verbose=False

#nodes[nid].listKeys(fd)
#targetn.listKeys(fd)
if 'count' in option:
	max=int(option['count'])
	limit=True
else:
	print 'no limit'
	limit=False
count=0
a=0
stime=time.time()
for i in targetn.listKeysIter():
	if not i:
		break
	k=i.split(',')[0]
	if len(k) != 40:
		continue
	K=Key(k)
	kcos=k[-2:]
	if int(kcos,16) > MXCOS:
		if verbose:
			print "Key cos sorted out "+k
		continue
	try:
		if PHYS:
			targetn.chunkapiStoreOpPhysDelete(K,True)
		else:
			ver=int(i.split(',')[4])+64
			targetn.chunkapiStoreOpDelete(K,ver)
	except Exception, e:
		if verbose:
			print "Deletion error "+k+" "+e[0]
			continue
	if verbose and PHYS:
		print "Key physdeleted "+k
	elif verbose and not PHYS:
		print "Key deleted "+k
	else:
		if count % 100 == 0:
			a=count
			#print "\r",count,
			et=time.time()-stime
			persec=count/et
		print 'line done %d (%d per second)\r'%(a,persec),
		#print 'line done %d\r'%a,
	count+=1		
	if limit:
		if count >= max:
			print "Reached limit "+str(count)+"/"+str(max)
			break
et=time.time()-stime
persec=count/et
print "Key processed "+str(count)+", "+str(persec).split('.')[0]+" key per second" 
exit(0) 
