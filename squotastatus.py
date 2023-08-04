#!/usr/bin/python3

import os
import sys
from datetime import datetime
import yaml
import requests
import json
import argparse
import salt.client
import salt.config
import salt.runner 

QUOTA=('groups','users','volume')
DEFAUTQ='volume'

try:
  parser = argparse.ArgumentParser(description="Check server's process status")
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-p', '--port', nargs=1, const=None ,help='User this port for remote curl')
  parser.add_argument('-q', '--quota', nargs=1, default=DEFAUTQ ,help='Type of quota in need in : '+str(QUOTA))
  parser.add_argument('-t', '--target', nargs=1, required=True,help='Specify the salt target. Use G@ in front of the target to target a grains (roles only). use , if you want to use a list and do not mix @G and minions')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')
  args=parser.parse_args()
except SystemExit:
  bad = sys.exc_info()[1]
  parser.print_help(sys.stderr)
  exit(9)

class Msg():
  def __init__(self,level='info'):
    self.level=level
    self.valid=['info','debug','verbose','warning']

  def set(self,level):
    print("{0:15} : {1}".format('INFO','Setting loglevel to '+level))
    if level not in self.valid:
      self.display("not a valid level {0}".format(level))
      return(9)
    self.level=level

  def get(self):
    return self.level

  def verbose(self,msg,label=None):
    if self.level != 'info':
      if label != None:
        header=label
      else:
        header='VERBOSE'
      print("{0:15} : {1}".format(header,msg))

  def info(self,msg,label=None):
    if label != None:
      header=label
    else:
      header="INFO"
    print("{0:15} : {1}".format(header,msg))
  
  def error(self,msg,fatal=False):
    header="ERROR"
    print("{0:15} : {1}".format(header,msg))
    if fatal == True:
      exit(9)
  
  def warning(self,msg,fatal=False):
    header="WARNING"
    print("{0:15} : {1}".format(header,msg))
    if fatal:
      exit(9)
  
  def raw(self,msg):
    print(msg)

  def debug(self,msg):
    if self.level == "debug":
      header="DEBUG"
      print("{0:15} : {1}".format(header,msg))

  def showlevel(self):
    print("Error level is {0} : ".format(self.level))

display=Msg('info')


#args = parser.parse_args()
args,cli=parser.parse_known_args()
if args.verbose == True:
  display.set('verbose')
if args.debug==True:
  display.set('debug')

pepper = salt.client.LocalClient()

class saltConn():
  def __init__(self,target,quotatype):
    self.target=target
    self.targettype="list"
    self.port='10200'
    self.url='http://127.0.0.1:'+self.port
    self.quotatype=quotatype[0]
    self.food={} # salt call results dict
    self.verifyTarget()
    self.runCmd()
    self.parseResult()

  def verifyTarget(self):
    dummy=[]
    self.target=self.target[0].split(',')
    if len(self.target) == 1:
      if self.target[0][:2] == 'G@':
        display.debug("argument is a role : {}".format(self.target[0][2:]))
        self.targettype="grain"
        self.target='roles:'+self.target[0][2:]
    return()
    
    for i in self.target[0].split(','):
      if i[0][:2] == 'G@':
        display.error("Cannot mix minions name and roles or use several roles",fatal=True)
      else:
        dummy.append(i)
    self.target=dummy 
    
  def runCmd(self):
    #cat=('groups','users','vol')
    #if self.quotatype not in cat:
    #  display.error("quota type must be in {}, got {}".format(cat,self.quotatype),fatal=True)
    query='http://127.0.0.1:10200/fs/quota/'+self.quotatype
    display.debug("Running salt against {} {}".format(self.target,query))
    self.food=pepper.cmd(self.target,'http.query',[query],tgt_type=self.targettype,full_return=True)
    display.debug("Salt call result {}".format(self.food))
    

  def parseResult(self):
    #print(self.food)
    for s in self.food.keys():
      display.debug(self.food[s])
      if self.food[s]['retcode'] != 0:
        display.verbose("minion {} did not answer properly".format(s,self.food[s]))
        continue
      display.raw("{} : {}".format(s,self.food[s]['ret']['body'])) 



def disable_proxy():
  done=0
  for k in list(os.environ.keys()):
    if k.lower().endswith('_proxy'):
      del os.environ[k]
      done=1
  if done != 0:
    display.debug("Proxy has been disabled")

def main():
  disable_proxy()
  print(args)
  display.debug("params {}".format(args))
  conn=saltConn(args.target,args.quota)

if __name__ == '__main__':
  main()
else:
  print("loaded")

