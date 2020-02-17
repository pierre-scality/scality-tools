#!/usr/bin/python

import os
from datetime import datetime
import argparse
import logging 

parser = argparse.ArgumentParser(description="Help to understand ring setting and create installation files  including pillar/csv")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-g', '--grains', dest='grains', action="store_true", default=False ,help='Get list of servers sorted  by grains')
parser.add_argument('-p', '--platform', dest='platform', action="store_true", default=False ,help='Generate plateform description file for hosts')
parser.add_argument('-q', '--quiet', dest='quiet', action="store_true", default=False ,help='Do not display general information on each host')
parser.add_argument('-s', '--sls', dest='sls', action="store_true", default=False ,help='Generate pillar.sls for hosts (in /tmp)')
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target hosts, use all to loop on all minions')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')

args,cli=parser.parse_known_args()


logging.basicConfig(format='%(asctime)s : %(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
#logger = logging.getLogger()
logger = logging.getLogger(__name__)
#ch = logging.StreamHandler()
#ch.setLevel(logging.DEBUG)
#logger.addHandler(ch)


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
    logger.debug("Proxy has been disabled")

class MyRing():
  def __init__(self,args,target='all'):
    self.definition = { 'ROLE_CONN_CIFS' : 'smb', 'ROLE_ELASTIC' : 'elastic' , 'ROLE_STORE' : 'store' , 'ROLE_ZK_NODE' : 'zookeeper' , 'ROLE_SVSD' : 'svsd' , 'ROLE_CONN_SOFS' : 'sofs' , 'ROLE_CONN_NFS' : 'nfs' , 'ROLE_CONN_CDMI' : 'cdmi', 'ROLE_SUP' : 'supervisor' , 'ROLE_HALO' : 'halo' }
    self.csvbanner=['data_ip', 'data_iface', 'mgmt_ip', 'mgmt_iface', 's3_ip', 's3_iface', 'svsd_ip', 'svsd_iface', 'ring_membership', 'role', 'minion_id', 'enclosure', 'site', '#cpu', 'cpu', 'ram', '#nic', 'nic_size', '#os_disk', 'os_disk_size', '#data_disk', 'data_disk_size', '#raid_card', 'raid_cache', 'raid_card_type', '#ssd', 'ssd_size', '#ssd_for_s3', 'ssd_for_s3_size']
    self.target = target
    self.grains = {} 
    self.get_grains()
    self.isnode = False
    self.sls = False
    self.silent =  args.quiet
    self.platform =  args.platform
    self.csv = {}
 
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
      self.pr_silent("{} : {}".format(v,l[v]))
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
    serverinfo=["id","productname","cpu_model","mem_total","os","osrelease","SSDs"]
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
   
    if grains['os_family'] != "RedHat":
      logger.warning('WARNING : Support only RH family')
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
    self.pr_silent("Raw disks list : {}\nRaw disks count : {} ".format(dlist,dcount))
    self.add_csv(self.target,'minion_id',self.target)
    hd=self.analyse_disks(mounted)
    if 'ROLE_STORE' in self.grains[self.target]:
      self.pr_silent("Scality hdd found : {}".format(hd[0])) 
      self.pr_silent("Scality ssd found : {}".format(hd[1]))
    self.add_csv(self.target,'#hdd',format(hd[0]))
    self.add_csv(self.target,'#ssd',format(hd[1]))
    for this in  grains['ip4_interfaces'].keys():
      if this == 'lo':
        continue
      if grains['ip4_interfaces'][this] == []:
        if args.debug:
          print 'DEBUG : interface without ip v4'+this 
      else:
        self.pr_silent("{} : {}".format(this,grains['ip4_interfaces'][this][0])) 
    #self.get_value(grains,'roles') 

  def get_if_info(self):
    if self.target == 'all' :
      logger.info("No specific target asked, will no go to all servers")
      return(0)
    self.get_scal_pillar(self.target)
    pillar=self.pillar[self.target] 
    localpillar={ 'scality' : ''}
    if 'supervisor_ip' in pillar:
      self.pr_silent("supervisor_ip : {}".format(pillar['supervisor_ip']))
      localpillar['  supervisor_ip']=pillar['supervisor_ip']
    else:
      self.pr_silent("No supervisor ip defined")
    for i in ['data','mgmt']:
      if i+'_ip' in pillar:
        self.pr_silent("{}_ip : {}".format(i,pillar[i+'_ip']))
        localpillar['  '+i+'_iface']=pillar[i+'_ip']
        self.add_csv(self.target,i,pillar[i+'_ip'])
      elif i+'_iface' in pillar:
        ipv4 = self.grains[self.target]['ip4_interfaces']      
        self.pr_silent("{}_ip : {} # from  (from data_iface)".format(i,pillar[i+'_iface']))
        localpillar['  '+i+'_ip']=pillar[i+'_iface']
        self.add_csv(self.target,i,pillar[i+'_iface'])
      else:
       self.pr_silent("Neither {}_ip or {}_iface found".format(i,i))
    if self.sls:
      self.createsls(localpillar)

  def createsls(self,dict):
    for i in dict.keys():
      print "{} : {}".format(i,dict[i]) 

  def add_csv(self,host,p,v):
    if not host in self.csv.keys():
      self.csv[host] = {}
      for field in self.csvbanner:
        self.csv[host].update({field:''})
    self.csv[host].update({p:v})

  def print_csv(self):
    for header in self.csvbanner:
      print header+',',
    print
    for i in self.csv.keys():
      for header in self.csvbanner:
        print str(self.csv[i][header])+",",

  def pr_silent(self,msg):
    if self.silent == False:  
      print msg

  def mainloop(self,l):
    logger.debug("Main loop with args {}".format(l))
    for i in l:
      self.set_target(i)
      self.get_srv_info()
      self.get_if_info()
    if self.platform == True:
      self.print_csv() 

def main():
  l=[]
#  print args.silent
  if args.grains == False and args.target==None:
    logger.info("Did you use -t or -g ?")
    parser.print_help()
    exit(1)
  R=MyRing(args)
  if args.sls == True:
    R.sls = True
  logger.debug("Checking target {}".format(args.target))
  if args.target != None:
    if args.target[0] == 'all' :
      l=R.grains.keys()
      R.mainloop(l)
    else:
      R.mainloop(args.target)
  if args.grains == True:
    R.display_roles()    
  exit(0)
if __name__ == '__main__':
  main()
else:
  print "loaded"

