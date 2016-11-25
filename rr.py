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
import json

 
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

logging.basicConfig(format='%(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
logger = logging.getLogger()

try:
  RING=os.environ['RING']
except KeyError:
  RING='DATA'

SPECIAL=('compare')
CONN=('rest','rs2','connector','conn','accessor','r')
NODE=('node','n')
RINGOPS=('get','set','run','status','heal','logget','logset','list')
NODEOP_W=('set','logset')
NODEOP_R=('get','logget','cat','list','comp','compare','stat','exec')
NODEOPS=NODEOP_W+NODEOP_R
CONNOP_W=('set','logset')
CONNOP_R=('get','logget','cat','list')
CONNOPS=CONNOP_W+CONNOP_R
SELF_HEALING=('rebuild_auto','chordpurge_enable','join_auto','chordproxy_enable','chordrepair_enable','chordcsd_enable','chordcsd_ringsplit_blocktasks','chordcsd_ringsplit_minhiwat','chordcsd_ringsplit_minlowat','chordcsd_ringsplit_unblocktasks')

RUN_EXEC=False
RUN_LOG=False
STRIPOUT=['Load','Use']
PYSCAL=('py','python','pyscal','pyscality')
PARAMFILE=None
CREDFILE="/tmp/scality-installer-credentials"
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

By default it runs on a single node/connector needs -a to iterate on all of them
The set command by default do not run command but dislay it, one need to add -a flag
So to run a set command on all nodes one needs to run:
 rr.py -fa node set msgstore_protocol_chord chordhttpdmaxsessionschordhttpdmaxsessions 

 * ring name 
 Ring name must be specfied with -r or use DATA as default ring name.
 One can use RING env variable instead.

 * ring status 
 ring status [long] : gives ringStatus with just general status or all but Disk with long param

 * log settings 
 node logget/logset syntax as for node/connector

 * statistics
 node stat [param]
 Node statistics (dumpstat) without arg list all stats
 With 1 parameter do an exact match of the path

 * compare mode (node only for now)
 -c <param file> node compare
You can compare node parameters based on a text file (with -c parameter file) 
with format module:parameter as below (unlimited number of lines) as :
  msgstore_protocol_chord:chordhttpdmaxsessions

It will output for this parameters the number of nodes having different values  :
msgstore_protocol_chord chordhttpdmaxsessions 2000 1
msgstore_protocol_chord chordhttpdmaxsessions 2500 6
msgstore_protocol_chord chordhttpdmaxsessions 3000 29

If you want then to check with node has different parameter you have to use :
rr.py -a node get msgstore_protocol_chord chordhttpdmaxsessions 2500 
It will return all nodes having this parameter

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
parser.add_argument('-m', '--method', nargs='?', help='Switch internal code to ringsh or pyscality',default='ringsh')
parser.add_argument('-c', '--compfile', nargs='?', help='List of parameters to be compared',default=PARAMFILE)


args,cli=parser.parse_known_args()
if args.debug==True:
  logger.setLevel(logging.DEBUG)

class ring_obj():
  def __init__(self,login,password,ring,comp="None",target="None",url="https://127.0.0.1:2443"):
  #def __init__(self,login,password,ring,url="https://127.0.0.1:2443",type="node"):
   logger.debug("Initialisation object ring : "+str(comp))
   self.ring=ring
   self.node=""
   self.nodes={}
   self.rs2={}
   self.names={}
   self.rs2names={}
   self.nodestatus={}
   self.comp=comp
   self.sup = Supervisor(url=url,login=login,passwd=password)
   self.status = self.sup.supervisorConfigDso(action="view", dsoname=self.ring)
   if self.comp == 'node':
     logger.info('Getting ring configuration')
     for n in self.status['nodes']:
       nid = '%s:%s' % (n['ip'], n['chordport'])
       self.nodes[nid] = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=self.ring, login=login, passwd=password)
       self.names[nid]=n['name']
       try:
         self.nodestatus[nid]=self.nodes[nid].nodeGetStatus()[0]
       except ScalDaemonException:
         print "ERROR accessing node %s" % n['name']
       if not self.node: self.node = self.nodes[nid]
   elif self.comp == 'accessor': 
     r = self.sup.supervisorConfigBizstore(action="view", dso_filter=ring)
     for i in r['restconnectors']:
       self.rid = '%s:%s' % (i['adminaddress'], i['adminport'])
       self.rs2names[rid]=i['name'] 
   else: 
     raise NotImplementedError
     # if we reach here we are probably neither working onnode/accessor => sup 

  def obj_list(self,param):
    logger.debug("Building list for : "+str(self.comp)+','+param)
    if self.comp == 'supervisor':
      for i in self.sup.supervisorConfigMain().keys():
        print i,
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
        print dict[i],i
    elif param == 'name':
      for i in dict.keys():
        print dict[i]
    elif param == 'address':
      for i in dict: print dict[i]
    return(0)

  def ip_to_n(self,name):
    if name in self.names.keys(): 
      return(self.names[name])
    else:
      return None

  def n_to_ip(self,name='ALL'):
    out={}
    for i in self.names.keys():
      if name == 'ALL':
        out[self.names[i]]=i
      elif self.names[i] == name: 
        return(i)
    return(out)

  def obj_config_struct(self):
    struct={}
    for this in self.nodes.keys():
      if this not in struct.keys():
        struct[this]={}
      struct[this]=self.nodes[this].configViewModule()
    return(struct)  


  def obj_conf(self,target):
    print a 

