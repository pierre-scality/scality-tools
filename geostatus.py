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
parser.add_argument("-r","--role",help="Specify role (not yet used)")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target daemon to check queue')


# Salt client breaks logging class.
# Simple msg display class
class Msg():
  def __init__(self,level='info'):
    self.level=level
    self.valid=['info','debug']

  def set(self,level):
    print "{0:15} : {1}".format('INFO','Setting loglevel to debug')
    if level not in self.valid:
      self.display("not a valid level {0}".format(level))
      return(9)
    self.level=level

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
if args.debug==True:
  display.set('debug')

local = salt.client.LocalClient()
journal='/journal'

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
    display.info("Server {0} is GEO TARGET".format(dict['target']))
  elif target > 1:
    display.error("There is more than 1 server running GEO SOURCE")
  if source == 0 and target == 0:
    display.error("There is neither GEO SOURCE or TARGET daemon running")


#salt '*' file.file_exists /etc/passwd
def get_cdmi_host_process():
  display.info("Checking CDMI connector journal configuration")
  geosync=local.cmd('roles:ROLE_CONN_CDMI','file.file_exists',['/run/scality/connectors/dewpoint/config/general/geosync'],expr_form="grain")
  for i in geosync.keys():
  #print target,i,source[i]
    if geosync[i] == False:
      display.error("Server {0} is NOT configured for journal".format(i))
    else:
      #salt '*' file.contains => does not work with true as arg
      geojournalon=local.cmd(i,'cmd.run',['cat /run/scality/connectors/dewpoint/config/general/geosync'])
      if geojournalon[i] == 'true':
        display.debug("Server {0} is running geo journal".format(i))
      else:
        display.debug("Server {0} is NOT running geo journal".format(i))


# salt.modules.mount.is_mounted(name)
def get_cdmi_journal_mount():
  display.info("Checking CDMI/GEO connector journal mountpoint")
  for role in ["ROLE_CONN_CDMI","ROLE_GEO"]:
    mount=local.cmd('roles:'+role,'file.is_mounted',[journal],expr_form="grain")
    for i in mount.keys():
      if mount[i] == False:
        display.error("Server {0} is NOT mounting journal".format(i))
      else:
        display.info("Server {0} is mounting journal".format(i))


def check_replication_status(dict,target=None):
  if target == None:
    target=dict['target']
  if len(target) > 1:
    display.error("Too much target hosts {0}".format(target))
    return(3)
  if len(target) == 0:
    display.info("No target host on this site")
    return(0)
  target=target[0]
  display.info("Checking GEO TARGET daemon transfert queue")
  url="http://{0}:8381/status".format(target)
  display.debug("Using target server url {0}".format(url))
  try:
    r = requests.get(url)
  except requests.exceptions.RequestException as e:  # This is the correct syntax
    display.error("Error connecting to GEO TARGET daemon : {0}".format(e))
    return(8)
  if r.status_code == 200:
    #print(r.headers)
    #print(r.text)
    status=json.loads(r.text)
    s=str(status["metrics"]["transfers_in_progress"]["value"])
    transfert=s.encode('utf-8')
    display.info("Transfert in progress {0}".format(transfert))
  else:
    display.error("Error querying target daemon")

def main():
  georole=get_geo_host_processes()
  #display.debug(georole)
  verify_geo_host_processes(georole)
  get_cdmi_host_process()
  get_cdmi_journal_mount()
  check_replication_status(georole,target=args.target)

if __name__ == '__main__':
  main()
else:
  print "loaded"

