#!/usr/bin/python

import os
import sys
import salt.client
import salt.config
from datetime import datetime
import requests
import json


local = salt.client.LocalClient()
journal='/journal'

def p(arg,bebug=False):
  print arg

# Checking process on geo hosts 
p("Checking GEO connector processes")
source=local.cmd('roles:ROLE_GEO','service.status',['uwsgi'],expr_form="grain")
for i in source.keys():
  #print source,i,source[i]
  if source[i] == False:
    p("Server {0} is NOT running source daemon".format(i))
  else:
    p("Server {0} is running source daemon".format(i))
target=local.cmd('roles:ROLE_GEO','service.status',['scality-sfullsyncd-target'],expr_form="grain")
for i in target.keys():
  #print target,i,source[i]
  if target[i] == False:
    p("Server {0} is NOT running target daemon".format(i))
  else:
    p("Server {0} is running target daemon".format(i))


#salt '*' file.file_exists /etc/passwd
geosync=local.cmd('roles:ROLE_CONN_CDMI','file.file_exists',['/run/scality/connectors/dewpoint/config/general/geosync'],expr_form="grain")
for i in geosync.keys():
  #print target,i,source[i]
  if geosync[i] == False:
    p("Server {0} is NOT configured for journal".format(i))
  else:
    #salt '*' file.contains => does not work with true as arg
    geojournalon=local.cmd(i,'cmd.run',['cat /run/scality/connectors/dewpoint/config/general/geosync'])
    if geojournalon[i] == 'true':
      p("Server {0} is running geo journal".format(i))
    else:
      p("Server {0} is NOT running geo journal".format(i))
      

# salt.modules.mount.is_mounted(name)
mount=local.cmd('roles:ROLE_CONN_CDMI','file.is_mounted',[journal],expr_form="grain")
for i in mount.keys():
  if mount[i] == False:
    p("Server {0} is NOT mounting journal".format(i))
  else:
    #salt '*' file.contains => does not work with true as arg
    geojournalon=local.cmd(i,'cmd.run',['cat /run/scality/connectors/dewpoint/config/general/geosync'])
    if geojournalon[i] == 'true':
      p("Server {0} is using geo journal".format(i))
    else:
      p("Server {0} is NOT using geo journal".format(i))

#replication status
for i in target.keys():
  if target[i] == True:
    url="http://{0}:8381/status".format(i)
    r = requests.get(url)
    if r.status_code != '200':
      #print(r.headers)
      #print(r.text)
      status=json.loads(r.text)
      s=str(status["metrics"]["transfers_in_progress"]["value"])
      transfert=s.encode('utf-8')
      p("Transfert in progress {0}".format(transfert))
    else:
      p("Error querying target daemon")
