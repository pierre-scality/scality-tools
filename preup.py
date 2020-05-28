#!/usr/bin/python

import os
import sys
from datetime import datetime
import argparse
import logging 
import textwrap

epilog = '''
Typical usage to have butter, cake and honey: 
# preup.py -pSs -e storage -E data_ip -d /root/

You'll get plateform file, selector values et all sls created in /root/
-e means you dont have role elastic already and then you use the selector storage server to set ES role
-E means you want to use the data_ip of those servers for ES ip

WARNING : the script will overwrite existing files.
'''


parser = argparse.ArgumentParser(description="Help to understand ring setting and create installation files  including pillar/csv",formatter_class=argparse.RawDescriptionHelpFormatter,epilog=textwrap.dedent(epilog))
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-D', '--dir', dest='dir', nargs=1, default=["/var/tmp"], help='Specify ouput directory for created files, default /var/tmp/')
parser.add_argument('-e', '--forcees', dest='forcees', nargs=1, help='If no role ELASTIC is found will duplicate this selector to create elastic selector')
parser.add_argument('-E', '--esip', dest='es_ip', nargs=1, choices=['data_ip','mgmt_ip'], default=["data_ip"], help='ES ip to use it can be data_ip or mgmt_ip, default data_ip (use with -e)')
#parser.add_argument('-I', '--info', dest='info', action="store_true", default=False ,help='print verbose server information')
parser.add_argument('-p', '--platform', dest='platform', action="store_true", default=False ,help='Generate plateform description file for hosts')
parser.add_argument('-q', '--quiet', dest='quiet', action="store_true", default=False ,help='Do not display general information on each host')
parser.add_argument('-s', '--sls', dest='sls', action="store_true", default=False ,help='Generate pillar.sls for hosts (in /var/tmp, see -D)')
parser.add_argument('-S', '--selector', dest='selector', action="store_true", default=False ,help='Build selector list for scality common pillar')
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target hosts, use all to loop on all minions')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Print verbose information on servers')
args, ukn = parser.parse_known_args()

logging.basicConfig(format='%(levelname)-8s : %(funcName)-20s: %(message)s',level=logging.INFO)
#logger = logging.getLogger()
logger = logging.getLogger(__name__)
#ch = logging.StreamHandler()
#ch.setLevel(logging.DEBUG)
#logger.addHandler(ch)


if args.debug==True:
  logger.setLevel(logging.DEBUG)
  logger.debug('Set debug mode')
  logger.debug(args)

