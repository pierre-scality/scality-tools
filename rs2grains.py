#!/usr/bin/python
# vim: tabstop=2 shiftwidth=2 expandtab
 
import os
import sys
from datetime import datetime
import argparse
import salt.client
import salt.config

parser = argparse.ArgumentParser(description="Check server's GEO replication status")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')
parser.add_argument('-t', '--target', nargs=1, const=None, required=True, help='MANDATORY Specify target host')
parser.add_argument('-c', '--count', nargs=1, const=None, help='MANDATORY Interface count for RS2 connector')
parser.add_argument('-s', '--set', dest='set', action="store_true", default=False, help='If this argument is used it will set the grains RS2IF_X with the order values of secondary iface from scality:prod_iface')


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


def get_grains(target,grains):
  display.verbose("Checking grains {0} on {1}".format(grains,target))
  resp=local.cmd(target,'grains.get',[grains])
  display.debug('response check {0} {1}'.format(target,resp))
  return(resp)

def get_network_settings(target):
  display.verbose("Checking network settings on {0}".format(target))
  resp=local.cmd(target,'network.interfaces')
  return(resp)

def get_iface(target,iface="scality:prod_iface",type="pillar"):
  display.verbose("Checking interface {0}".format(target))
  resp=local.cmd(target,type+'.get',[iface])
  return(resp)

def get_secondary_sorted(dict,iface):
  if not 'secondary' in dict.keys():
    display.error("No secondary interface found {0} on interface {1}".format(dict.keys(),iface))
    exit(9)
  temp={}
  list=[]
  for this in dict['secondary']:
    indice=this['label'].split(':')[1]
    addr=this['address']
    temp[indice]=addr
  for i in sorted(temp.keys()):
    display.debug('found secondary iface #{0} add {1}'.format(i,temp[i]))
    list.append(temp[i])
  return(list)    

def process_rs2if_grains(target,list,count,run):
  display.verbose("Getting all the grains from the server {0}".format(target))
  resp=local.cmd(target,'grains.items')
  if target != resp.keys()[0]:
    display.error("something bad happends getting grains") 
    display.debug("Dumping output : \n {0}".format(resp))
  for i in range(1,count+1):
    j=i-1
    grain="RS2IF_"+str(i)
    if grain in resp[target].keys():
      display.info("Found grain {0} value {1}".format(grain,resp[target][grain]))
      if resp[target][grain] != list[j]:
        display.warning("grains {0} is set to {1} but should be {2}".format(grain,resp[target][grain],list[j]))
      if run == True:
        resp=local.cmd(target,'grains.setval',[grain,list[j]])
        if resp[target][grain] != list[j]:
          display.warning("It looks like grains in not set as expeced please check")
    else:
      display.info("No grain {0}".format(grain))
      display.verbose("if set was true it would have set grain {0} to {1}".format(grain,list[j]))
 
  
  

def main():
  display.debug("running with opts {0} {1}".format(args,cli))
  target=args.target[0]
  iface=get_iface(target)[target]
  if iface  == '':
    display.error("Cant find target interface scality:prod_iface")
    exit(9)
  else:
    display.debug("Found target interface : {0}".format(target))
  network=get_network_settings(target)
  display.debug("Network settings {0}".format(network[target]))
  if not iface in network[target].keys():
    display.error("Cannot find interface {0} in network settings".format(iface))
  else:
    display.debug("interface {0} in network settings : {1}".format(iface,network[target].keys()))
  secondary_list=get_secondary_sorted(network[target][iface],iface) 
  process_rs2if_grains(target,secondary_list,int(args.count[0]),args.set)

if __name__ == '__main__':
  local = salt.client.LocalClient()
  main()
