#!/usr/bin/python

import os
import sys
from datetime import datetime
import requests
import json
import argparse
import salt.client
import salt.config
import salt.runner 

parser = argparse.ArgumentParser(description="Check server's GEO replication status")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-c', '--cont', dest='cont', action="store_true", default=False, help='If this option is set program wont quit if it finds missing servers, unexpected results may happend')
parser.add_argument("-r","--repli",action="store_true",help="Check replication queue only")
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target daemon to check queue')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')

ZKNB=5 

# Salt client breaks logging class.
# Simple msg display class
class Msg():
  def __init__(self,level='info'):
    self.level=level
    self.valid=['info','debug','verbose']

  def set(self,level):
    print "{0:15} : {1}".format('INFO','Setting loglevel to '+level)
    if level not in self.valid:
      self.display("not a valid level {0}".format(level))
      return(9)
    self.level=level

  def verbose(self,msg,label=None):
    if self.level != 'info':
      if label != None:
        header=label
      else:
        header='VERBOSE'
      print "{0:15} : {1}".format(header,msg)

  def info(self,msg,label=None):
    if label != None:
      header=label
    else:
      header="INFO"
    print "{0:15} : {1}".format(header,msg)
  
  def error(self,msg,fatal=False):
    header="ERROR"
    print "{0:15} : {1}".format(header,msg)
    if fatal:
      exit(9)
  
  def warning(self,msg,fatal=False):
    header="WARNING"
    print "{0:15} : {1}".format(header,msg)
    if fatal:
      exit(9)

  def debug(self,msg):
    if self.level == "debug":
      header="DEBUG"
      print "{0:15} : {1}".format(header,msg)

  def showlevel(self):
    print "Error lelvel is {0} : ".format(self.level)

display=Msg('info')


#args = parser.parse_args()
args,cli=parser.parse_known_args()
if args.verbose == True:
  display.set('verbose')
if args.debug==True:
  display.set('debug')

local = salt.client.LocalClient()
journal='/journal'

def disable_proxy():
  done=0
  for k in list(os.environ.keys()):
    if k.lower().endswith('_proxy'):
      del os.environ[k]
      done=1
  if done != 0:
    display.debug("Proxy has been disabled")

def check_server_status(cont=True):
  bad=[]
  display.info("Checking all servers availability")
  opts = salt.config.master_config('/etc/salt/master.d/60_scality.conf')
  opts['quiet'] = True
  runner = salt.runner.RunnerClient(opts)
  ret = runner.cmd('manage.status',[])
  display.debug(ret)
  if ret['down'] != []:
    bad=ret['down']
  display.debug("Server results {}".format(ret))
  if bad == []:
    display.verbose("All servers available{} ".format(','.join(ret['up'])))
  else:
    if not args.cont:
      display.error('Quitting because of missing servers ({0})'.format(','.join(bad)),fatal=True)
    else:
      display.error('There are unavailable servers which may lead to unexpected results ({0})'.format(','.join(bad)))
  return bad

def check_svsd():
  display.info("Checking svsd service")
  svsd=local.cmd('roles:ROLE_SVSD','service.status',['scality-svsd'],expr_form="grain")
  bad=[]
  for srv in svsd.keys():
    if svsd[srv] == False:
      bad.append(srv)
  if bad != []:
    display.error("Some hosts are not running svsd : {0}".format(','.join(bad))) 
    return(9)
  else:
    display.debug("All servers run SVSD {0}".format(','.join(svsd.keys())))
  return(0)

def check_service(service,grains,label=None):
  if label == None:
    label = service
  display.info("Checking {0} services".format(label))
  resp=local.cmd('roles:'+grains,'service.status',[service],expr_form="grain")
  display.debug('response check {0} {1}'.format(service,resp))
  bad=[]
  for srv in resp.keys():
    if resp[srv] == False:
      bad.append(srv)
  if bad != []:
    display.error("Some hosts are not running {1} : {0}".format(','.join(bad),service))
    return(9)
  else:
    display.debug("All servers run {1} {0}".format(str(','.join(resp.keys())),service))
  return(0)



def check_samba():
  display.info("Checking samba services")
  srvlist=['sernet-samba-smbd','sernet-samba-smbd','sernet-samba-winbindd']
  for this in srvlist:
    resp=local.cmd('roles:ROLE_CONN_CIFS','service.status',[this],expr_form="grain")
    display.debug('response check samba {0}'.format(resp))
    bad=[]
    for srv in resp.keys():
      if resp[srv] == False:
        bad.append(srv)
    if bad != []:
      display.error("Some hosts are not running {1} : {0}".format(','.join(bad),this)) 
      return(9)
    else:
      display.debug("All servers run {1} {0}".format(str(','.join(resp.keys())),this))
  return(0)


