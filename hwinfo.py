#!/usr/bin/python

import os
from datetime import datetime
import argparse
import logging 

parser = argparse.ArgumentParser(description="Check server's GEO replication status")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target daemon to check queue')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')
parser.add_argument('-g', '--grains', dest='grains', action="store_true", default=False ,help='Get list of servers sorted  by grains')

args,cli=parser.parse_known_args()


#logging.basicConfig(format='%(asctime)s : %(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
#logger = logging.getLogger()
logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)


if args.debug==True:
  logger.setLevel(logging.DEBUG)
  logger.debug('Set debug mode')


import salt.client
import salt.config
import salt.runner 
local = salt.client.LocalClient()


def disable_proxy():
  done=0
  for k in list(os.environ.keys()):
    if k.lower().endswith('_proxy'):
      del os.environ[k]
      done=1
  if done != 0:
    display.debug("Proxy has been disabled")


def get_value(l,v,displ=True):
  if v in l.keys():
    if displ == True:
      print "{} : {}".format(v,l[v])
    return(l[v])
  else:
    logger.debug("Value {} not found".format(v))
    return(None)

def analyse_disks(l):
  hdd=0
  ssd=0
  for this in l.keys():
    if this.split('/')[1] == 'scality':
      if this.split('/')[2][0:4] == 'disk':
        hdd+=1
        continue
      if  this.split('/')[2][0:3] == 'ssd':
        ssd+=1
      else:
        logger.debug("Unexpected Value found {}".format(this)) 
  return(hdd,ssd) 

def main():
  if args.grains == True:
    g=grains_sorted()
  else:
    try:
      target=args.target[0]
    except TypeError:
      print "Did you use -t or -g ?"
      exit(9)
    get_srv_info(target)

def get_srv_info(target): 
  serverinfo=["id","productname","mem_total","os","osrelease","SSDs"]
  hdd=["rot_count","rot_size"]
  sdd=["ssd_count","ssd_size"]
  disable_proxy()
  outdump="/tmp/"+target+".out"
  grains=local.cmd(args.target[0],'grains.items')
  mounted=local.cmd(args.target[0],'disk.usage')[target]
  fd=open(outdump,'w')
  fd.write(str(grains))
  fd.close()
  grains=grains[target]
  print outdump

  get_value(grains,'cpu_model') 
 
  if grains['os_family'] != "RedHat":
    print 'WARNING : Support only RH family'
  for i in serverinfo:
    get_value(grains,i)

  #if 'rot_count' in grains.keys():
  #  print "#disk : {0} size : {1}".format(grains["rot_count"],grains["rot_size"]/grains["rot_count"]/10e11)  
  #  print "#ssd : {0} size : {1}".format(grains["ssd_count"],grains["ssd_size"]/grains["ssd_count"]/10e11)  
  #else:
  # print 'INFO : No rot_count found'

  # not used 
  dcount=0
  dlist=[]
  disks=get_value(grains,'disks',displ=False)
  for this in disks:
    if this[0:3] == 'ram':
      continue
    if this[0:4] == 'loop':
      continue
    dcount+=1
    dlist.append(this)
  print "Raw disks list : {}\nRaw disks count : {} ".format(dlist,dcount)

  hd=analyse_disks(mounted)
  print "Scality hdd found : {}".format(hd[0]) 
  print "Scality ssd found : {}".format(hd[1]) 

  for this in  grains['ip4_interfaces'].keys():
    if this == 'lo':
      continue
    if grains['ip4_interfaces'][this] == []:
      if args.debug:
        print 'DEBUG : interface without ip v4'+this 
    else:
      print "{} : {}".format(this,grains['ip4_interfaces'][this][0]) 

  get_value(grains,'roles') 

def grains_sorted():
  roles={}
  logger.debug('Getting all grains')
  grains=local.cmd('*','grains.get',['roles'])
  for srv in grains.keys():
    for role in grains[srv]:
      if not role in roles.keys():
        roles[role]='L@'+srv
      else:
        roles[role]=roles[role]+","+srv 
  return(roles)

def display_roles():
  definition = { 'ROLE_CONN_CIFS' : 'smb', 'ROLE_ELASTIC' : 'elastic' , 'ROLE_STORE' : 'store' , 'ROLE_ZK_NODE' : 'zookeeper' , 'ROLE_SVSD' : 'svsd' }

if __name__ == '__main__':
  main()
else:
  print "loaded"

