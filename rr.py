#!/usr/bin/python2


import sys
import os
import time
import getopt
import logging 
import yaml 
import subprocess
import re
import signal
 
sys.path.insert(0,'/usr/local/scality-ringsh/ringsh/modules')
#from argparse import ArgumentParser
import argparse
from scality.supervisor import Supervisor
from scality.node import Node
from scality.daemon import DaemonFactory , ScalFactoryExceptionTypeNotFound
from scality.common import ScalDaemonException

def sighandler(signum, frame):
        print 'Graceful exit'
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
STRIPOUT=['Load','Use']

login="root"
password="admin"


parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description='''
Run ringsh commands on single or several target

Sample commands :
rr.py node get   ==> Will display all nodes parameter on a single random node
rr.py node get timeout ==> a parameter can be added to limit output on this string
rr.py rs2 get   ==> Will display all rs2 connector  parameter on a single random (accept rs2/res/accessor/conn/connector keyword)
rr.py ring get rebuild   ==> will display ring parameter matching rebuild
rr.py -a -f -r META node set ov_interface_admin maxsessions 100 => when parameter has a space use \ like ov_protocol_netscript "socket\ timeout" 29 

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
      print parser.description
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
    self.server_list=[]
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
    logger.debug("Building target list"+str(self.target)+','+self.grep)
    if self.method == "ringsh":
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
          logger.debug("Chekging server to list "+current+" "+self.target[0])
          regex=".*"+re.escape(self.target[0])+".*" 
          rule=re.compile(regex)
          if rule.match(current):
            logger.debug("Adding server to list "+current)
            self.server_list.append(current)
    if self.server_list == []:
      logging.debug('Cannot find name target')
      exit(2)

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
      ##raise ValueError("Type not valid ")
      exit(1)
    ##self.get_target()
     
  """" Check and replace cli options to define the proper one """ 
  def pass_cmd(self):
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
      output=self.execute(cmd)
      for line in output:
        print line.rstrip()
      return(0)
    elif self.comp == 'ring' and self.op in ('heal','get'):
      cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigGet "+self.ring+" | grep -v Load"
      output=self.execute(cmd)
      for line in output:
        if not line:
          continue
        cat=line.split()[3].rstrip(',')
        if self.op == 'heal' :
          if cat in SELF_HEALING:
            print line.rstrip()
        else:
          #logging.debug("Displaying result sorting in : "+str(self.param))
          self.ifre_print(line.rstrip())
      return(0)
    elif self.comp in ('accessor','node') :
      if self.op == 'cat':
        cmd="ringsh -r "+self.ring+" -u "+self.server_list[0]+" "+self.sub+" configGet "
        output=self.execute(cmd)
        done=[]
        for line in output:
          if not line:
            continue
          
          strip=line.split()[1].rstrip(',')
          if strip not in done:
            done.append(strip)
            print strip
        #for i in output:
        #  print i
        exit(0)
      for i in self.server_list :
        if len(self.param)> 0:
          filter=self.param[0]
        else:
          filter=None
        cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configGet"
        logging.debug("run command "+self.sub+" : "+cmd)
        output=self.execute(cmd)
        for line in output:
          self.ifre_print(line.rstrip(),i)
    return(0)


  def ring_op_set(self):
    if self.comp  == 'ring':
      cmd="ringsh -r "+self.ring+" "+self.sub+" ringConfigSet "+self.ring+" "+self.param[0]+" "+self.param[1]
      if self.run_exec == False:
        print "NOEXEC "+str(cmd)
      else:
        logging.debug("Running : "+cmd)
        output=self.execute(cmd)
        for line in output:
          if not line:
            continue
          elif line.split()[0] == "Load":
            continue
          print line.rstrip()
        self.op='get'
        self.ring_op_get()
        exit(0)
    elif self.comp in ('node','accessor'):
      for i in self.server_list :
        if len(self.param)< 3:  
          logging.info('Missing arguments to set Module:Name:Value ')
          exit(5)
        if ' ' in self.param[1]:
          self.param[1]=self.param[1].replace(" ","\ ")
        cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configSet "+self.param[0]+" "+self.param[1]+" "+self.param[2]
        if self.run_exec == False:
          print "NOEXEC "+str(cmd) 
          continue
        logging.debug("run command "+self.sub+" : "+cmd)
        output=self.execute(cmd)
        for line in output:
          self.ifre_print(line.rstrip(),i)
    else:
      logging.info('Method not implemented '+self.comp)
      exit(9)

  """ Log all set operations : not ready yet"""
  def ring_op_log(self,cmd):
   return(0)
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
 
 # Get the comman toeexecute and returnlist of output
 # Exit with 1 if error and 9 if receive unexpected param
  def execute(self,cmd,force_method=None,**option):
    output=[]
    if force_method:
      run_method=force_method
    else:
      run_method=self.method
    if run_method=="ringsh":
      logging.debug("Execute command : "+cmd)
      p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
      stdout,stderr=p.communicate()
      tempout=stdout.split("\n")[::]
      #print tempout
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
        print stderr,stdout
        exit(1)
      if self.run_log == True:
        self.ring_op_log(cmd)
      return(output)
    else:
      logging.info("method not implemented")
      exit(9)
 
def main():
  logging.debug("Main"+str(args)+str(cli))
  obj=ring_op(args,cli)
  obj.sort_op()
  obj.get_target()
  obj.pass_cmd()
  sys.exit(0)

if __name__ == '__main__':
  main()

# vim: tabstop=2 shiftwidth=2 expandtab
