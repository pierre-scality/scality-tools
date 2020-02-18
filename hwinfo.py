#!/usr/bin/python

import os
import sys
from datetime import datetime
import argparse
import logging 

parser = argparse.ArgumentParser(description="Help to understand ring setting and create installation files  including pillar/csv")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-I', '--info', dest='info', action="store_true", default=False ,help='print verbose server information')
parser.add_argument('-S', '--selector', dest='selector', action="store_true", default=False ,help='Build selector list for scality common pillar')
parser.add_argument('-p', '--platform', dest='platform', action="store_true", default=False ,help='Generate plateform description file for hosts')
parser.add_argument('-q', '--quiet', dest='quiet', action="store_true", default=False ,help='Do not display general information on each host')
parser.add_argument('-s', '--sls', dest='sls', action="store_true", default=False ,help='Generate pillar.sls for hosts (in /var/tmp)')
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target hosts, use all to loop on all minions')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')
args, ukn = parser.parse_known_args()

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
#logger = logging.getLogger()
logger = logging.getLogger(__name__)
#ch = logging.StreamHandler()
#ch.setLevel(logging.DEBUG)
#logger.addHandler(ch)


if args.debug==True:
  logger.setLevel(logging.DEBUG)
  logger.debug('Set debug mode')

if ukn != []:
  logger.error("Some params are not correct {}".format(ukn))
  exit(9)

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
  def __init__(self,args):
    self.definition = { 'ROLE_CONN_CIFS' : 'smb', 'ROLE_ELASTIC' : 'elastic' , 'ROLE_STORE' : 'store' , 'ROLE_ZK_NODE' : 'zookeeper' , 'ROLE_SVSD' : 'svsd' , 'ROLE_CONN_SOFS' : 'sofs' , 'ROLE_CONN_NFS' : 'nfs' , 'ROLE_CONN_CDMI' : 'cdmi', 'ROLE_SUP' : 'supervisor' , 'ROLE_HALO' : 'halo' }
    self.csvbanner=['data_ip', 'data_iface', 'mgmt_ip', 'mgmt_iface', 's3_ip', 's3_iface', 'svsd_ip', 'svsd_iface', 'ring_membership', 'role', 'minion_id', 'enclosure', 'site', '#cpu', 'cpu', 'ram', '#nic', 'nic_size', '#os_disk', 'os_disk_size', '#data_disk', 'data_disk_size', '#raid_card', 'raid_cache', 'raid_card_type', '#ssd', 'ssd_size', '#ssd_for_s3', 'ssd_for_s3_size']
    self.target = args.target
    if self.target == None:
      self.target = ['all']
    self.grains = {} 
    self.get_grains_pillars()
    self.isnode = False
    self.sls = args.sls
    self.info = args.info
    self.slsdir = "/var/tmp/"
    self.silent =  args.quiet
    self.platform =  args.platform
    self.csv = {}
    
 
  def get_grains_pillars(self):
    if self.target[0] == 'all':
      logger.debug('Getting ALL grains and pillars')
      target='*'
    else:
      logger.debug('Getting grains and pillars for {}'.format(self.target[0]))
      target=self.target[0]
    self.grains=local.cmd(target,'grains.items')
    #self.pillar = local.cmd(target,'pillar.get',['scality'])
    self.pillar = local.cmd(target,'pillar.items')
    self.target = self.grains.keys()
    logger.debug('Final target list'.format(self.target))

  def get_csv_role(self,roles):
    csvrole=[]
    for i in roles:
      if i not in self.definition:
        logger.debug('role {} not in known'.format(i))
        continue
      else:
        csvrole.append(self.definition[i])
    return(csvrole) 


  def display_selector(self):
    roles={}
    logger.debug('Getting roles from {}'.format(self.grains.keys()))
    logger.info('Selector : ')
    for srv in self.grains.keys():
      for role in self.grains[srv]['roles']:
        if role not in self.definition:
          #logger.debug('role {} not in known'.format(role))
          continue
        else:
          role=self.definition[role]
        if not role in roles.keys():
          roles[role]='L@'+srv
        else:
          roles[role]=roles[role]+","+srv 
    for i in roles:
      print "{}: {}".format(i,roles[i],info=True)
    return(roles)

  def get_value(self,l,v,displ=True):
    if v in l.keys():
      if displ == True:
        self.pr_silent("{} : {}".format(v,l[v]))
      return(l[v])
    else:
      logger.debug("Value {} not found".format(v))
      return(None)

  def set_target(self):
    if self.target != None:
      if self.target == all:
        self.target == self.grains.keys()
      elif self.target not in self.grains.keys():
        logger.error("server {} is not in the list of minions.\n{}".format(target,self.grains.keys()))
        exit(0)
    print self.target
    exit()

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

  def get_srv_info(self,srv):
    serverinfo=["id","productname","num_cpus","cpu_model","mem_total","os","osrelease","SSDs"]
    hdd=["rot_count","rot_size"]
    sdd=["ssd_count","ssd_size"]
    disable_proxy()
    outdump="/tmp/"+srv+".out"
    grains=self.grains[srv]
    mounted=local.cmd(srv,'disk.usage')[srv]
    fd=open(outdump,'w')
    fd.write(str(grains))
    fd.close()
    logger.debug("grains dump for {} file : {}".format(srv,outdump))
   
    if grains['os_family'] != "RedHat":
      logger.warning('WARNING : Support only RH family')
    
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
    self.pr_silent("Raw disks list : {}\nRaw disks count : {} ".format(dlist,dcount),info=True)
    self.add_csv(srv,'minion_id',srv)
    self.add_csv(srv,'#cpu',self.grains[srv]['num_cpus'])
    self.add_csv(srv,'cpu',"\"{}\"".format(self.grains[srv]['cpu_model']))
    self.add_csv(srv,'enclosure',"\"{}\"".format(self.grains[srv]['productname']))
    hd=self.analyse_disks(mounted)
    if 'ROLE_STORE' in self.grains[srv]['roles']:
      self.pr_silent("Scality hdd found : {}".format(hd[0]),info=True) 
      self.pr_silent("Scality ssd found : {}".format(hd[1]),info=True)
      if 'rot_count' in self.grains[srv]:
        self.add_csv(srv,'#data_disk',format(self.grains[srv]['rot_count']))
        self.add_csv(srv,'data_disk_size',format(self.grains[srv]['rot_size']/self.grains[srv]['rot_count']/(1024 * 1024 * 1024)))
      else:
        logger.warning("rot_count not found in grains")
        self.add_csv(srv,'#data_disk',format(hd[0]))
      if 'ssd_count' in self.grains[srv]:
        self.add_csv(srv,'#ssd',format(self.grains[srv]['ssd_count']))
        self.add_csv(srv,'ssd_size',format(self.grains[srv]['ssd_size']/self.grains[srv]['ssd_count']/(1024 * 1024 * 1024)))
      else:
        logger.warning("ssd_count not found in grains")
        self.add_csv(srv,'#ssd',format(hd[1]))
      if not 'rings' in self.pillar[srv]['scality']:
        logger.warning("not rings found for store node {}".format(srv))
      else:
        rings="\"{}\"".format(self.pillar[srv]['scality']['rings'])
        self.pr_silent("Scality rings found : {}".format(rings),info=True)
        self.add_csv(srv,'ring_membership',format(rings))
    for this in  grains['ip4_interfaces'].keys():
      if this == 'lo':
        continue
      if grains['ip4_interfaces'][this] == []:
        if args.debug:
          print 'DEBUG : interface without ip v4'+this 
      else:
        self.pr_silent("{} : {}".format(this,grains['ip4_interfaces'][this][0]),info=True) 
    csvroles=self.get_csv_role(self.get_value(grains,'roles'))
    csvroles.sort()
    csvroles="\"{}\"".format(','.join(csvroles))
    self.add_csv(srv,'role',csvroles)

  def get_if_info(self,srv):
    pillar=self.pillar[srv]['scality'] 
    localpillar={ 'scality' : ''}
    if 'supervisor_ip' in pillar:
      self.pr_silent("supervisor_ip : {}".format(pillar['supervisor_ip']),info=True)
      localpillar['  supervisor_ip']=pillar['supervisor_ip']
    else:
      self.pr_silent("No supervisor ip defined")
    for i in ['data','mgmt']:
      if i+'_ip' in pillar:
        self.pr_silent("{}_ip : {}".format(i,pillar[i+'_ip']),info=True)
        localpillar['  '+i+'_iface']=pillar[i+'_ip']
        self.add_csv(srv,i+'_ip',pillar[i+'_ip'])
      elif i+'_iface' in pillar:
        ipv4 = self.grains[srv]['ip4_interfaces']      
        self.pr_silent("{}_ip : {} # from  (from data_iface)".format(i,pillar[i+'_iface']),info=True)
        localpillar['  '+i+'_ip']=pillar[i+'_iface']
        self.add_csv(srv,i,pillar[i+'_iface'])
      else:
       self.pr_silent("Neither {}_ip or {}_iface found".format(i,i))
    if self.sls:
      self.create_sls(localpillar,srv)

  def create_sls(self,dict,srv):
    outfile=self.slsdir+srv+".sls"
    try:
      f=open(outfile, 'w') 
    except:
      logger.error("Can't generate pillar, opening {} with error {}".format(outfile,sys.exc_info()[0]))
      return(9)
    logger.info("generating pillar sls file {}".format(outfile))
    for i in dict.keys():
      line="{}:{}".format(i,dict[i])
      self.pr_silent("{}".format(line)) 
      f.write(str(line)+"\n")
    f.close()

  def add_csv(self,host,p,v):
    if not host in self.csv.keys():
      self.csv[host] = {}
      for field in self.csvbanner:
        self.csv[host].update({field:''})
    self.csv[host].update({p:v})

  def print_csv(self):
    outfile=self.slsdir+"plateform.csv"
    header=""
    try:
      f=open(outfile, 'w') 
    except:
      logger.error("Can't generate plateform file, opening {} with error {}".format(outfile,sys.exc_info()[0]))
      return(9)
    logger.info("generating plateform file {}".format(outfile))
    for i in self.csvbanner:
      header=header+str(i)+","
    header.strip(',')
    self.pr_silent(header)
    f.write(str(header)+"\n")
    for i in self.csv.keys():
      line=""
      for j in self.csvbanner:
        line=line+str(self.csv[i][j])+","
      line.strip(',')
      self.pr_silent(line)
      f.write(str(line)+"\n")
    f.close()

  def pr_silent(self,msg,info=False):
    if self.silent == False: 
      if info == False:
        print msg
      #print "::: {} {}".format(info,self.info)
      if info == True and self.info == True:
        print msg

  def mainloop(self):
    logger.debug("Main loop with args {}".format(args))
    for i in self.target:
      logger.info("Server : {}".format(i))
      self.get_srv_info(i)
      self.get_if_info(i)
    if self.platform == True:
      self.print_csv() 
    if args.selector == True:
      self.display_selector()    
    exit(0)

def main():
  l=[]
  R=MyRing(args)
  logger.debug("Checking target {}".format(args.target))
  if args.target == None:
    if args.sls == False and args.selector==None and args.platform == False:
      logger.info("Did you use any argument ?")
      parser.print_help()
      exit(1)
  R.mainloop()

if __name__ == '__main__':
  main()
else:
  print "loaded"

