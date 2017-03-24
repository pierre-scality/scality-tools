#!/usr/bin/env python
'''
Read keys from stdin and tries to find them by running listKeys on their node.
'''

import sys, os, getopt , re

sys.path.insert(0,'scality')
import subprocess

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
        -f|--filename containing a list of keys to undelete 
	-p|--password login node password (internal credentials)
        -r|--ring ring name
        -s|--supurl Supervisor Url
        -o| operation can be delete undelete or physdelete

""" % os.path.basename(sys.argv[0]))

if __name__ == "__main__":
    #options="hacr:s:f:l:p:o:"
    options="acf:hl:o:p:r:s:"
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
        elif o in ("-l", "--login"):
            login = a
        elif o in ("-p", "--password"):
            password = a
        elif o in ("-o","--operation"):
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
	nodes[nid] = DaemonFactory().get_daemon(
            "node",
            url='https://{0}:{1}'.format(n['ip'], n['adminport']),
            chord_addr=n['ip'],
            chord_port=n['chordport'],
            dso=ring,
            login=login,
            passwd=password)
	if not node: node = nodes[nid]

    for line in fp.readlines():
		key = Key(line)
		print "Key to Analyse:", key.getHexPadded()
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
			print  "%s;%s;%s" % ( key.getHexPadded() , arck.getHexPadded() , tab )
			if operation == "undelete":
				if tab["deleted"] == True:
					print "Undelete Key " , arck.getHexPadded()
					version = int(tab["version"]+64)
					try:
				     		et= check.chunkapiStoreOp(op="undelete", key=arck.getHexPadded(), extra_params={"version": version})
				     		print {"status": et.find("result").find("status").text}
					except ScalFactoryExceptionTypeNotFound as e:
				     		print "Error %s " , e
			elif operation == "delete":
				print "{0} Key ".format(operation,arck.getHexPadded())
				if tab["deleted"] == True:
					print "Key {0} already deleted".format(arck.getHexPadded())
					continue
				version = int(tab["version"]+64)
				try:
					et= check.chunkapiStoreOp(op="delete", key=arck.getHexPadded(), extra_params={"version": version})
			     		print {"status": et.find("result").find("status").text}
				except ScalFactoryExceptionTypeNotFound as e:
			     		print "Error %s " , e
			elif operation == "physdelete":
				et = check.chunkapiStoreOp("physdelete", key=arck.getHexPadded())	
			elif operation == "rebuild":
				#nodeRebuild(self, range_start='0', number='0', flags=0, key=None, mask=None, filter_type=None, filter_value=None)
			 	k = arck.getHexPadded()
				#print arck,arck.getHexPadded(),k
				cosk,repk = k[-2:],k[-1]
				print "toto",k,cosk,repk
				max=cosk[0]+cosk[0]
				if cosk == max:
					lookup=cosk[0]+'0'
				else:
					lookup=cosk[0]+str((int(cosk[1])-1))
					print lookup,cosk[0],cosk[1]
				s = [ x.getHexPadded() for x in arck.getReplicas() ]
				dict={}
				for i in s:
					dict[i[-2:]]=i
				predkey=dict[lookup]
				print "pred {0} : key {1} : reps : {2}".format(predkey,str(k),str(s))
			if check:
				tab = check.checkLocal(arck.getHexPadded())
				print str(arck),str(tab)

    fp.close()

    sys.exit(0 if success else 1)
