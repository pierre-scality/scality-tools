#!/usr/bin/python2


import sys
import os
import time
import getopt
import logging 
import yaml 
import subprocess
import re
 
sys.path.insert(0,'/usr/local/scality-ringsh/ringsh/modules')
#from argparse import ArgumentParser
import argparse
from scality.supervisor import Supervisor
from scality.node import Node
from scality.daemon import DaemonFactory , ScalFactoryExceptionTypeNotFound
from scality.common import ScalDaemonException

PRGNAME=os.path.basename(sys.argv[0])
keylist=[]
cli=[]
option={}
sup ='https://127.0.0.1:2443'
#ring='ring1'
dummy=[]
file=None
ringyaml="/etc/scality-supervisor/confv2.yaml"

logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)
logger = logging.getLogger()

CONN=('rest','rs2','connector','conn','accessor')
NODE=('node')
RINGOPS=('get','set','run','status','heal','logget','logset')
NODEOP_W=('set','logset')
NODEOP_R=('get','logget','cat')
NODEOPS=NODEOP_W+NODEOP_R
CONNOP_W=('set','logset')
CONNOP_R=('get','logget','cat')
CONNOPS=('get','set','cat','logget','logset')
SELF_HEALING=('rebuild_auto','chordpurge_enable','join_auto','chordproxy_enable','chordrepair_enable','chordcsd_enable','chordcsd_ringsplit_blocktasks')

RUN_EXEC=False
RUN_LOG=False

login="root"
password="admin"


#parser = ArgumentParser(description='Run ringsh commands on single or all components') 
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description='''
Run ringsh commands on single or several target

Sample commands :
rr.py node get   ==> Will display all nodes parameter on a single random node
rr.py rs2 get   ==> Will display all rs2 connector  parameter on a single random (accept rs2/res/accessor/conn/connector keyword)
rr.py ring get rebuild   ==> will display ring parameter matching rebuild
rr.py -a -f -r META node set 

''') 

parser.add_argument('-a', '--all', help='Loop on all servers', action="store_true", default=False)
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
#parser.add_argument('-D', '--debuglevel', nargs=1, help='Choose debug level see https://docs.python.org/2/library/logging.html')
parser.add_argument('-f', '--force', action="store_true", help='force execution on set commands', default=RUN_EXEC)
parser.add_argument('-l', '--login', nargs='?', help='login', const=login, default=login)
parser.add_argument('-L', '--logset', action="store_true", help='logset', default=RUN_LOG)
parser.add_argument('-p', '--password', nargs='?', help='password', const=password, default=password)
parser.add_argument('-r', '--ring-name', nargs='?', help='ring name default is DATA', const='DATA', default='DATA')
parser.add_argument('-s', '--server-name', nargs=1, help='run on a single defined node')


args,cli=parser.parse_known_args()
if args.debug==True:
  logger.setLevel(logging.DEBUG)
  #print args,cli


#self.s = Supervisor(url=sup,login=login,passwd=password)
#self.r = s.supervisorConfigDso(action="view", dsoname=self.ring)
#rez={}
#node=""
#for n in ringstat['nodes']:
#  nid = '%s:%s' % (n['ip'], n['chordport'])
#  nodes[nid] = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=ring, login=login, passwd=password)
#  names[nid]=n['name']
#  try:
#    nodestatus[nid]=nodes[nid].nodeGetStatus()[0]
#  except ScalDaemonException:
#    print "ERROR accessing node %s" % n['name']
#  if not node: node = nodes[nid]


