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

logging.basicConfig(format='%(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
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
    self.virtualhost = ['VMware Virtual Platform','OpenStack Nova']
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
    minionvers = {}
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
    for i in self.grains.keys():
      if self.grains[i]['saltversion'] not in minionvers.keys():
        minionvers[self.grains[i]['saltversion']]=[i]
      else:
        minionvers[self.grains[i]['saltversion']].append(i)
    if len(minionvers) != 1:
      tmp=""
      for i in minionvers.keys():
        tmp=tmp+str(i)+','
      logger.warning("Different version of salt running {}".format(tmp.rstrip(',')))
    return(0)

  def get_csv_role(self,roles):
    csvrole=[]
    for i in roles:
      if i not in self.definition:
        logger.debug('role {} not in known roles'.format(i))
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

  def get_value(self,l,v,displ=False):
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
    #hdd=["rot_count","rot_size"]
    #sdd=["ssd_count","ssd_size"]
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
    disks=self.get_value(grains,'disks')
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
    enclosure=self.grains[srv]['productname']
    if enclosure in self.virtualhost:
      enclosure="VIRTUAL MACHINE"
    self.add_csv(srv,'enclosure',"\"{}\"".format(enclosure))
    hd=self.analyse_disks(mounted)
    for this in  grains['ip4_interfaces'].keys():
      if this == 'lo':
        continue
      if grains['ip4_interfaces'][this] == []:
        if args.debug:
          print 'DEBUG : interface without ip v4'+this 
      else:
        self.pr_silent("{} : {}".format(this,grains['ip4_interfaces'][this][0]),info=True) 
    if 'roles' not in self.grains[srv]:
      logger.warning("Server {} hasn\'t any roles grain".format(srv))
      return(1)
    if 'ROLE_STORE' in self.grains[srv]['roles']:
      logger.debug("Store server getting disk count")
      self.pr_silent("Scality hdd found : {}".format(hd[0]),info=True) 
      self.pr_silent("Scality ssd found : {}".format(hd[1]),info=True)
      if 'rot_count' in self.grains[srv]:
        self.add_csv(srv,'#data_disk',format(self.grains[srv]['rot_count']))
        if 'rot_size' in self.grains[srv]:
          self.add_csv(srv,'data_disk_size',format(self.grains[srv]['rot_size']/self.grains[srv]['rot_count']/(1024 * 1024 * 1024)))
        else:
          logger.warning("Server {} has rot_count but no rot_size".format(srv))
      else:
        logger.warning("Server {} has no rot_count".format(srv))
        self.add_csv(srv,'#data_disk',format(hd[0]))
      if 'ssd_count' in self.grains[srv]:
        self.add_csv(srv,'#ssd',format(self.grains[srv]['ssd_count']))
        if 'ssd_size' in self.grains[srv]:
          self.add_csv(srv,'ssd_size',format(self.grains[srv]['ssd_size']/self.grains[srv]['ssd_count']/(1024 * 1024 * 1024)))
        else:
          logger.warning("Server {} has ssd_count but no ssd_size".format(srv))
      else:
        logger.warning("Server {} has no ssd_count".format(srv))
        self.add_csv(srv,'#ssd',format(hd[1]))
      if not 'rings' in self.pillar[srv]['scality']:
        logger.warning("not rings found for store node {}".format(srv))
      else:
        rings="\"{}\"".format(self.pillar[srv]['scality']['rings'])
        self.pr_silent("Scality rings found : {}".format(rings),info=True)
        self.add_csv(srv,'ring_membership',format(rings))
    roles=self.get_value(grains,'roles')
    csvroles=self.get_csv_role(roles)
    csvroles.sort()
    csvroles="\"{}\"".format(','.join(csvroles))
    self.add_csv(srv,'role',csvroles)
    # This is the default output
    if not isinstance(roles, list): 
      roles=roles.split()
    strroles=''.join(","+e for e in roles)[1:]
    print "Server {:<10} has roles : {:<20}".format(srv,strroles)

  def get_if_info(self,srv):
    pillar=self.pillar[srv]['scality'] 
    localpillar={}
    if 'supervisor_ip' in pillar:
      self.pr_silent("supervisor_ip : {}".format(pillar['supervisor_ip']),info=True)
      localpillar['supervisor_ip']=pillar['supervisor_ip']
    else:
      self.pr_silent("No supervisor ip defined")

    data_ip=""
    if 'data_ip' in pillar:
      self.pr_silent("data_ip : {}".format(pillar['data_ip']),info=True)
      self.add_csv(srv,'data_ip',pillar['data_ip'])
    elif 'data_iface' in pillar:
      iface=pillar['data_iface']
      if not iface in self.grains[srv]['ip4_interfaces']:
        logger.error("data_iface {} is not present in grains {}".format(iface,self.grains[srv]['ip4_interfaces']))
        for iface in self.grains[srv]['ip4_interfaces'].keys():
          if not self.grains[srv]['ip4_interfaces'][iface] == []:
            if self.grains[srv]['ip4_interfaces'][iface][0] != '127.0.0.1':
              logger.warning("Server {} Using random local ip as no data ip/if grain found : chosen {}".format(srv,self.grains[srv]['ip4_interfaces'][iface][0]))
              break
        return(1)
      else:
        data_ip = self.grains[srv]['ip4_interfaces'][iface][0] 
        self.pr_silent("data_ip : {}".format(data_ip),info=True)
        self.add_csv(srv,'data_ip',data_ip)
    
    if 'mgmt_ip' in pillar:
      self.pr_silent("mgmt_ip : {}".format(pillar['mgmt_ip']),info=True)
      self.add_csv(srv,'mgmt_ip',pillar['mgmt_ip'])
    elif 'mgmt_iface' in pillar:
      iface=pillar['mgmt_iface']
      if not iface in self.grains[srv]['ip4_interfaces']:
        logger.error("SERver {} mgmt_iface {} is not present in grains {}".format(srv,iface,self.grains[srv]['ip4_interfaces']))
        if data_ip != "":
          logger.debug("Using data ip for mgmt ip as neither mgmt_ip/mgmt_iface usable")
          mgmt_ip=data_ip
        else:
          logger.error("No mgmt and data ip found")
      else:
        mgmt_ip = self.grains[srv]['ip4_interfaces'][iface][0] 
        self.pr_silent("mgmt_ip : {}".format(mgmt_ip),info=True)
        self.add_csv(srv,'mgmt_ip',mgmt_ip)
    if self.sls:
      self.create_sls(localpillar,srv)

  def create_sls(self,dict,srv):
    outfile=self.slsdir+srv+".sls"
    try:
      f=open(outfile, 'w') 
    except:
      logger.error("Can't generate pillar, opening {} with error {}".format(outfile,sys.exc_info()[0]))
      return(9)
    self.pr_silent("generating pillar sls file {}".format(outfile),info=True)
    f.write("scality: \n")
    for i in dict.keys():
      line="  {}:{}".format(i,dict[i])
      self.pr_silent("{}".format(line),info=True) 
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
      logger.debug("Server : {}".format(i))
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