if ukn != []:
  logger.error("Some params are not correct {0}".format(ukn))
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
    self.definition = { 'ROLE_CONN_CIFS' : 'smb', 'ROLE_ELASTIC' : 'elastic' , 'ROLE_STORE' : 'storage' , 'ROLE_ZK_NODE' : 'zookeeper' , 'ROLE_SVSD' : 'svsd' , 'ROLE_CONN_SOFS' : 'sofs' , 'ROLE_CONN_NFS' : 'nfs' , 'ROLE_CONN_CDMI' : 'cdmi', 'ROLE_SUP' : 'supervisor' , 'ROLE_HALO' : 'halo' , 'ROLE_CONN_SPROXYD' : 'sproxyd'}
    self.csvbanner=['data_ip', 'data_iface', 'mgmt_ip', 'mgmt_iface', 's3_ip', 's3_iface', 'svsd_ip', 'svsd_iface', 'ring_membership', 'role', 'minion_id', 'enclosure', 'site', '#cpu', 'cpu', 'ram', '#nic', 'nic_size', '#os_disk', 'os_disk_size', '#data_disk', 'data_disk_size', '#raid_card', 'raid_cache', 'raid_card_type', '#ssd', 'ssd_size', '#ssd_for_s3', 'ssd_for_s3_size']
    self.csvringbanner=["sizing_version","customer_name","#ring","data_ring_name","meta_ring_name","HALO API key","S3 endpoint","cos","arc-data","arc-coding"]
    self.virtualhost = ['VMware Virtual Platform','OpenStack Nova']
    self.target = args.target
    if self.target == None:
      self.target = ['all']
    self.grains = {} 
    self.get_grains_pillars()
    self.isnode = False
    self.sls = args.sls
    self.info = args.verbose
    self.outdir = args.dir[0]+"/"
    if os.access(self.outdir, os.W_OK) and os.path.isdir(self.outdir):        
        self.outdir=os.path.abspath(self.outdir)+"/" 
    else: 
        logger.error('Can not write on output dir : {0}'.format(self.outdir))
        exit(9)
    self.silent =  args.quiet
    self.platform =  args.platform
    self.csv = {}
    self.sup = None
    self.es_ip = args.es_ip[0]
    self.forcees = args.forcees
    # Hardcoded values for csv file build
    self.sizingversion=0.0
    self.nic_size=10
    # Used for store only
    self.raid_card_count=1
    self.raid_card_cache=4
    self.raid_card_type="DEFINE_RAID_CARD_HERE"
    # Hardcoded values for OS disk
    #os_disk;os_disk_size
    self.osdisk_count=1
    self.osdisk_size=50
 
  def get_grains_pillars(self):
    minionvers = {}
    if self.target[0] == 'all':
      logger.debug('Getting ALL grains and pillars')
      target='*'
    else:
      logger.debug('Getting grains and pillars for {0}'.format(self.target[0]))
      target=self.target[0]
    logger.info('Getting grains and pillars for all minions')
    self.grains=local.cmd(target,'grains.items')
    #self.pillar = local.cmd(target,'pillar.get',['scality'])
    self.pillar = local.cmd(target,'pillar.items')
    self.target = self.grains.keys()
    logger.debug('Final target list {0}'.format(self.target))
    for i in self.grains.keys():
      if self.grains[i]['saltversion'] not in minionvers.keys():
        minionvers[self.grains[i]['saltversion']]=[i]
      else:
        minionvers[self.grains[i]['saltversion']].append(i)
    if len(minionvers) != 1:
      tmp=""
      for i in minionvers.keys():
        tmp=tmp+str(i)+','
      logger.warning("Different version of salt running {0} [Use salt-run manage.versions for details]".format(tmp.rstrip(',')))
    return(0)

  def get_csv_role(self,roles):
    csvrole=[]
    for i in roles:
      if i not in self.definition:
        logger.debug('role {0} not in known roles'.format(i))
        continue
      else:
        csvrole.append(self.definition[i])
    return(csvrole) 


  def create_selector(self):
    outfile=self.outdir+"selector.sls"
    try:
      f=open(outfile, 'w')
    except:
      logger.error("Can't write selector file, opening {0} with error {1}".format(outfile,sys.exc_info()[0]))
      return(9)
    roles={}
    logger.debug('Getting roles from {0}'.format(self.grains.keys()))
    for srv in sorted(self.grains.keys()):
      if not 'roles' in self.grains[srv]:
        logger.warning("No roles for server {0}".format(srv))
        continue
      this = self.grains[srv]['roles']
      if isinstance(this, str):
        this = [this] 
      for role in this:
        if role not in self.definition:
          logger.debug('role {0} not in known'.format(role))
          continue
        else:
          role=self.definition[role]
        if not role in roles.keys():
          roles[role]='L@'+srv
        else:
          roles[role]=roles[role]+","+srv 
    f.write("  selector: \n")
    for i in roles:
      f.write("    {0}: {1}\n".format(i,roles[i]))
    if not 'elastic' in roles.keys():
      if self.forcees != None:
        logger.debug("elastic selector not found trying to force {0} {1}".format(self.forcees,roles.keys()))
        if self.forcees[0] in roles.keys():
          print "    {0}: {1}".format('elastic',roles[self.forcees[0]],info=True)
          f.write("    {0}: {1}\n".format('elastic',roles[self.forcees[0]]))
        else:
          logger.error("Can not set elastic role, selector {0} not found".format(self.forcees[0])) 
      else:
        logger.warning("can not create selector for elastic role")    
    logger.info("Create selector file : {0}".format(outfile))
    f.close()
    return(roles)

  def get_value(self,l,v,displ=False):
    if v in l.keys():
      if displ == True:
        self.pr_silent("{0} : {1}".format(v,l[v]))
      return(l[v])
    else:
      logger.debug("Value {0} not found".format(v))
      return(None)

  def set_target(self):
    if self.target != None:
      if self.target == all:
        self.target == self.grains.keys()
      elif self.target not in self.grains.keys():
        logger.error("server {0} is not in the list of minions: \n{1}".format(target,self.grains.keys()))
        exit(0)
    #print self.target
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
          logger.debug("Unexpected Value found {0}".format(this)) 
    return(hdd,ssd) 

  # count existing ifs with ip (may be redundant with grains before)
  def get_ip4_iface_count(self,grains):
    allifs=grains['ip4_interfaces'].keys()
    allifs.remove('lo')
    keep=[]
    for i in allifs:
      if grains['ip4_interfaces'][i] != []:
        keep.append(i)
    count=len(keep)
    logger.debug("Found {0} ip4 ifs {1} from {2}".format(count,keep,allifs))
    return(count)

  # Use a function to be able to fine tune search if needed
    allifs=grains['ip4_interfaces'].keys()
    allifs.remove('lo')
    count=len(allifs)
    logger.debug("Found {0} ip4 ifs".format(count))
    return(count)

  # simulate functin to get os disk values
  def set_csv_osdisk(self,srv):
    self.add_csv(srv,'#os_disk',self.osdisk_count)
    self.add_csv(srv,'os_disk_size',self.osdisk_size)

  def get_srv_info(self,srv):
    serverinfo=["id","productname","num_cpus","cpu_model","mem_total","os","osrelease","SSDs"]
    #hdd=["rot_count","rot_size"]
    #sdd=["ssd_count","ssd_size"]
    disable_proxy()
    outdump="/var/tmp/"+srv+".out"
    grains=self.grains[srv]
    mounted=local.cmd(srv,'disk.usage')[srv]
    try:
      fd=open(outdump,'w')
    except:
      logger.error("Can't open to write pillars {0} with error {1}".format(outdump,sys.exc_info()[0]))
      exit(9)
    fd.write(str(grains))
    fd.close()
    logger.debug("grains dump for {0} file : {1}".format(srv,outdump))
    if grains['os_family'] != "RedHat":
      logger.warning('WARNING : Support only RH family')
    dcount=0
    dlist=[]
    disks=self.get_value(grains,'disks')
    if disks != None:
      for this in disks:
        if this[0:3] == 'ram':
          continue
        if this[0:4] == 'loop':
          continue
        dcount+=1
        dlist.append(this)
      self.pr_silent("Raw disks list : {0}\nRaw disks count : {1} ".format(dlist,dcount),info=True)
    self.add_csv(srv,'minion_id',srv)
    self.add_csv(srv,'#cpu',self.grains[srv]['num_cpus'])
    self.add_csv(srv,'cpu',"\"{0}\"".format(self.grains[srv]['cpu_model']))
    if ['mem_physical'] in self.grains[srv].keys():
      self.add_csv(srv,'ram',str(self.grains[srv]['mem_physical']))
    elif 'mem_total' in self.grains[srv].keys():
      self.add_csv(srv,'ram',str(self.grains[srv]['mem_total']))
    else:
      self.add_csv(srv,'ram','UNKNOWRAM')

    self.add_csv(srv,'#nic',self.get_ip4_iface_count(self.grains[srv]))
    # Not doing NW speed to limit salt calls. Speed is not in the grains.
    self.add_csv(srv,'nic_size',self.nic_size)
    self.set_csv_osdisk(srv)
    
    if 'ROLE_STORE' in grains['roles']:
      self.add_csv(srv,'#raid_card',self.raid_card_count)
      self.add_csv(srv,'raid_cache',self.raid_card_cache)
      self.add_csv(srv,'raid_card_type',self.raid_card_type)
    enclosure=self.grains[srv]['productname']
    if enclosure in self.virtualhost:
      enclosure="VIRTUAL MACHINE"
    self.add_csv(srv,'enclosure',"\"{0}\"".format(enclosure))
    hd=self.analyse_disks(mounted)
    for this in  grains['ip4_interfaces'].keys():
      if this == 'lo':
        continue
      if grains['ip4_interfaces'][this] == []:
        if args.debug:
          print 'DEBUG : interface without ip v4'+this 
      else:
        self.pr_silent("{0} : {1}".format(this,grains['ip4_interfaces'][this][0]),info=True) 
    if 'roles' not in self.grains[srv]:
      logger.warning("Server {0} hasn\'t any roles grain".format(srv))
      return(1)
    if 'ROLE_STORE' in self.grains[srv]['roles']:
      logger.debug("Store server getting disk count")
      self.pr_silent("Scality hdd found : {0}".format(hd[0]),info=True) 
      self.pr_silent("Scality ssd found : {0}".format(hd[1]),info=True)
      if 'rot_count' in self.grains[srv]:
        self.add_csv(srv,'#data_disk',format(self.grains[srv]['rot_count']))
        if 'rot_size' in self.grains[srv]:
          self.add_csv(srv,'data_disk_size',format(self.grains[srv]['rot_size']/self.grains[srv]['rot_count']/(1024 * 1024 * 1024)))
        else:
          logger.debug("Server {0} has rot_count but no rot_size".format(srv))
      else:
        logger.debug("Server {0} has no rot_count".format(srv))
        self.add_csv(srv,'#data_disk',format(hd[0]))
      if 'ssd_count' in self.grains[srv]:
        self.add_csv(srv,'#ssd',format(self.grains[srv]['ssd_count']))
        if 'ssd_size' in self.grains[srv]:
          self.add_csv(srv,'ssd_size',format(self.grains[srv]['ssd_size']/self.grains[srv]['ssd_count']/(1024 * 1024 * 1024)))
        else:
          logger.debug("Server {0} has ssd_count but no ssd_size".format(srv))
      else:
        logger.debug("Server {0} has no ssd_count".format(srv))
        self.add_csv(srv,'#ssd',format(hd[1]))
      if not 'rings' in self.pillar[srv]['scality']:
        logger.warning("not rings found for store node {0}".format(srv))
      else:
        rings="\"{0}\"".format(self.pillar[srv]['scality']['rings'])
        self.pr_silent("Scality rings found : {0}".format(rings),info=True)
        self.add_csv(srv,'ring_membership',format(rings))
    roles=self.get_value(grains,'roles')
    csvroles=self.get_csv_role(roles)
    csvroles.sort()
    csvroles="\"{0}\"".format(','.join(csvroles))
    self.add_csv(srv,'role',csvroles)
    # This is the default output
    if not isinstance(roles, list): 
      roles=roles.split()
    strroles=''.join(","+e for e in roles)[1:]
    if 'ROLE_SUP' in roles:
      self.sup=srv
    logger.info("Server {0:<10} has roles : {1:<20}".format(srv,strroles))

  def get_if_info(self,srv):
    pillar=self.pillar[srv]['scality'] 
    localpillar={}
    if 'supervisor_ip' in pillar:
      self.pr_silent("supervisor_ip : {0}".format(pillar['supervisor_ip']),info=True)
      localpillar['supervisor_ip']=pillar['supervisor_ip']
    else:
      self.pr_silent("No supervisor ip defined")

    data_ip=""
    if 'data_ip' in pillar:
      self.pr_silent("data_ip : {0}".format(pillar['data_ip']),info=True)
      localpillar['data_ip']=pillar['data_ip']
      self.add_csv(srv,'data_ip',localpillar['data_ip'])
    elif 'data_iface' in pillar:
      iface=pillar['data_iface']
      logger.debug("iface {0} ".format(iface))
      if not iface in self.grains[srv]['ip4_interfaces']:
        logger.error("data_iface {0} is not present in grains {1}".format(iface,self.grains[srv]['ip4_interfaces']))
        for iface in self.grains[srv]['ip4_interfaces'].keys():
          if not self.grains[srv]['ip4_interfaces'][iface] == []:
            if self.grains[srv]['ip4_interfaces'][iface][0] != '127.0.0.1':
              logger.warning("Server {0} Using random local ip as no data ip/if grain found : chosen {1} ({2})".format(srv,self.grains[srv]['ip4_interfaces'][iface][0],iface))
              localpillar['data_ip']=self.grains[srv]['ip4_interfaces'][iface][0]
              self.add_csv(srv,'data_ip',localpillar['data_ip'])
              break
        #return(1)
      else:
        try:
          data_ip = self.grains[srv]['ip4_interfaces'][iface][0] 
        except:
          logger.error("Can not get data_ip with {} for server {}".format(iface,srv))
        localpillar['data_ip'] = data_ip
        self.add_csv(srv,'data_ip',localpillar['data_ip'])
        logger.debug("adding ip {0} ".format(data_ip))
  
    ## ugly code to manage mgmt_iface case need to rethink the algo 
    ## Do not add _iface in the csv file
    logger.debug("Checking mgmt_ip") 
    if 'mgmt_ip' in pillar:
      self.pr_silent("mgmt_ip : {0}".format(pillar['mgmt_ip']),info=True)
      localpillar['mgmt_ip']=pillar['mgmt_ip']
      self.add_csv(srv,'mgmt_ip',localpillar['mgmt_ip'])
    elif 'mgmt_iface' in pillar:
      iface=pillar['mgmt_iface']
      if not iface in self.grains[srv]['ip4_interfaces']:
        logger.error("Server {0} mgmt_iface {1} is not present in grains {2}".format(srv,iface,self.grains[srv]['ip4_interfaces']))
        if data_ip != "":
          logger.debug("Using data ip for mgmt ip as neither mgmt_ip/mgmt_iface usable")
          mgmt_ip=data_ip
          localpillar['mgmt_ip']=mgmt_ip
          self.add_csv(srv,'mgmt_ip',mgmt_ip)
        else:
          logger.warning("No mgmt and data ip found, forcing to : {0}".format(localpillar['data_ip']))
          mgmt_ip = localpillar['data_ip']
      else:
        try:
          mgmt_ip = self.grains[srv]['ip4_interfaces'][iface][0] 
        except:
          logger.error("Can not get mgmt_ip with {} for server {}".format(iface,srv))
        localpillar['mgmt_ip']=mgmt_ip
        self.add_csv(srv,'mgmt_ip',localpillar['mgmt_ip'])
    else:
      mgmt_ip = self.grains[srv]['ip4_interfaces'][iface][0] 
      self.pr_silent("mgmt_ip : {0}".format(mgmt_ip),info=True)
      localpillar['mgmt_ip']=mgmt_ip
      self.add_csv(srv,'mgmt_ip',localpillar['mgmt_ip'])
    if 'zone' in pillar:
      localpillar['zone'] = pillar['zone']
    else:
      localpillar['zone'] = 'site1'
    self.add_csv(srv,'site',localpillar['zone'])
    if self.sls:
      if self.forcees != None:
        logger.debug("Try to force ES if proper role")
        for role in self.definition:
          if role in self.grains[srv]['roles']:
            if self.definition[role] == self.forcees[0]:
              logger.debug("{0} has role {1} ({2}) and match {3},using elasticsearch ip: {4}".format(srv,role,self.definition[role],self.forcees[0],self.es_ip))
              localpillar['elasticsearch']=localpillar[self.es_ip]
      self.create_sls(localpillar,srv)

  def create_sls(self,dict,srv):
    if srv.count('.') != 0:
      filename=srv.split('.')[0]
      outfile=self.outdir+filename+".sls"
      logger.warning("Server {0} has . in the name, using short name for pillar file : {1}".format(srv,filename))
    else:
      outfile=self.outdir+srv+".sls"
    try:
      f=open(outfile, 'w') 
    except:
      logger.error("Can't generate pillar, opening {0} with error {1}".format(outfile,sys.exc_info()[0]))
      return(9)
    #self.pr_silent("generating pillar sls file {0}".format(outfile),info=True)
    logger.info("generating pillar sls file {0}".format(outfile))
    if 'elasticsearch' in dict.keys():
      f.write("elasticsearch: \n")
      f.write("  net_ip: {0}\n".format(dict['elasticsearch']))
      dict.pop('elasticsearch')
    f.write("scality: \n")
    localindex=dict.keys()
    localindex.sort()
    for i in localindex:
      line="  {0}: {1}".format(i,dict[i])
      self.pr_silent("{0}".format(line),info=True) 
      f.write(str(line)+"\n")
    if 'ROLE_ELASTIC' in self.grains[srv]['roles']:
      logger.debug("Creating ES entry in pillar")
      if self.es_ip in dict.keys():
        line="{0}:\n  net_ip: {1}\n".format('elasticsearch',dict['data_ip'])
        f.write(str(line)+"\n")
      else:
        logger.warning("Cannot create elasticsearch entry as data_ip is not know")
    else:
      logger.debug("srv {0} not role ROLE_ELASTIC".format(srv))
    f.close()

  def create_top_sls(self):
    outfile=self.outdir+'top'+".sls"
    try:
      f=open(outfile, 'w') 
    except:
      logger.error("Can't generate pillar, opening {0} with error {1}".format(outfile,sys.exc_info()[0]))
      return(9)
    logger.info("Create top sls file : {0}".format(outfile))
    f.write("base:\n  '*':\n    - scality-common\n    - order: 1\n")
    for i in sorted(self.grains.keys()):
      if i.count('.') != 0:
        filename=i.split('.')[0]
      else:
        filename=i
      logger.debug("Adding {0} to top file".format(i))
      line="  '{0}':\n    - match: compound\n    - {1}\n    - order: 2".format(i,filename)
      f.write(str(line)+"\n")

  def add_csv(self,host,p,v):
    if not host in self.csv.keys():
      self.csv[host] = {}
      for field in self.csvbanner:
        self.csv[host].update({field:''})
    self.csv[host].update({p:v})

  # get the pillar and return list "DATA,MD"
  # if unable return more or less random
  def guess_meta_ring(self,rings):
    found=None
    for i in rings:
      if self.pillar[self.sup]['scality']['ring_details'][i]['is_ssd'] == True:
        found=i
        break
    logger.debug("MD ring found > {0} < if any".format(found)) 
    return(found) 

  """ sizing_version,customer_name;#ring;data_ring_name;meta_ring_name;HALO API key;S3 endpoint;cos;arc-data;arc-coding"""
  def create_csvtop(self):
    logger.debug("create_csvtop : build csv's rings line")
    csvtopvalue={}
    csvtopvalue['arc-data'] = None
    csvtopvalue['arc-coding'] = None
    for i in self.grains.keys():
      ## Assume that rings is in the pillar or die ... and in order data,meta
      rings=self.pillar[self.sup]['scality']['rings'].split(",")
      csvtopvalue['#ring']=len(rings)
      if len(rings) == 1:
        csvtopvalue['data_ring_name']=rings[0]
        csvtopvalue['meta_ring_name']=None
      elif len(rings) >= 2:
        md=self.guess_meta_ring(rings)
        if md != None:
          csvtopvalue['meta_ring_name']=md
          rings.remove(md)
          csvtopvalue['data_ring_name']=rings[0]
        else:
          csvtopvalue['meta_ring_name']=rings[1]
          csvtopvalue['data_ring_name']=rings[0]
      allcos=self.pillar[self.sup]['scality']['ring_details'][csvtopvalue['data_ring_name']]['redundancy']['cos']
      maxcos=0
      for i in allcos:
        if i[0:3] == 'ARC':
          csvtopvalue['arc-data'] = i[3:].split('+')[0]
          csvtopvalue['arc-coding'] = i[3][3:].split('+')[1]
        else:
          if i > maxcos:
            maxcos=i
      csvtopvalue['cos'] = maxcos
      csvtopvalue['sizing_version']=self.sizingversion
      csvtopvalue['customer_name']='INSERT_CUSTOMER_NAME_HERE'
      csvtopvalue['HALO API key']='INSERT_HALO_KEY_HERE'
      csvtopvalue['S3 endpoint']='INSERT S3 ENDPOINT'
    logger.debug("create_csvtop : found {0}".format(csvtopvalue))
    return(csvtopvalue)

  def create_csv(self):
    outfile=self.outdir+"plateform.csv"
    logger.info("Create csv file : {0}".format(outfile))
    line=""
    ##### sizing_version;customer_name;#ring;data_ring_name;meta_ring_name;HALO API key;S3 endpoint;cos;arc-data;arc-coding;;;;;;;;;;;;;;;;;;;
    ##### 17,5;<CUSTOMERNAME>;2;DATA;META;;s3.mediahubaustralia.com.au;3;7;5;;;;;;;;;;;;;;;;;;;
    csvtopvalue=self.create_csvtop()
    try:
      f=open(outfile, 'w') 
    except:
      logger.error("Can't generate plateform file, opening {0} with error {1}".format(outfile,sys.exc_info()[0]))
      return(9)
    f.write("ring ;;;;;;;;;;;;;;;;;;;;;;;;;;;;\n")
    for i in self.csvringbanner:
      line=line+str(i)+";"
    line.strip(';')
    line=line+"\n"
    f.write(line)
    line=""
    for i in self.csvringbanner:
      line=line+str(csvtopvalue[str(i)])+";"
    line.strip(';')
    f.write(str(line)+"\n")
    f.write(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;\n")
    f.write("servers ;;;;;;;;;;;;;;;;;;;;;;;;;;;;\n")
    line=""
    for i in self.csvbanner:
      line=line+str(i)+";"
    line.strip(';')
    f.write(str(line)+"\n")
    for i in self.csv.keys():
      line=""
      for j in self.csvbanner:
        line=line+str(self.csv[i][j])+";"
      line.strip(';')
      f.write(str(line)+"\n")
    f.close()

  def pr_silent(self,msg,info=False):
    if self.silent == False: 
      if info == False:
        print msg
      if info == True and self.info == True:
        print msg

  def mainloop(self):
    logger.debug("Main loop with args {0}".format(args))
    for i in self.target:
      logger.debug("Server : {0}".format(i))
      self.get_srv_info(i)
      self.get_if_info(i)
    if self.platform == True:
      self.create_csv() 
    if args.selector == True:
      self.create_selector()   
    if self.sls == True: 
      self.create_top_sls()
    exit(0)

def main():
  l=[]
  R=MyRing(args)
  logger.debug("Checking target {0}".format(args.target))
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