class ring_op():
  def __init__(self,arg,cli,server_name=None):
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
    self.run_exec=arg.force
    self.run_log=arg.logall
    self.server_list=[]
    self.ring_list=[]
    self.compfile=arg.compfile
    self.all_rings=arg.all_rings
    if arg.method not in PYSCAL:
      self.method='ringsh'
    else:
      self.method='pyscal'
    if arg.all == True:
      self.target="ALL"
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
    print self.ring,command

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
      self.pass_cmd()
      print

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
          logger.debug("Checking server to list "+current+" "+self.target[0])
          regex=".*"+re.escape(self.target[0])+".*" 
          rule=re.compile(regex)
          if rule.match(current):
            logger.debug("Adding server to list "+current)
            self.server_list.append(current)
        
    if self.server_list == []:
      logging.debug('Cannot find name target')
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
      ##raise ValueError("Type not valid ")
      exit(1)
    ##self.get_target()
     
  """" Check valid parameter and pass to ring command """ 
  def pass_cmd(self):
    if self.compfile != None:
      self.ring_op_compare()
      return(0)
    if self.op == 'list': 
      self.ring_op_list()
      return(0)
    logging.debug("Passing command : "+self.sub+" "+self.op+" Ring : "+self.ring)
    if self.op in ('logget','logset'):
      self.ring_op_log()
      return(0) 
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

  def ifre_print(self,line,label=None,field=0,exact=False,raw=0):
    if len(self.param) == 0 or raw == 1:
      if label == None:
        print line
      else:
        print label+ ": "+line
      return(0)
    elif len(self.param) == 1 or self.comp == 'supervisor' :
      """ to search when having module parameter """
      logger.debug("ifreprint {0}".format(str(self.param)))
      pattern=self.param[field]
      if exact:
        regex=".*"+re.escape(pattern)+"\W.*"
      else:
        regex=".*"+re.escape(pattern)+".*"
      rule=re.compile(regex)
      if rule.match(line):
        if label == None:
          print line 
        else:
          print label+" : "+line
      return(0)
    elif len(self.param) > 1:
      logger.debug("doing exact match {0}".format(str(self.param)))
      z={}
      for j in line.split(','):
        z[j.split(':')[0].strip()]=j.split(':')[1].strip()
      if z['Name'] != self.param[1]:
        logger.debug('Ignoring value '+z['Name']+' not equal to '+self.param[1])
        return(0)
    elif len(self.param) > 2:
      if z['Value'] != self.param[2]:
        logger.debug('Ignoring value '+z['Value']+' not equal to '+self.param[2])
        return(0)
    if label == None:
        print line
    else:
        print label+ ": "+line
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
      cmd="ringsh -r "+self.ring+" supervisor ringStatus "+self.ring+" | grep "+self.grep+":"
      output=self.execute(cmd)
      for line in output:
        print line.rstrip()
    return(0)

  def ring_op_get(self):
    logging.debug("Entering function ring_op_get {0} {1}".format(str(self.comp),str(self.op)))
    if self.comp  == 'supervisor' and self.op == 'status':
      if len(self.param) > 0 and self.param[0] == 'long':
        cmd="ringsh -r "+self.ring+" "+self.sub+" ringStatus "+self.ring+"| grep -v '^Disk'"
      else:
        cmd="ringsh -r "+self.ring+" "+self.sub+" ringStatus "+self.ring+"| head -4"
      output=self.execute(cmd)
      for line in output:
        print line.rstrip()
      return(0)
    elif self.comp == 'supervisor' and self.op in ('heal','get'):
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
          logging.debug("Displaying result sorting in : "+str(self.param))
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
          module=line.split()[1].rstrip(',')
          if module not in done:
            self.ifre_print(module)
            done.append(module)
        return(0)
      """ We are in a configGet/exec """
      logging.debug("Entering configet/exec module :: {0} {1}".format(self.sub,self.param[0]))
      field=0
      for i in self.server_list :
        #filter=None
        #if len(self.param) == 0:
        #  filter=self.param[0]
        """ if param[0] is set we do a regex with ifre_print """
        if self.op == 'stat':
          if len(self.param) == 0: 
            cmd="ringsh -r {0} -u {1} {2} dumpStats".format(self.ring,i,self.sub)
            output=self.execute(cmd)
            for line in output:
              self.ifre_print(line.rstrip(),i)
            exit(0)
          else:
            #cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configGet "+self.param[0]
            cmd="ringsh -r {0} -u {1} {2} dumpStats {3}".format(self.ring,i,self.sub,self.param[0]) 
          # to go in exact match in ifre_print set parm 1 = 0
          output=self.execute(cmd)
          for line in output:
            self.ifre_print(line.rstrip(),i,exact=1)
          continue
        if self.op == 'exec':
          command=' '.join(map(str, self.param[0:]))
          cmd="ringsh -r {0} -u {1} {2} {3}".format(self.ring,i,self.sub,command)
          logging.debug("run command :: "+self.sub+" : "+cmd)
          output=self.execute(cmd)
          #print output
          for line in output:
            self.ifre_print(line.rstrip(),i,raw=1)
          continue 
        if len(self.param) <=1:
          cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configGet"
          logging.debug("run command :: "+self.sub+" : "+cmd)
          output=self.execute(cmd)
          #print output
          for line in output:
            self.ifre_print(line.rstrip(),i)
	  continue
        """ To search module : param we check if we had more than 1 param on input and set field to 1 to pass to print command"""
        """ This is exact match """
        """ param is ['module','name','value']  """
        cmd="ringsh -r "+self.ring+" -u "+i+" "+self.sub+" configGet "+self.param[0]
        output=self.execute(cmd)
        #print str(len(self.param)),str(self.param)
        for line in output:
          self.ifre_print(line.rstrip(),i)
    return(0)


  def ring_op_set(self):
    if self.comp  == 'supervisor':
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
      logging.info("Component not implemented ".format(self.comp))
      exit(9)
  """ Compare param in dev """
  def ring_op_compare(self):
    #source=defaultdict(lambda: defaultdict(dict))
    source={}
    result={}
    try:
      f = open(self.compfile,'r')
    except IOError as e:
      logger.error("File error({0}): {1} : {2}".format(e.errno, e.strerror,self.compfile))
      exit(9)
    instance=ring_obj(self.login,self.password,self.ring,self.comp)
    objstruct=instance.obj_config_struct() 
    linenb=0
    for line in f:
      if line.count(':') == 0:
        logger.debug('Ignoring line : '+str(linenb))
        continue
      module=line.split(':')[0].rstrip() 
      param=line.split(':')[1].rstrip() 
      value=None
      if line.count(':') == 2:
        value=line.split(':')[2].rstrip()
      if not module in source.keys():
        source[module]={}
      if not param in source[module].keys():
        source[module][param]=value
      linenb+=1
    logger.debug('file parsed nb lines '+str(linenb))
    ip=[]
    for server in self.server_list:
      ip.append(instance.n_to_ip(server))
      for this in ip:
        logger.debug('Found target to compare '+str(this))
        for module in source.keys():
          for param in  source[module].keys():
            logger.debug("Param to get "+this+":"+module+":"+param)
            try:
              value=objstruct[this][module][param]['value']
            except KeyError as e:
              logger.info("no such key "+module+" , "+param)
              continue
            #print instance.ip_to_n(this)+" "+str(module)+":"+str(param)+" "+str(value)
            index=str(module)+":"+(param)+":"+str(value) 
            if index not in result.keys():
              result[index]=[this]
            else:
              if this not in result[index]:
                result[index].append(this)
    for i in sorted(result.keys()):
      #print i,len(result[i]),result[i]
      print i.replace(':',' '),len(result[i])
    return(0) 

  def ring_op_log(self):
   if self.op == 'logset':
     logging.info("Method not implemented {0} {1}".format(self.comp,self.op))
     exit(9)
   print str(self.sub)
   if self.comp == 'supervisor' and self.op == 'logget':
     cmd="ringsh -r "+self.ring+" "+self.sub+" logLevelGet"
     output=self.execute(cmd)
     for line in output:
       if not line:
         continue
       else:
         self.ifre_print(line.rstrip(),self.ring)
     return(0)
   elif self.comp in ('node','accessor') and self.op == 'logget':
     for node in self.server_list :
       cmd="ringsh -r "+self.ring+" -u "+node+" "+self.sub+" logLevelGet"
       output=self.execute(cmd)
       for line in output:
         if not line:
           continue
         else:
           self.ifre_print(line.rstrip(),node)
     return(0)
   elif self.comp == 'supervisor' and self.op == 'logset': 
     cmd="ringsh -r "+self.ring+" "+self.sub+" logLevelGet"
     output=self.execute(cmd)
   elif self.comp in ('node','accessor') and self.op == 'logget':
     for node in self.server_list :
       cmd="ringsh -r "+self.ring+" -u "+node+" "+self.sub+" logLevelGet"
       output=self.execute(cmd)
   else:
     logging.info("Method not implemented {0} {1}".format(self.comp,self.op))
     exit(9)



  """ Log all set operations : not ready yet"""
  def log_ring_commands(self,cmd):
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
