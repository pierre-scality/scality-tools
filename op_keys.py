#!/usr/bin/env python
'''
Read keys from stdin and tries to find them by running listKeys on their node.
'''

import sys, os, getopt , re

sys.path.insert(0,'scality')
import subprocess,httplib

from scality.supervisor import Supervisor
from scality.daemon import DaemonFactory , ScalFactoryExceptionTypeNotFound
from scality.key import Key

def usage(output):
    output.write("""Usage: %s -o [operation] [options]
        Options:
        -h|--help                    Show this help message
       
	-a|--all deletes all the replicas
	-c|--check check the key after operation
	-l|--login login node login (internal credentials)
        -k	single key to process
        -f|--filename containing a list of keys to undelete 
	-p|--password login node password (internal credentials)
        -r|--ring ring name
        -s|--supurl Supervisor Url
        -o| operation can be delete undelete or physdelete

""" % os.path.basename(sys.argv[0]))
def clean_status(status):
	#{'status': 'free', 'deleted': False, 'version': None, 'needquorum': False, 'size': None}
	out=''
	for i in status:
		if i == 'deleted':
			if status[i] == False: 
				out='|'+"NOT DELETED"+out
			else:
				out='|'+"DELETED"+out
			continue
		if i == 'version':
			out='|'+"version "+str(status[i])+out
			continue
		if i == 'status':
			if status[i] == 'free':
				out='|'+"status NOKEY"
			out='|'+"status "+str(status[i])+out
			continue
		if i == 'size':
			out='|'+"size "+str(status[i])+out
	return out	
operation_list = ("rebuild","delete","physdelete","undelete")

