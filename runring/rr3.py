#!/usr/bin/python3
 # -*- coding: utf-8 -*-

import sys
import os
import time
import getopt
import logging 
import yaml 
import subprocess
import re
import signal
import json

 
sys.path.insert(0,'/usr/local/scality-ringsh/ringsh/modules')
#from argparse import ArgumentParser
import argparse
from scality.supervisor import Supervisor
from scality.node import Node
from scality.daemon import DaemonFactory , ScalFactoryExceptionTypeNotFound
from scality.common import ScalDaemonException

def sighandler(signum, frame):
        print('Graceful exit')
        exit(0)

signal.signal(signal.SIGINT, sighandler)


PRGNAME=os.path.basename(sys.argv[0])
keylist=[]
cli=[]
option={}
sup ='https://127.0.0.1:2443'
dummy=[]
file=None
ringyaml="/etc/scality-supervisor/confv2.yaml"

#logging.basicConfig(format='%(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
logger = logging.getLogger()

try:
  RING=os.environ['RING']
except KeyError:
  RING='DATA'

SPECIAL=('compare')
CONN=('rest','rs2','connector','conn','accessor','r')
NODE=('node','n')
RINGOP_W=('set','run','logset','list','maint')
RINGOP_R=('get','status','heal','logget','run','joinall','server','storage')
RINGOPS=RINGOP_W+RINGOP_R
NODEOP_W=('set','logset')
NODEOP_R=('get','logget','cat','list','comp','compare','stat','disk','status')
NODEOPS=NODEOP_W+NODEOP_R
CONNOP_W=('set','logset')
CONNOP_R=('get','logget','cat','list')
CONNOPS=CONNOP_W+CONNOP_R
SELF_HEALING=('rebuild_auto','chordpurge_enable','join_auto','chordproxy_enable','chordrepair_enable','chordcsd_enable')
RING_MAINTENANCE_OFF={'rebuild_auto':'1','chordpurge_enable':'1','join_auto':'2'}
RING_MAINTENANCE_ON={'rebuild_auto':'0','chordpurge_enable':'0','join_auto':'0'}
RING_MAINTENANCE=('on','off')

RUN_EXEC=False
RUN_LOG=False
STRIPOUT=['Load','Use','Adding','Done']
PYSCAL=('py','python','pyscal','pyscality')
PARAMFILE=None
try:
  CREDFILE=os.environ['RRFILE']
except:
  CREDFILE="/tmp/scality-installer-credentials"
login="root"
password="admin"

parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description='''
Run ringsh commands on single or several target
The first parameter is the component and can be ring, node or rs2 (or connector) then the command.
Basic options are get/get/list  and for log config  logset/logget 
The set command by default do not run command but display what is should run, add the -f flag to execute the command

Sample commands :
rr.py node get            ==> Will display all nodes parameter on a single random node
rr.py node get timeout    ==> a parameter can be added to limit output on this string
rr.py rs2 get             ==> Will display all rs2 connector  parameter on a single random (accept rs2/res/accessor/conn/connector keyword)
rr.py ring get rebuild    ==> will display ring parameter matching rebuild
For set when parameter has a space use \ like ov_protocol_netscript "socket\ timeout" 15
rr.py node set ov_protocol_netscript  "socket\ timeout" 15

Targeting :
By default it runs on a single node/connector needs -a to iterate on all of them
To select a specific server or set of server use -s <string> it will match (only string no re) target component
if neither -a or -s are given it will take the first component available
To select a ring use -r (if nothing specified it will use DATA, if a en variable RING is found it will use it) 

Sample commands :
rr.py -R -s node6-n3 node get chordpurgetombstonetimer                 => will display chordpurgetombstonetimer param on all rings for nodes matching "node6-n3"
rr.py -fa node set msgstore_protocol_chord chordhttpdmaxsessions 4000  => it will set chordhttpdmaxsessions to all nodes (for 1st ring), use -R to do on all rings

Other options:
  ring
    * ring status 
    ring status [long | full ] : gives ringStatus with just general status or all but Disk with long param and all with full
    ring status xxx where xxx is neither long or full will grep the string out of the ringStatus output

    * ring server
    show ring server list, you can match a string with "ring server something" => will match lines with "something"

    * ring joinall
    join all the nodes of a given ring

    * ring maint [on|off] [noforce]
    Without arg will show rebuild/purge/join ring params. With :
      - on  -> rebuild/purge/join to 0  
      - off -> rebuild/purge/join to 1/1/2 (2 for auto_join).  For off noforce option will set auto_join to 1 instead of 2.

    * ring heal
    Set healthealing main parameters

    * ring help
    show the basic heal healing params (auto join, auto rebuild ...)

  node
   * statistics
   node stat [param]
   Node statistics (dumpstat) without arg list all stats
   With 1 parameter do an exact match of the path

   * disk 
   run diskConfigGet for the target

   * compare mode (node only for now)
   -c <param file> node compare
   You can compare node parameters based on a text file (with -c parameter file) 
   with format module:parameter as below (unlimited number of lines) as :
   msgstore_protocol_chord:chordhttpdmaxsessions

   It will output for this parameters the number of nodes having different values  :
   msgstore_protocol_chord chordhttpdmaxsessions 2000 1
   msgstore_protocol_chord chordhttpdmaxsessions 2500 6
   msgstore_protocol_chord chordhttpdmaxsessions 3000 29

   if --diff option is set and values are defined in compare file it will display the nodes where values are different with output like :
   2018-02-13 16:16:27,359 : INFO : ring_op_compare: Not matching value 100 :  DATA-node02-n1 msgstore_protocol_chord chordpurgetombstoneexpirationtime 3600
   2018-02-13 16:16:27,359 : INFO : ring_op_compare: Not matching value 100 :  DATA-node03-n1 msgstore_protocol_chord chordpurgetombstoneexpirationtime 3600


   If you want then to check with node has different parameter you have to use :
   rr.py -a node get msgstore_protocol_chord chordhttpdmaxsessions 2500 
   It will return all nodes having this parameter

Authentication:
  Default is to check /tmp/scality-installer-credential file or use -l/-p login/password 
''') 

parser.add_argument('-a', '--all', help='Loop on all servers', action="store_true", default=False)
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
#parser.add_argument('-D', '--debuglevel', nargs=1, help='Choose debug level see https://docs.python.org/2/library/logging.html')
parser.add_argument('-f', '--force', action="store_true", help='force execution on set commands', default=RUN_EXEC)
parser.add_argument('-l', '--login', nargs='?', help='login', const=login)
parser.add_argument('-L', '--logall', action="store_true", help='logall', default=RUN_LOG)
parser.add_argument('-p', '--password', nargs='?', help='password', const=password)
parser.add_argument('-r', '--ring-name', nargs='?', help='ring name default is DATA', const='DATA', default=RING)
parser.add_argument('-R', '--all-rings', help='Loop on all rings', action="store_true", default=False)
parser.add_argument('-s', '--server-name', nargs=1, help='run on a single defined node')
#parser.add_argument('-u', '--use-name', nargs=1, help='run as -u ringsh option')
parser.add_argument('-m', '--method', nargs='?', help='Switch internal code to ringsh or pyscality',default='ringsh')
parser.add_argument('-c', '--compfile', nargs='?', help='List of parameters to be compared',default=PARAMFILE)
parser.add_argument('-z','--diff', action="store_true", help='apply component with differnt value for node/rs2 params',default=False)


args,cli=parser.parse_known_args()
if args.debug==True:
  logger.setLevel(logging.DEBUG)

