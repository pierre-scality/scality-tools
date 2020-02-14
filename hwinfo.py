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

class MyRing():
  def __init__(self,target='all'):
    self.definition = { 'ROLE_CONN_CIFS' : 'smb', 'ROLE_ELASTIC' : 'elastic' , 'ROLE_STORE' : 'store' , 'ROLE_ZK_NODE' : 'zookeeper' , 'ROLE_SVSD' : 'svsd' , 'ROLE_CONN_SOFS' : 'sofs' , 'ROLE_CONN_NFS' : 'nfs' , 'ROLE_CONN_CDMI' : 'cdmi', 'ROLE_SUP' : 'supervisor' , 'ROLE_HALO' : 'halo' }
    self.target = target
    self.grains = {} 
    self.get_grains()
    self.isnode = False
 
  def get_grains(self):
    logger.debug('Getting all grains')
    self.grains=local.cmd('*','grains.get',['roles'])

  def get_scal_pillar(self,target='*'):
    logger.debug('Getting pillar for {}'.format(target))
    self.pillar = local.cmd(target,'pillar.get',['scality'])
     
  def display_roles(self):
    roles={}
    for srv in self.grains.keys():
      for role in self.grains[srv]:
        if role not in self.definition:
          logger.debug('role {} not in known'.format(role))
          continue
        else:
          role=self.definition[role]
        if not role in roles.keys():
          roles[role]='L@'+srv
        else:
          roles[role]=roles[role]+","+srv 
    for i in roles:
      print "{}: {}".format(i,roles[i])
    return(roles)

  def get_value(self,l,v,displ=True):
    if v in l.keys():
      if displ == True:
        print "{} : {}".format(v,l[v])
      return(l[v])
    else:
      logger.debug("Value {} not found".format(v))
      return(None)

  def set_target(self,target):
    if target not in self.grains.keys():
      logger.error("server {} is not in the list of minions.\n{}".format(target,self.grains.keys()))
      exit(0)
    self.target=target

  def analyse_disks(self,l):
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

  def get_srv_info(self):
    if self.target == 'all' :
      logger.info("No specific target asked, will no go to all servers")
      return(0) 
    serverinfo=["id","productname","mem_total","os","osrelease","SSDs"]
    hdd=["rot_count","rot_size"]
    sdd=["ssd_count","ssd_size"]
    disable_proxy()
    outdump="/tmp/"+self.target+".out"
    #grains=self.grains[self.target]
    grains=local.cmd(self.target,'grains.items')[self.target]
    mounted=local.cmd(self.target,'disk.usage')[self.target]
    fd=open(outdump,'w')
    fd.write(str(grains))
    fd.close()
    #grains=grains[self.target]
    logger.debug("outdump file : {}".format(outdump))
    self.get_value(grains,'cpu_model') 
   
    if grains['os_family'] != "RedHat":
      print 'WARNING : Support only RH family'
    for i in serverinfo:
      self.get_value(grains,i)

    #if 'rot_count' in grains.keys():
    #  print "#disk : {0} size : {1}".format(grains["rot_count"],grains["rot_size"]/grains["rot_count"]/10e11)  
    #  print "#ssd : {0} size : {1}".format(grains["ssd_count"],grains["ssd_size"]/grains["ssd_count"]/10e11)  
    #else:
    # print 'INFO : No rot_count found'

    # not used 
    dcount=0
    dlist=[]
    disks=self.get_value(grains,'disks',displ=False)
    for this in disks:
      if this[0:3] == 'ram':
        continue
      if this[0:4] == 'loop':
        continue
      dcount+=1
      dlist.append(this)
    print "Raw disks list : {}\nRaw disks count : {} ".format(dlist,dcount)

    hd=self.analyse_disks(mounted)
    if 'ROLE_STORE' in self.grains[self.target]:
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

    self.get_value(grains,'roles') 

  def get_if_info(self):
    if self.target == 'all' :
      logger.info("No specific target asked, will no go to all servers")
      return(0)
    self.get_scal_pillar(self.target)
    pillar=self.pillar[self.target] 
    if 'supervisor_ip' in pillar:
      print "Supervisor ip : {}".format(pillar['supervisor_ip'])
    else:
      print "No supervisor ip defined"
    if 'data_ip' in pillar:
      print "data_ip : {}".format(pillar['supervisor_ip'])
    elif 'data_iface' in pillar:
      ipv4 = self.grains[self.target]['ip4_interfaces']      
      print "data_ip (from data_iface): {}".format(pillar['supervisor_ip'])
    else:
      print "Neither data_ip or data_iface found"

def main():
  R=MyRing()
  if args.target != None:
    R.set_target(args.target[0])
    R.get_srv_info()
    R.get_if_info()
  elif args.grains == True:
    R.display_roles()    
  else:
    print "Did you use -t or -g ?"
    exit(9)
 
if __name__ == '__main__':
  main()
else:
  print "loaded"

