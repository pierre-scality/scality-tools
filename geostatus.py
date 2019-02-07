#!/usr/bin/python

import os
import sys
from datetime import datetime
import requests
import json
import argparse
import salt.client
import salt.config

parser = argparse.ArgumentParser(description="Check server's GEO replication status")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument("-r","--role",help="Specify role (not yet used)")
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target daemon to check queue')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')


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

def check_server_status(list=None):
  if list == None:
    list=['ROLE_STORE']
  display.debug("Checking server status for role {0}".format(list))
  bad=[]
  for role in list:
    test=local.cmd('roles:'+role,'test.ping',expr_form="grain")
    print test
    for i in test:
      if test[i] != True:
        bad.append(test(i))
        display.error("server {0} is not accessible".format(i))
      else:
        display.verbose("server {0} is accessible".format(i))
  if bad != []:
    display.error("There are some servers accessible".format(test[i]))



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
      display.debug("Server {0} is NOT running target daemon".format(i))
    else:
      display.debug("Server {0} is running target daemon".format(i))
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
  queue=local.cmd('roles:ROLE_GEO','file.find',['/journal/accepted/','name=geosync.*'],expr_form="grain")
  srv=queue.keys()[0]
  qfiles=queue[srv]
  if len(qfiles) != 0:
    display.error("Journal queue is not empty, {0} files queued".format(len(qfiles)))
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
    f=str(status["metrics"]["total_failed_operations"]["value"])
    transfert=t.encode('utf-8')
    failures=int(f.encode('utf-8'))
    display.info("Transfert in progress {0}".format(transfert))
    if failures != 0:
      display.error("failed operation(s) found : {0} error(s)".format(failures))
    else:
      display.info("No failed operations")
  else:
   display.error("Checking GEO TARGET daemon transfert queue")

def main():
  disable_proxy()
  check_server_status()
  georole=get_geo_host_processes()
  verify_geo_host_processes(georole)
  #display.debug(georole)
  check_journal_entries(georole)
  get_cdmi_host_process(georole)
  get_cdmi_journal_mount()
  check_replication_status(georole,target=args.target)
  display.debug(georole)

if __name__ == '__main__':
  main()
else:
  print "loaded"