class ring_obj():
  def __init__(self,login,password,ring,comp="None",url="https://127.0.0.1:2443",target=None):
   logger.debug("Initialisation object ring : "+str(comp))
   self.ring=ring
   self.node=""
   self.nodes={}
   self.rs2={}
   self.rs2names={}
   self.rs2status={}
   self.names={}
   self.nodestatus={}
   self.comp=comp
   self.sup = Supervisor(url=url,login=login,passwd=password)
   self.status = self.sup.supervisorConfigDso(action="view", dsoname=self.ring)
   if self.comp == 'node':
     logger.info('Getting node configuration ring {0}'.format(self.ring))
     ###BAD logger.debug('target are {0}'.format(target))
     for n in self.status['nodes']:
       nid = '%s:%s' % (n['ip'], n['chordport'])
       self.nodes[nid] = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=self.ring, login=login, passwd=password)
       if n['name'] in target or target == None:
        self.names[nid]=n['name']
       else:
        logger.debug("Ignoring node {0} not in target".format(n['name']))
        self.nodes.pop(nid)
        continue
       logger.debug("Merging node {0} configuration".format(n['name']))
       try:
         self.nodestatus[nid]=self.nodes[nid].nodeGetStatus()[0]
       except ScalDaemonException:
         print("ERROR accessing node %s" % n['name'])
       if not self.node: self.node = self.nodes[nid]
   elif self.comp == 'accessor': 
     logger.info('Getting rs2 configuration ring {0}'.format(self.ring))
     r = self.sup.supervisorConfigBizstore(action="view", dso_filter=ring)
     for i in r['restconnectors']:
       rid = '%s:%s' % (i['adminaddress'], i['adminport'])
       self.rs2[rid]=DaemonFactory().get_daemon("restconnector", url='https://{0}:{1}'.format(i['adminaddress'], i['adminport']), login=login, passwd=password)
       if i['name'] in target or target == None:
         self.names[rid]=i['name']
       else:
         logger.debug("Ignoring rs2 {0} not in target".format(i['name']))
         self.rs2.pop(rid)
         continue
       try:
         self.rs2status[rid]=self.rs2[rid].configViewModule()
       except ScalDaemonException:
         logger.error("Cant get configuration from ".format(i['name']))
   else: 
     raise NotImplementedError

  def obj_list(self,param):
    logger.debug("Building list for : "+str(self.comp)+','+param)
    if self.comp == 'supervisor':
      for i in list(self.sup.supervisorConfigMain().keys()):
        print(i, end=' ')
      return(0)
    if self.comp in CONN:
      dict=self.rnames
    elif self.comp in NODE:
      dict=self.names
    else:
      logger.error("type not valid "+what)
      exit(9) 
    if param == 'all':
      for i in dict:
        print(dict[i],i)
    elif param == 'name':
      for i in list(dict.keys()):
        print(dict[i])
    elif param == 'address':
      for i in dict: print(dict[i])
    return(0)

  def ip_to_n(self,name):
    if name in list(self.names.keys()): 
      return(self.names[name])
    else:
      return None

  def n_to_ip(self,name='ALL'):
    out={}
    for i in list(self.names.keys()):
      if name == 'ALL':
        out[self.names[i]]=i
      elif self.names[i] == name: 
        return(i)
    return(out)

  def obj_config_struct(self):
    struct={}
    if self.comp == "node":
      for this in list(self.nodes.keys()):
       logging.debug("Getting conf of {0}".format(this))
       if this not in list(struct.keys()):
         struct[this]={}
       struct[this]=self.nodes[this].configViewModule()
    elif self.comp == "accessor":
      for this in list(self.rs2.keys()):
       logging.debug("Getting conf of {0}".format(this))
       if this not in list(struct.keys()):
         struct[this]={}
       struct[this]=self.rs2[this].configViewModule()
    return(struct)  

