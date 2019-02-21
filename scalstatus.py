#!/usr/bin/python2

import os
import sys
from datetime import datetime
import requests
import json
import argparse
import salt.client
import salt.config
import salt.runner 


try:
  parser = argparse.ArgumentParser(description="Check server's process status")
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-c', '--cont', dest='cont', action="store_true", default=False, help='If this option is set program wont quit if it finds missing servers, unexpected results may happend')
  parser.add_argument("-r","--role",help="Specify role (not yet used)")
  parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target daemon to check queue')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')
  parser.add_argument('--zkcount', dest='zkcount',default=5 ,help='Specify number of ZK hosts')
  args=parser.parse_args()
except SystemExit:
  bad = sys.exc_info()[1]
  #print(bad)
  parser.print_help(sys.stderr)
  exit(9)


#ZKNB=5 

# Salt client breaks logging class.
# Simple msg display class
class Msg():
  def __init__(self,level='info'):
    self.level=level
    self.valid=['info','debug','verbose','warning']

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
  #display.debug(ret)
  if ret['down'] != []:
    bad=ret['down']
  display.debug("Server results {}".format(ret))
  if bad == []:
    display.verbose("All servers available")
    display.debug("Servers list {} ".format(','.join(ret['up'])))
  else:
    if not args.cont:
      display.error('Quitting because of missing servers ({0})'.format(','.join(bad)),fatal=True)
    else:
      display.warning('There are unavailable servers which may lead to unexpected results ({0})'.format(','.join(bad)))
  return bad

def check_service(service,operation,target,msg="",dict={}):
  if msg == "" :
    msg = "Checking {1} for {0} service".format(service,operation)
  display.verbose(msg)
  #svsd=local.cmd('roles:ROLE_SVSD','service.status',['scality-svsd'],expr_form="grain")
  #print target,operation,service
  resp=local.cmd(target,operation,[service],expr_form="grain")
  bad=[]
  good=[]
  display.debug("Salt response {0}".format(resp))
  for srv in resp.keys():
    if resp[srv] == False:
      bad.append(srv)
    elif resp[srv] == True:
      good.append(srv)
  if bad != []:
    display.error("{0} {1} is not OK on {2}".format(service,operation,','.join(bad))) 
    return(9)
  else:
    display.info("{0} {1} is ok on all servers ({2})".format(service,operation,','.join(good)),label="OK") 
    display.debug("Servers list ({0})".format(','.join(bad))) 
    return(1)
  return(0)

def check_svsd(type="scality-svsd",target="ROLE_SVSD",targettype='roles'):
  display.verbose("Checking svsd service")
  svsd=check_service("scality-svsd","service.status",targettype+':'+target)
  svsd=check_service("scality-svsd","service.enabled",targettype+':'+target)

def check_fuse(type="scality-sfused",target="ROLE_CONN_SOFS",targettype='roles'):
  display.verbose("Checking {0} service , target {1}".format(type,target))
  fuse=check_service(type,"service.enabled",targettype+':'+target)
  fuse=check_service(type,"service.status",targettype+':'+target)


def check_zk():
  display.verbose("Checking zookeeper status ")
  #global args.zkcount
  zkcount=int(args.zkcount)
  follower=0
  leader=0
  # salt -G roles:ROLE_ZK_NODE cmd.run 'echo stat | nc localhost 2181|grep Mode'
  zk=local.cmd('roles:ROLE_ZK_NODE','cmd.run',['echo stat | nc localhost 2181|grep Mode'],expr_form="grain")
  display.debug("Zookeeper result {0}".format(zk))
  if len(zk.keys()) != zkcount:
    display.warning("Zookeeper does not run {0} instances".format(zkcount))
  for i in zk.keys():
    if zk[i].split(':')[1].strip() == 'follower':
      follower=follower+1
    elif zk[i].split(':')[1].strip() == 'leader': 
      leader=leader+1
    else:
      display.error('unexpected state on zookeeper {0} {1}'.format(i,zk[i]))
  if follower != zkcount -1:
    display.error('unexpected number of zookeeper follower, expect {0} found {1}'.format(zkcount -1,follower))
  if leader != 1:
    display.error('Zookeeper number of master is {0}, one single leader is expected'.format(leader))
  display.info('{0} leader and {1} zookeeper follower found'.format(leader,follower),label="OK")
  return(0)

def check_es():
  check_service("elasticsearch","service.enabled","roles:ROLE_ELASTIC")
  es=local.cmd('roles:ROLE_SUP','cmd.run',['hostname'],expr_form="grain")
  target="localhost"
  url="http://{0}/api/v0.1/es_proxy/_cluster/health?pretty".format(target)
  try:
    r = requests.get(url)
  except requests.exceptions.RequestException as e:
    display.error("Error connecting to supervisor on localhost: {0}".format(target))
    display.debug("Error is  : \n{0}\n".format(e))
    return(1)
  if r.status_code == 200:
    status=json.loads(r.text)
  else:
    display.error("Sup return non 200 response {0}".format(r.status_code))
    return(1)
  if status['status'] == 'green': 
    display.info("Elastic search status is green",label="OK")
  else:
    display.error("Elastic search status not  green",label="OK")
    print json.dumps(status,indent=2)
    check_service("elasticsearch","service.status","roles:ROLE_ELASTIC")
    
def check_corosync(target="roles:ROLE_COROSYNC"):
  check_service("corosync","service.enabled",target) 
  check_service("corosync","service.status",target) 

def check_samba(target="roles:ROLE_CONN_CIFS",service=None):
  if service == None:
    service=['sernet-samba-smbd','sernet-samba-nmbd']
  for i in service:
    check_service(i,"service.enabled",target)
    check_service(i,"service.status",target) 
  
    
def main():
  disable_proxy()
  check_server_status(args.cont)
  check_svsd()
  check_zk()
  check_fuse()
  check_fuse(target="ROLE_CONN_CIFS")
  check_es()
  check_corosync()
  check_samba()

if __name__ == '__main__':
  main()
else:
  print "loaded"