class ring_op():
  def __init__(self,arg,cli,method="ringsh",server_name=None):
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
    self.method=method
    self.run_exec=arg.force
    self.run_log=arg.logset
    if arg.all == True:
      self.target="ALL"
    elif arg.server_name is not None:
      self.target=arg.server_name
    else:
      self.target="ANY"

  def show_args(self):
    command=""
    for i in self.cli:
      command=command+i+" "
    print self.ring,command

  def get_target(self):
    server_list=[]
    #print 'target'+str(self.target)+self.grep
    if self.method == "ringsh":
      grep=self.grep+':'
      cmd="ringsh -r "+self.ring+" supervisor ringStatus "+self.ring+"| grep "+grep 
      p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
      for line in p.stdout.readlines():
        current=line.split(" ")[1].rstrip(',')
        #print "Ring status is : "+current
        if self.target  == "ALL":
          server_list.append(current)
          continue
        if self.target == "ANY":
          server_list.append(current)
          return(server_list)
        """ Do a regexp to avoid missing not standard component name """
        regex=".*"+re.escape(self.target[0])+".*" 
        rule=re.compile(regex)
        if rule.match(line):
          server_list.append(current)
    else:
      logging.info("Method not defined "+self.method)
    if server_list == []:
      logging.debug('Cannot find name matching')
      exit(2)
    return(server_list)

  def sort_op(self):
    if self.comp=="ring":
      self.sub="supervisor"
      self.grep="State"
    elif self.comp in CONN:
      self.sub="accessor"
      self.comp="accessor"
      self.grep="Connector"
    elif self.comp in NODE:
      self.sub="node"
      self.grep="Node"
    else:
      logger.info("Invalid command "+self.comp)
      raise ValueError("Type not valid ")
      exit(1)
    self.get_target()
     
  """" Check and replace cli options to define the proper one """ 
  def option_check(self):
    logging.debug("Checking args : "+self.sub+" "+self.op)
    if self.sub=="supervisor":
      if self.op not in RINGOPS:
        logger.error("ring command must be in "+str(RINGOPS)) 
        exit(9)
      elif self.op in ("get","status","heal","logget","run"):
        self.ring_op_get()
      else:
        self.ring_op_set()
      return(0)
   
    if self.sub=="node":
      if self.op not in NODEOPS:
        logger.info("node command must be in "+str(NODEOPS))
        exit(5)
      elif self.op in NODEOP_R:
        self.ring_op_get()
      else:
        self.ring_op_set()
    elif self.sub=="accessor":
      if self.op not in CONNOPS:
        logger.info("accessor command must be in "+str(CONNOPS))
        raise ValueError("Command not valid")
      elif self.op in CONNOP_R:
        self.ring_op_get()
      else:
        self.ring_op_set()
    else:
      logger.info("Unknow command "+self.sub)
      raise ValueError("Command not valid")
    return(self.op)
 
  def ifre_print(self,line,label=None):
    if len(self.param) == 0:
      if label == None:
        print line
      else:
        print label+ ": "+line
    else:
      pattern=self.param[0]
      regex=".*"+re.escape(pattern)+".*"
      rule=re.compile(regex)
      if rule.match(line):
        if label == None:
          print line 
        else:
          print label+" : "+line 

  def ring_op_get(self):
    logging.debug("Entering function ring_op_get")
    if self.comp  == 'ring' and self.op == 'status':
      cmd="ringsh -r "+self.ring+" "+self.sub+" ringStatus "+self.ring+"| head -4"
      logging.debug("run ring status command : "+cmd)
      p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
      for line in p.stdout.readlines():
        print line.rstrip()
      return(0)
    elif self.comp == 'ring' and self.op in ('heal','get'):
      cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigGet "+self.ring+" | grep -v Load"
      logging.debug("run command ring health|get : "+cmd)
      p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
      for line in p.stdout.readlines():
        cat=line.split()[3].rstrip(',')
        if self.op == 'heal' :
          if cat in SELF_HEALING:
            print line.rstrip()
        else:
          self.ifre_print(line.rstrip())
      return(0)
    elif self.comp in ('accessor','node') :
      against=self.get_target()
      logging.debug("running command")
      if self.op == 'cat':
        cmd="ringsh -r "+self.ring+" -u "+against[0]+" "+self.sub+" configGet "
        p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        output=[]
        for line in p.stdout.readlines():
          strip=line.split()[1].rstrip(',')
          if strip not in output:
            output.append(strip)
        for i in output:
          print i
        exit(0)
      for i in against:
        if len(self.param)> 0:
          filter=self.param[0]
        else:
          filter=None
        cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configGet"
        logging.debug("run command "+self.sub+" : "+cmd)
        p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for line in p.stdout.readlines():
          self.ifre_print(line.rstrip(),i)
    return(0)

  def ring_op_set(self):
    if self.comp  == 'ring':
      cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigSet "+self.ring+" "+self.param[0]+" "+self.param[1]
      if self.run_exec == False:
        print "NOEXEC "+str(cmd)
      else:
        logging.debug("Running : "+cmd)
        p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for line in p.stdout.readlines():
          print line.rstrip()
        self.op='get'
        self.ring_op_get()
        if self.run_log == True:
          self.ring_op_log(cmd)
        exit(0)
    elif self.comp in ('node','accessor'):
      against=self.get_target()
      for i in against:
        if len(self.param)< 3:  
          logging.info('Missing arguments to set Module:Name:Value ')
          exit(5)
        cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configSet "+self.param[0]+" "+self.param[1]+" "+self.param[2]
        if self.run_exec == False:
          print "NOEXEC "+str(cmd) 
          continue
        logging.debug("run command "+self.sub+" : "+cmd)
        p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for line in p.stdout.readlines():
          self.ifre_print(line.rstrip(),i)
    else:
      logging.info('Method not implemented '+self.comp)
    exit(9)

  """ Log all set operations : not ready yet"""
  def ring_op_log(self,cmd):
   now=time.strftime('%X %x %Z')
   print "LOG : "+now+" : "+cmd 

  def open_ring_access(self):
    if os.path.exists(ringyaml):
      defyaml=yaml.load(open(ringyaml))
      login=defyaml['sup_login']
      password=defyaml['sup_passwd']
      logger.debug('Using root/password as :'+login+"/"+password) 
    else:
      login='root'
      password='admin'
 
def main():
  logging.debug("Main"+str(args)+str(cli))
  obj=ring_op(args,cli)
  #obj.show_args()
  obj.sort_op()
  obj.option_check()
  #obj.ring_op()
  sys.exit(0)

main()

# vim: tabstop=2 shiftwidth=2 expandtab