if __name__ == "__main__":
    #options="hacr:s:f:l:p:o:"
    options="acf:k:hl:o:p:r:s:"
    long_options=["help", "check","ring=","supurl=","filename=","login=", "operation","password="]

    try:
        opts, args = getopt.getopt(sys.argv[1:], options, long_options)
    except getopt.GetoptError, err:
        sys.stderr.write("getopt error %s" % err)
        usage(sys.stderr)
        sys.exit(2)

    ring = None
    sup = None
    key = None
    all = None
    login = "root"
    password = "admin"
    for o, a in opts:
        if o in ("-h", "--help"):
            usage(sys.stdout)
            sys.exit(0)
        elif o in ("-r", "--ring"):
            ring = a
	elif o in ("-c","--check"):
	    check= True
        elif o in ("-s", "--supurl"):
            sup = a
        elif o in ("-a", "--all"):
            all = True
        elif o in ("-f", "--filename"):
	    try:
		    fp = open(a,"r")
	    except IOError as e :
			print e
        elif o in ("-k"):
            fp = open('/tmp/ops_key.entry', 'w')
	    fp.write(a)
	    fp.close()
	    fp = open('/tmp/ops_key.entry',"r")
        elif o in ("-l", "--login"):
            login = a
        elif o in ("-p", "--password"):
            password = a
        elif o in ("-o","--operation"):
            if a not in operation_list:
		print "operation not in operation list : {0}".format(str(operation_list))
		exit()
            operation = a
        else:
            usage(sys.stderr)
            sys.exit(2)

    if not ring:
    	print "missing ring"
        usage(sys.stderr)
        sys.exit(2)

    if not sup:
	sup = 'http://127.0.0.1:5580'
    
    if not operation:
        print "No operation, please use -o | --operation"
        usage(sys.stderr)
        exit(9)	

    s = Supervisor(url=sup, login=login, passwd=password)
    nodes = {}
    success = True
    node =  None
    arck = None

    for n in s.supervisorConfigDso(dsoname=ring)['nodes']:
	nid = '%s:%s' % (n['ip'], n['chordport'])
	nodes[nid] = DaemonFactory().get_daemon("node",url='https://{0}:{1}'.format(n['ip'],n['adminport']),chord_addr=n['ip'],chord_port=n['chordport'],dso=ring,login=login,passwd=password)
	if not node: node = nodes[nid]

    for line in fp.readlines():
		key = Key(line)
		print "Key to Analyse :\t", key.getHexPadded()
		if all:
			key_list = [ key ] + [ x for x in key.getReplicas() ]
		else:
			key_list = [ key ]
	        for arck in key_list :
			check = nodes[node.findSuccessor(arck.getHexPadded())["address"]]
                        try:
				tab = check.checkLocal(arck.getHexPadded())
                        except httplib.HTTPException as e:
				print "Error on key {0}".format(arck.getHexPadded())
				print >> sys.stderr, \
					"{0} from {1} for key {2}".format(e, check._chord.hostport, arck.getHexPadded())
				continue
			print  "Current \t {0} current {1} status {2}".format(key.getHexPadded(),arck.getHexPadded(),clean_status(tab))
			if operation == "undelete":
				if tab["deleted"] == True:
					print "Undelete Key \t{0}",clean_status(arck.getHexPadded())
					version = int(tab["version"]+64)
					try:
				     		et= check.chunkapiStoreOp(op="undelete", key=arck.getHexPadded(), extra_params={"version": version})
				     		print {"status": et.find("result").find("status").text}
					except ScalFactoryExceptionTypeNotFound as e:
				     		print "Error %s " , e
				else:
					print "Key {0} not deleted".format(arck.getHexPadded())
			elif operation == "delete":
				#print "{0} Key {1}".format(operation,arck.getHexPadded())
				if tab["deleted"] == True:
					print "Key {0} already deleted".format(arck.getHexPadded())
					continue
				version = int(tab["version"]+64)
				try:
					et= check.chunkapiStoreOp(op="delete", key=arck.getHexPadded(), extra_params={"version": version})
			     		#print {"status": et.find("result").find("status").text}
					print "After operation {0} Key {1}".format(operation,arck.getHexPadded())
				except ScalFactoryExceptionTypeNotFound as e:
			     		print "Error %s " , e
			elif operation == "physdelete":
				et = check.chunkapiStoreOp("physdelete", key=arck.getHexPadded())	
			elif operation == "rebuild":
				#nodeRebuild(self, range_start='0', number='0', flags=0, key=None, mask=None, filter_type=None, filter_value=None)
			 	k = arck.getHexPadded()
				#print arck,arck.getHexPadded(),k
				cosk,repk = k[-2:],k[-1]
				#print "toto",k,cosk,repk,cosk[0]+'0'
				if cosk != cosk[0]+'0':
					lookup=cosk[0]+str((int(cosk[1])-1))
				else:
					lookup=cosk[0]+cosk[0]
					#print lookup,cosk[0],cosk[1]
				replicas = [ x.getHexPadded() for x in arck.getReplicas() ]
				dict={}
				for i in replicas:
					dict[i[-2:]]=i
				predkey=dict[lookup]
				print "Before ops :\tkey {1} : pred {0} reps : {2}".format(predkey,str(k),str(replicas))
				prednode = nodes[node.findSuccessor(predkey)["address"]]
				#print "***"+prednode.nodeGetStatus()[0]['chord_addr']
                        	try:
                                	tab = prednode.checkLocal(predkey)
                        	except httplib.HTTPException as e:
                                	print "Error on key {0}".format(arck.getHexPadded())
                                	print >> sys.stderr, "{0} from {1} for key {2}".format(e, check._chord.hostport, arck.getHexPadded())
                                	continue
				print "Replicas \t{0} {1}".format(predkey,clean_status(tab))
				start=predkey[0:38]+str(int(predkey[38:])-1)
				#print start
				prednode.nodeRebuild(range_start=start,number=3)

			if check:
				tab = check.checkLocal(arck.getHexPadded())
				print "Result key\t {0} :  {1}".format(arck.getHexPadded(),clean_status(tab))

    fp.close()

    sys.exit(0 if success else 1)