class ring_op():
  def __init__(self,arg,cli,server_name=None):
    if len(cli) < 2:
      logging.error("Need at least type and commands")
      exit(9)
    self.cli=cli
    self.comp=cli[0] # obj ad ring/node...
    self.op=cli[1] # operation ad get/put
    self.param=cli[2:] # remaining options
    self.login=arg.login
    self.password=arg.password
    self.ring=arg.ring_name
    self.run_exec=arg.force
    self.run_log=arg.logall
    self.server_list=[]
    self.ring_list=[]
    self.compfile=arg.compfile
    self.diff=arg.diff
    self.all_rings=arg.all_rings
    if arg.method not in PYSCAL:
      self.method='ringsh'
    else:
      self.method='pyscal'
    if arg.all == True:
      self.target="ALL"
    # use name and server name are not compatible. Using name
    elif arg.server_name is not None:
      self.target=arg.server_name
    else:
      self.target="ANY"
    self.ring_auth()
    logger.debug("List of params :: "+str(self.param))

  def ring_auth(self):
    if self.login == None or self.password == None:
      try:
        d=open(CREDFILE,'r')
        cred=json.load(d)
        logger.debug("Open {0} file".format(CREDFILE))
        if self.login == None:
          self.login=cred['internal-management-requests']['username']
        if self.password == None:
          self.password=cred['internal-management-requests']['password']
        d.close()
      except IOError:
        logger.debug("Can't open {0} file".format(CREDFILE))
        if self.login == None:
          self.login=login
        if self.password == None:
          self.password=password
    logger.debug("Values {0} {1}".format(self.login, self.password))


  def show_args(self):
    command=""
    for i in self.cli:
      command=command+i+" "
    print(self.ring,command)

  """ Function to loop on all targeted rings"""
  def exec_per_ring(self):
    logger.debug("Building ring target list :: "+str(self.target)+','+self.grep)
    if self.all_rings:
      cmd="ringsh supervisor ringList" 
      output=self.execute(cmd)
      for line in output:
        self.ring_list.append(line)
    else:
      self.ring_list.append(self.ring)
    for ring in self.ring_list:
      self.ring=ring
      self.get_target()
      logger.debug("Final target list :: "+format(self.server_list))
      self.pass_cmd()
      print()

  """ function to set the target servers in server_list class var"""
  def get_target(self):
    logger.debug("Building target list :: "+str(self.target)+','+self.grep+','+self.ring)
    self.server_list=[]
    if self.method in ("ringsh",'pyscal') :
      grep=self.grep+':'
      cmd="ringsh -r "+self.ring+" supervisor ringStatus "+self.ring+"| grep "+grep 
      output=self.execute(cmd)
      for line in output:
        current=line.split(" ")[1].rstrip(',')
        if self.target  == "ALL":
          self.server_list.append(current)
          continue
        elif self.target == "ANY":
          self.server_list.append(current)
          return
        else: 
          """ Do a regexp to avoid missing not standard component name """
          #logger.debug("Checking server to list "+current+" "+self.target[0])
          target_list=self.target[0].split(',')
          logger.debug("building list from {0} with {1}".format(target_list,current))
          for sub in target_list:
              regex=".*"+re.escape(sub)+".*" 
              rule=re.compile(regex)
              if rule.match(current):
                logger.debug("Adding server to list "+current)
                self.server_list.append(current)
        
    if self.server_list == []:
      logging.warning('Cannot find any target')
      exit(2)


  """ function to define various informations to build commands
      comp define either ring, node or accessor 
      sub is the ringsh command to run 
      grep the parameter to grep in ringStatus command to build the target list
  """
  def sort_op(self):
    if self.comp=="ring":
      self.sub="supervisor"
      self.comp="supervisor"
      # Doesn't really make sens for supervisor but fill up something
      self.grep="State"
    elif self.comp in CONN:
      self.sub="accessor"
      self.comp="accessor"
      self.grep="Connector"
    elif self.comp in NODE:
      self.comp="node"
      self.sub="node"
      self.grep="Node"
    else:
      logger.info("Invalid command "+self.comp)
      exit(1)
    ##self.get_target()
     
  """" Check valid parameter and pass to ring command """ 
  def pass_cmd(self):
    if self.op == "compare":
      self.ring_op_compare()
      return(0)
    if self.op == 'list': 
      self.ring_op_list()
      return(0)
    if self.op in ('logget','logset'):
      self.ring_op_log()
      return(0) 
    if self.sub=="supervisor":
      if self.op in RINGOP_R:
        self.ring_op_get()
      elif self.op in RINGOP_W:
        self.ring_op_set()
      else:
        logger.error("ring command must be in "+str(RINGOPS)) 
        exit(9)
      return(0)
    if self.sub=="node":
      if self.op in NODEOP_W:
        self.ring_op_set()
      elif self.op in NODEOP_R:
        self.ring_op_get()
      else:
        logger.info("node command must be in "+str(NODEOPS))
        exit(9)
    elif self.sub=="accessor":
      if self.op in CONNOP_R:
        self.ring_op_get()
      elif self.op in CONNOP_W:
        self.ring_op_set()
      else:
        logger.error("accessor command must be in "+str(CONNOPS))
        exit(9)
    else:
      logger.info("Unknow command "+self.sub)
      raise ValueError("Command not valid")
      exit(9)
    return(self.op)

  # params label=None,field=0,exact=False,raw=0 are to pass to ifre_print
  def exec_print(self,cmd,rs=False,quit=False,label=None,field=0,exact=False,raw=0):
    logger.debug("exec_print {0}".format(str(cmd)))
    output=self.execute(cmd)
    for line in output:
      if not line:
        continue
      if rs == True:
        line=line.rstrip()
      self.ifre_print(line,label,field,exact,raw)
    if quit == True:
      exit(0)
    return(0)

  def ifre_print(self,line,label=None,field=0,exact=False,raw=0):
    if len(self.param) == 0 or raw == 1:
      if label == None:
        print(line)
      else:
        print(label+ ": "+line)
      return(0)
    elif len(self.param) == 1 or self.comp == 'supervisor' or self.op == 'logset' or self.op == 'logget':
      """ to search when having module parameter """
      # too verbose logger.debug("ifreprint {0}".format(str(self.param)))
      pattern=self.param[field]
      if exact:
        regex=".*"+re.escape(pattern)+"\W.*"
      else:
        regex=".*"+re.escape(pattern)+".*"
      rule=re.compile(regex)
      if rule.match(line):
        if label == None:
          print(line) 
        else:
          print(label+" : "+line)
      return(0)
    if len(self.param) > 1:
      logger.debug("doing exact match {0} step 1".format(str(self.param)))
      z={}
      for j in line.split(', '):
        try:
          z[j.split(':')[0].strip()]=j.split(':',1)[1].strip()
        except IndexError as e:
          logger.debug("Cant process output {0} : probably unexpected char or comma in {1} ".format(e,j))
          continue
      if z['Name'] != self.param[1]:
        #logger.debug('Ignoring value 1 '+z['Name']+' not equal to '+self.param[1])
        return(0)
      if z['Name'] == self.param[1]:
        if len(self.param) == 3:
          if z['Value'] != self.param[2] and self.diff == False :
            logger.debug('Ignoring value 2 '+z['Value']+' not equal to '+self.param[2])
            return(0)
          elif z['Value'] == self.param[2] and self.diff == True:
            logger.debug('Ignoring value 2 '+z['Value']+' negative match '+self.param[2])
            return(0)
      if label == None:
        print(line)
      else:
        print(label+ ": "+line)
    return(0)

  def ring_op_list(self):
    if self.comp not in ('accessor','node','supervisor'):
      logger.error("can only list accessor,supervisor and node")
      exit(9)
    if self.method == 'pyscal':
      instance=ring_obj(self.login,self.password,self.ring,self.comp)
      instance.obj_list('all')
      return(0)
    else: 
      if self.comp == 'supervisor':
        cmd="ringsh -r "+self.ring+" supervisor ringList"
      else:
        cmd="ringsh -r "+self.ring+" supervisor ringStatus "+self.ring+" | grep "+self.grep+": | awk '{print $2}'"
      logging.debug("Listing ".format(cmd))
      self.exec_print(cmd,rs=1)
    return(0)

  def ring_op_get(self):
    logging.debug("Entering function ring_op_get {0} {1}".format(str(self.comp),str(self.op)))
    if self.comp  == 'supervisor': 
      if self.op == 'status':
        if len(self.param) > 0 and self.param[0] == 'long':
          cmd="ringsh -r "+self.ring+" "+self.sub+" ringStatus "+self.ring+"| grep -v '^Disk'"
        elif len(self.param) > 0 and self.param[0] == 'full':
          cmd="ringsh -r "+self.ring+" "+self.sub+" ringStatus "+self.ring
        elif len(self.param) > 0:
          cmd="ringsh -r "+self.ring+" "+self.sub+" ringStatus "+self.ring+" |grep "+self.param[0]
        else:
          cmd="ringsh -r "+self.ring+" "+self.sub+" ringStatus "+self.ring+"| egrep -vE '(^Disk:|^Node:|^Connector:)'" 
        self.exec_print(cmd,raw=1)
      elif self.op == 'joinall':
        cmd="ringsh -r "+self.ring+" "+self.sub+" nodeJoinAll "+self.ring
        self.exec_print(cmd,rs=True)
      elif self.op == 'storage':
        cmd="ringsh -r "+self.ring+" "+self.sub+" ringStorage "+self.ring
        self.exec_print(cmd,rs=True)
      elif self.op in ('heal','get'):
        cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigGet "+self.ring+" | grep -v Load"
        output=self.execute(cmd)
        for line in output:
          if not line:
            continue
          cat=line.split()[3].rstrip(',')
          if self.op == 'heal' :
            if cat in SELF_HEALING:
              print(line.rstrip())
          else:
            logging.debug("Displaying result sorting in : "+str(self.param))
            self.ifre_print(line.rstrip())
      elif self.op == 'server':
        cmd="ringsh -r "+self.ring+" "+self.sub+" serverList | grep -v Load"
        self.exec_print(cmd)
    elif self.comp in ('accessor','node') :
      if self.op == 'cat':
        cmd="ringsh -r "+self.ring+" -u "+self.server_list[0]+" "+self.sub+" configGet "
        output=self.execute(cmd)
        done=[]
        for line in output:
          if not line:
            continue
          module=line.split()[1].rstrip(',')
          if module not in done:
            self.ifre_print(module)
            done.append(module)
        return(0)
      """ We are in a configGet/exec """
      logging.debug("Entering configet/exec module :: {0}".format(self.sub))
      field=0
      for i in self.server_list :
        """ if param[0] is set we do a regex with ifre_print """
        if self.op == 'stat':
          if len(self.param) == 0: 
            cmd="ringsh -r {0} -u {1} {2} dumpStats".format(self.ring,i,self.sub)
            self.exec_print(cmd,label=i)
          else:
            cmd="ringsh -r {0} -u {1} {2} dumpStats {3}".format(self.ring,i,self.sub,self.param[0]) 
            self.exec_print(cmd,rs=True,label=i,exact=1)
          continue
        if self.op == 'status':
          cmd="ringsh -r {0} -u {1} node showStatus".format(self.ring,i)
          if len(self.param) > 0:
            cmd=cmd+" | grep "+str(self.param)
          self.exec_print(cmd,label=i)
          continue
        if self.op == 'disk':
          if self.sub != "node":
           print("Argument error disk is only available for node")
           exit(9)
          cmd="ringsh -r {0} -u {1} {2} {3}".format(self.ring,i,self.sub,"diskConfigGet")
          logging.debug("run command :: "+self.sub+" : "+cmd)
          self.exec_print(cmd,label=i,rs=True,raw=1)
          continue 
        if len(self.param) <=2:
          cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configGet"
          logging.debug("run command : 1 param : "+self.sub+" : "+cmd)
          self.exec_print(cmd,label=i,rs=True)
        else:
          logger.error("too many args"+str(self.param))
          exit(2)
          #continue
        """ To search module : param we check if we had more than 1 param on input and set field to 1 to pass to print command"""
        """ This is exact match """
        """ param is ['module','name','value']  """
        #cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configGet "+self.param[0]
        #output=self.execute(cmd)
        #print str(len(self.param)),str(self.param)
        #for line in output:
        #  self.ifre_print(line.rstrip(),i)
    return(0)


  def ring_op_set(self):
    logging.debug("Entering function ring_op_set {0} {1}".format(str(self.comp),str(self.op)))
    if self.comp  == 'supervisor':
      if self.op == "maint":
        if self.param == []:
          self.param.append('show')
        self.ring_maint()
      else:
        cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigSet "+self.ring+" "+self.param[0]+" "+self.param[1]
        if self.run_exec == False:
          print("NOEXEC "+str(cmd))
        else:
          logging.debug("Running : "+cmd)
          output=self.execute(cmd)
          for line in output:
            if not line:
              continue
            elif line.split()[0] == "Load":
              continue
            print(line.rstrip())
    elif self.comp in ('node','accessor'):
      for i in self.server_list :
        if len(self.param)< 3:  
          logging.info('Missing arguments to set Module:Name:Value ')
          exit(5)
        if ' ' in self.param[1]:
          self.param[1]=self.param[1].replace(" ","\ ")
        cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configSet "+self.param[0]+" "+self.param[1]+" "+self.param[2]
        if self.run_exec == False:
          print("NOEXEC "+str(cmd)) 
          continue
        logging.debug("run command "+self.sub+" : "+cmd)
        output=self.execute(cmd)
        for line in output:
          self.ifre_print(line.rstrip(),i,raw=1)
    else:
      logging.info("Component not implemented ".format(self.comp))
      exit(9)

  def open_compare_file(self):
    source={}
    linenb=0
    if not self.compfile:
      logger.error("compfile is not set")
      exit(9)
    try:
      f = open(self.compfile,'r')
    except IOError as e:
      logger.error("File error({0}): {1} : {2}".format(e.errno, e.strerror,self.compfile))
      exit(9)
    for line in f:
      if line.count(':') == 0:
        logger.debug('Ignoring wrong format line : '+str(linenb))
        continue
      module=line.split(':')[0].rstrip() 
      param=line.split(':')[1].rstrip() 
      refvalue=None
      if line.count(':') == 2:
        refvalue=line.split(':')[2].rstrip()
        logger.debug('{0} {1} value to verify {2}:'.format(module,param,refvalue))
      if not module in list(source.keys()):
        source[module]={}
      if not param in list(source[module].keys()):
        source[module][param]=refvalue
      linenb+=1
    logger.debug('file parsed nb lines '+str(linenb))
    return(source)

  def ring_op_compare(self):
    logger.debug('Entering func ring_op_compare with comp file "{0}"'.format(self.compfile))
    source={}
    result={}
    source=self.open_compare_file()
    instance=ring_obj(self.login,self.password,self.ring,self.comp,target=self.server_list)
    objstruct=instance.obj_config_struct() 
    for server in self.server_list:
      logger.debug('Computing comparison on : '+str(server))
      this=instance.n_to_ip(server)
      for module in list(source.keys()):
        for param in list(source[module].keys()):
          try:
            value=objstruct[this][module][param]['value']
          except KeyError as e:
            logger.info("No such key "+module+" , "+param)
            continue
          index=str(module)+":"+str(param)+":"+str(value) 
          if source[module][param] != value and self.diff == True and source[module][param] != None:
            logger.info("Not matching value {4} :  {0} {1} {2} {3}".format(server,module,param,value,source[module][param]))
          else:
            logger.debug("Matching value {4} :  {0} {1} {2} {3}".format(server,module,param,value,source[module][param]))

          if index not in list(result.keys()):
            result[index]=[this]
          else:
            if this not in result[index]:
              result[index].append(this)
    fmt=[0,0,0]
    for i in list(result.keys()):
      k=i.split(':')
      for j in [0,1,2]: 
        if fmt[j] < len(k[j]):
          fmt[j]= len(k[j])

    logger.info("Printing summary of settings")
    for i in sorted(result.keys()):
      line = i.split(':')
      print('%-*s : %-*s : %-*s : %s' % (fmt[0],line[0],fmt[1],line[1],fmt[2],line[2],len(result[i])))
      #print i.replace(':',' '),len(result[i])
    return(0) 

  def ring_maint(self):
    if self.param[0] == 'show':
      cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigGet "+self.ring+" | grep -v Load"
      output=self.execute(cmd)
      for line in output:
        if not line:
          continue
        cat=line.split()[3].rstrip(',')
        if cat in list(RING_MAINTENANCE_ON.keys()):
            print(line.rstrip())
      return 
    logger.debug('maintenance mode {0} : ring " {1}'.format(self.param[0],self.ring))
    if self.param[0] == 'on':
      doop = RING_MAINTENANCE_ON
    elif self.param[0] == 'off':
      doop = RING_MAINTENANCE_OFF
    else:
      logger.debug('maintenance mode must be in {0}'.format(RING_MAINT))
      exit(9)
    if len(self.param) > 1:
      if self.param[1] == 'noforce' :
        logger.debug('Setting auto_join to 1')
        RING_MAINTENANCE_OFF['join_auto']='1'  
    for i in list(doop.keys()):
      logger.info('Setting {0} to {1} for ring {2}'.format(i,doop[i],self.ring))
      cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigSet "+self.ring+" "+i+" "+doop[i]
      if self.run_exec == False:
        print("NOEXEC "+str(cmd))
      else:
        self.exec_print(cmd)


  def ring_op_log(self):
   logging.debug("comp {0} operation {1} : sub {2} => {3}".format(self.comp,self.op,self.sub,self.param))
   if self.comp == 'supervisor': 
     if self.op == 'logget':
       cmd="ringsh -r "+self.ring+" "+self.sub+" logLevelGet"
     else:
       cmd="ringsh -r "+self.ring+" "+self.sub+" logLevelGet"
     self.exec_print(cmd,rs=True)
     # former print was    self.ifre_print(line.rstrip(),self.ring)
   elif self.comp in ('node','accessor'):
     if self.op == 'logget':
       postfix=" {0} logLevelGet ".format(self.sub)
       if len(self.param) > 0:
         postfix="{0} {1}".format(postfix,self.param[0])
     elif self.op == 'logset':
       """ add 1 1 for syslog params """
       postfix="{0} logLevelSet {1} {2} 1 1".format(self.sub,self.param[0],self.param[1])
     else:
       logging.info("Method not implemented {0} {1}".format(self.comp,self.op))
       exit(9)
     for node in self.server_list :
       cmd="ringsh -r {0} -u {1} {2}".format(self.ring,node,postfix)
       self.exec_print(cmd,rs=True)
   else:
     logging.info("Method not implemented {0} {1}".format(self.comp,self.op))
     exit(9)



  """ Log all set operations : not ready yet"""
  def log_ring_commands(self,cmd):
   return(0)
   now=time.strftime('%X %x %Z')
   print("LOG : "+now+" : "+cmd) 

  ## OLD
  def open_ring_access(self):
    if os.path.exists(ringyaml):
      defyaml=yaml.load(open(ringyaml))
      login=defyaml['sup_login']
      password=defyaml['sup_passwd']
      logger.debug('Using root/password as :'+login+"/"+password) 
    else:
      login='root'
      password='admin'

 # Get the comman to execute and returnlist of output
 # Exit with 1 if error and 9 if receive unexpected param
 # psycality not implemented yet
  def execute(self,cmd,force_method=None,**option):
    output=[]
    force_method='ringsh'
    if force_method:
      run_method=force_method
    else:
      run_method=self.method
    if run_method=="ringsh":
      logging.debug("Execute command : "+cmd)
      p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
      stdout,stderr=p.communicate()
      tempout=stdout.decode("utf-8").split("\n")[::]
      for i in tempout:
        if not i:
          continue
        elif i.split()[0] in STRIPOUT:
          continue
        else:
          output.append(i)
      rc = p.returncode
      if rc != 0:
        logging.info("Command return code non null, probably failed, dumping output")
        print(stderr,stdout)
        exit(1)
      if self.run_log == True:
        self.log_ring_commands(cmd)
      return(output)
    else:
      logging.info("method not implemented")
      exit(9)
 
def main():
  logging.debug("Main"+str(args)+str(cli))
  obj=ring_op(args,cli)
  obj.sort_op()
  obj.exec_per_ring()
  #obj.pass_cmd()
  sys.exit(0)

if __name__ == '__main__':
  main()

# vim: tabstop=2 shiftwidth=2 expandtab