def verify_nfs_processes():
  display.verbose("Checking nfs service")
  nfs=local.cmd('roles:ROLE_CONN_NFS','service.status',['scality-sfused'],expr_form="grain")
  bad=[]
  nfsservercount=len(nfs.keys())
  for srv in nfs.keys():
    if nfs[srv] == False:
      bad.append(srv)
  if bad != []:
    if nfsservercount == len(bad):
      display.error("All NFS servers are down: {0}".format(','.join(bad))) 
    else:
      display.warning("Some hosts are not running NFS : {0}".format(','.join(bad))) 
    return(9)
  else:
    display.debug("All servers run NFS {0}".format(','.join(nfs.keys())))
  return(0)


def check_zk():
  display.verbose("Checking zookeeper status ")
  global ZKNB
  follower=0
  leader=0
  # salt -G roles:ROLE_ZK_NODE cmd.run 'echo stat | nc localhost 2181|grep Mode'
  zk=local.cmd('roles:ROLE_ZK_NODE','cmd.run',['echo stat | nc localhost 2181|grep Mode'],expr_form="grain")
  display.debug("Zookeeper result {0}".format(zk))
  if len(zk.keys()) != ZKNB:
    display.warning("Zookeeper does not run {0} instances".format(ZKNB))
  for i in zk.keys():
    if zk[i].split(':')[1].strip() == 'follower':
      follower=follower+1
    elif zk[i].split(':')[1].strip() == 'leader': 
      leader=leader+1
    else:
      display.error('unexpected state on zookeeper {0} {1}'.format(i,zk[i]))
  if follower != ZKNB -1:
    display.error('unexpected number of zookeeper follower, expect {0} found {1}'.format(ZKNB -1,follower))
  if leader != 1:
    display.error('Zookeeper number of master is {0}, one single leader is expected'.format(leader))
  display.verbose('{0} leader and {1} zookeeper follower found'.format(leader,follower))
  return(0)

# Checking process on geo hosts 
def get_geo_host_processes():
  rep={}
  rep['source']=[]
  rep['target']=[]
  display.info('Checking GEO connector processes')
  source=local.cmd('roles:ROLE_GEO','service.status',['uwsgi'],expr_form="grain")
  for i in source.keys():
    if i not in rep.keys():
      rep[i]=[]
    if source[i] == False:
      display.debug('Server {0} is NOT running GEO SOURCE daemon'.format(i))
    else:
      display.debug('Server {0} is running GEO SOURCE daemon'.format(i))
      rep[i].append('source')
      rep["source"].append(i)
  target=local.cmd('roles:ROLE_GEO','service.status',['scality-sfullsyncd-target'],expr_form="grain")
  for i in target.keys():
    if i not in rep.keys():
      rep[i]=()
    if target[i] == False:
      display.debug("Server {0} is NOT running GEO TARGET".format(i))
    else:
      display.debug("Server {0} is running GEO TARGET".format(i))
      rep[i].append('target')
      rep["target"].append(i)
  return(rep)

def verify_geo_host_processes(dict):
  display.debug("Display receive struct {0}".format(dict))
  source=len(dict['source'])
  if source == 1:
    display.info("Server {0} is GEO SOURCE".format(dict['source'][0]))
  elif source > 1 :
    display.error("There is more than 1 server running GEO SOURCE")
  target=len(dict['target'])
  if target == 1:
    display.info("Server {0} is GEO TARGET".format(dict['target'][0]))
  elif target > 1:
    display.error("There is more than 1 server running GEO SOURCE")
  if source == 0 and target == 0:
    display.error("There is neither GEO SOURCE or TARGET daemon running")


def get_cdmi_host_process(georole):
  display.info("Checking CDMI connector journal configuration")
  geosync=local.cmd('roles:ROLE_CONN_CDMI','file.file_exists',['/run/scality/connectors/dewpoint/config/general/geosync'],expr_form="grain")
  #if geosync[i] == False:
  #  display.error("Server {0} is NOT configured for journal".format(i))
  #  return(9)
  if georole['source'] != []:
    role='source'
  elif georole['target'] != []:
    role='target'
  else:
    role='unknown'
  display.debug("get_cdmi_host_process for {0} GEO role".format(role))
  for i in geosync.keys():
    if 'cdmi' not in georole.keys():
      georole['cdmi']=[]
    georole['cdmi'].append(i)
    georole[i]=['cdmi']  
    geojournalon=local.cmd(i,'cmd.run',['cat /run/scality/connectors/dewpoint/config/general/geosync'])
    display.debug("geo journal for {0} is {1}".format(i,geojournalon))
    if geojournalon[i] == 'true':
      if role == 'source':
        display.verbose("Server {0} is running geo journal".format(i))
      else:
        display.error("Server {0} is running geo journal BUT site is not running GEO SOURCE".format(i))
    else:
      if role == 'source':
        display.error("Server {0} is NOT running geo journal AND is GEO SOURCE site".format(i))
      else:
        display.verbose("Server {0} is NOT running geo journal".format(i))
          


# salt.modules.mount.is_mounted(name)
def get_cdmi_journal_mount():
  display.info("Checking CDMI/GEO connector journal mountpoint")
  for role in ["ROLE_CONN_CDMI","ROLE_GEO"]:
    mount=local.cmd('roles:'+role,'file.is_mounted',[journal],expr_form="grain")
    for i in mount.keys():
      if mount[i] == False:
        display.error("Server {0} is NOT mounting journal".format(i))
      else:
        display.verbose("Server {0} is mounting journal".format(i))

def check_journal_entries(georole,journal="/journal"):
  if len(georole['source']) == 0:
    display.debug("There are no source daemon, do not check journal entries")
    return(0)
  display.info("Checking journal entries")
  # below command does not timeout even with timeout param.
  queue=local.cmd('roles:ROLE_GEO','file.find',['/journal/accepted/','name=geosync.*'],timeout=9,expr_form="grain")
  srv=queue.keys()[0]
  qfiles=queue[srv]
  if len(qfiles) != 0:
    display.warning("Journal queue is not empty, {0} files queued".format(len(qfiles)))
    display.debug("Remaing files"+str(qfiles))
  else:
    display.verbose("Journal queue is empty")

def guess_remote_target(hostname):
  s=hostname.split('-')
  if s[1] == 'prd':
    s[1] = 'dr'
  elif s[1] == 'dr':
    s[1] = 'prd'
  else:
    return False
  s='-'.join(s)
  return(s)

""" Target server may be passed as argument or if target site be in the georol dict """
""" Otherwise we guess the rep server hostname by changing prd/dr in the hostname (vopp naming) """
""" If target server passed as argument it will prevail """ 
def check_replication_status(dict,target=None):
  if target == None:
    if dict['target'] != []:
      target=dict['target']
    # salt return list and may (but shouldnt return several servers)
      if len(target) > 1:
        display.error("Too much target hosts {0}".format(target))
        return(3)
      else:
        target=target[0]
    else:
      display.debug("No GEO TARGET server, guessing")
      geoserver=local.cmd('roles:ROLE_GEO','cmd.run',['hostname'],expr_form="grain") 
      geoserver=geoserver.keys()[0]
      target=guess_remote_target(geoserver)
      if target == False:
        display.debug("Not GEO TARGET server found")
        return(0)
      else:
        display.debug("Using guessed target server {0}".format(target))
  else:
    target=target[0]
  display.info("Checking GEO TARGET {0} daemon status".format(target))
  url="http://{0}:8381/status".format(target)
  display.debug("Using target server url {0}".format(url))
  try:
    r = requests.get(url)
  except requests.exceptions.RequestException as e:  # This is the correct syntax
    display.error("Error connecting to GEO TARGET daemon : {0}".format(target))
    display.debug("Error is  : \n{0}\n".format(e))
    return(8)
  if r.status_code == 200:
    #print(r.headers)
    #print(r.text)
    status=json.loads(r.text)
    t=str(status["metrics"]["transfers_in_progress"]["value"])
    m=str(status["metrics"]["metadata_operations_in_progress"]["value"])
    f=str(status["metrics"]["total_failed_operations"]["value"])
    transfert=t.encode('utf-8')
    meta=m.encode('utf-8')
    failures=int(f.encode('utf-8'))
    if int(transfert) != 0:
      display.warning("Transfert in progress {0}".format(transfert))
    else:
      display.verbose("Transfert in progress {0}".format(transfert))
    if int(meta) != 0:
      display.warning("Metadata transfert in progress {0}".format(meta))
    else:
      display.verbose("Metadata transfert in progress {0}".format(transfert))
    if failures != 0:
      display.error("failed operation(s) found : {0} error(s)".format(failures))
    else:
      display.verbose("No failed operations")
  else:
   display.error("Checking GEO TARGET daemon transfert queue")

def main():
  disable_proxy()
  if args.repli == True:
    georole=get_geo_host_processes()
    verify_geo_host_processes(georole)
    check_journal_entries(georole)
    check_replication_status(georole,target=args.target)
  else:
    check_server_status(args.cont)
    check_svsd()
    check_samba()
    check_service('scality-dewpoint-fcgi','ROLE_CONN_CDMI',label='CDMI')
    check_zk()
    georole=get_geo_host_processes()
    verify_nfs_processes()
    verify_geo_host_processes(georole)
    #display.debug(georole)
    get_cdmi_host_process(georole)
    get_cdmi_journal_mount()
    check_journal_entries(georole)
    check_replication_status(georole,target=args.target)
    display.debug(georole)

if __name__ == '__main__':
  main()
else:
  print "loaded"

