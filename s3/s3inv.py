#!/bin/python3

import argparse
import configparser

import salt.client
import salt.config
import ipaddress

DEFAULT="/srv/scality/s3/s3-offline/federation/env/s3config/inventory"

try:
  parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''
  s3inv.py <inventory file>
  Display inventory file based information. 
  By default it will display WSB servers and Majority/Minority setting if any
  Use -a to add md or s3 with -a "s3 md"
  You can also set salt grains corresponding to the inventory.
  set will set the grains, get read the grains and dry will show what a set would do
  s3inv.py -s set
''')
  parser.add_argument('-a', '--argument', dest='argument', default=None ,help='Specify which section you want to see. Take list and display if section exists')
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-l', '--list', dest='list', action="store_true", default=False ,help='list sections of the inventory')
  parser.add_argument('-s', '--salt', dest='salt', default=None, choices=['set', 'get', 'dry'], help='manage salt grains from inventory can be set/get/dry')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='It will display the request to repd')
except SystemExit:
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
    if fatal:
      exit(9)

  def warning(self,msg,fatal=False):
    header="WARNING"
    print("{0:15} : {1}".format(header,msg))
    if fatal:
      exit(9)

  def debug(self,msg):
    if self.level == "debug":
      header="DEBUG"
      print("{0:15} : {1}".format(header,msg))

  def raw(self,msg):
      print("{0}".format(msg))


  def showlevel(self):
    print("Error level is {0} : ".format(self.level))


display=Msg('info')

args,cli=parser.parse_known_args()
if args.verbose == True:
  print('v')
  display.set('verbose')
if args.debug==True:
  print('d')
  display.set('debug')

if cli == []:
  file=DEFAULT
else:
  file=cli[0]


class Inventory():
  def __init__(self,args,invfile="/srv/scality/s3/s3-offline/federation/env/s3config/inventory"):
    self.invgrains={'wsb':'ROLE_S3_WSB','runners_s3':'ROLE_S3_EP','runners_metadata':'ROLE_S3_MD'}
    self.s3roles={}
    self.server={}
    self.invfile=invfile
    self.fd=self.open_env()
    self.inv={}
    self.list=args.list
    self.argument=args.argument
    if args.salt != None:
      self.salt=args.salt
      self.process_grains()
 
  def process_grains(self):
    self.parse_env()
    print(self.inv['default'])
    invlist={}
    for i in self.inv['default']:
      l=i.split()
    target='*'
    
    display.verbose("process grains for {}".format(target))
    saltquery = salt.client.LocalClient()
    self.grains=saltquery.cmd(target,'grains.items') 
    for i in self.grains.keys():
      print("{} -> {}".format(i,self.grains[i]['ip4_interfaces']))
    self.get_role_target()
    exit(0)

  # for each host get the grain(s) to set
  # host is the ansiblehost
  def get_role_target(self):
    for k in self.inv.keys():
      print(k)
      print(self.invgrains.keys())
      if k in self.invgrains.keys():
        self.s3roles[self.invgrains[k]]=self.inv[k]
        print(self.s3roles)
    for i in self.s3roles.keys():
      print("{} : {}".format(i,self.s3roles[i]))
 
  def open_env(self):
    display.verbose("Opening {}".format(self.invfile))
    try:
      fd=open(self.invfile)
    except FileNotFoundError:
      display.error("Can't open file {}".format(self.invfile))
      exit(9)
    return(fd)

  def parse_env(self):
    sect='default'
    self.inv[sect]=[]
    self.inv['wsb']=[]
    for line in self.fd.readlines():
      if line[0] == "#":
        continue
      if len(line) == 1:
        continue
      if line[0] == '[':
        sect=line[1:].split(']')[0].rstrip()
        display.debug("New section {}".format(sect))
        self.inv[sect]=[]
        continue
      else:
        display.debug("add in section {} :  {}".format(sect,line.rstrip()))
        entry=line.rstrip()
        if entry in self.server.keys():
          display.debug("Matched {} and {}".format(entry,self.server[entry]))
          entry="{}:{}".format(entry,self.server[entry]) 
        self.inv[sect].append(entry) 
      if sect == 'default':
        explode=line.split()
        s=explode[0]
        n=explode[1].split("=")[1]
        display.debug("s3 name : {} realname : {}".format(s,n))
        self.server[s]=n
        if s[:3] == 'wsb':
          display.debug("Adding {} to wsb list {}".format(n,self.inv['wsb']))
          self.inv['wsb'].append("{}:{}".format(s,n))
          #self.wsb.append(n)
    display.debug("sections found {}".format(self.inv.keys()))
    if self.list:
      for i in self.inv.keys():
        display.raw(i)
      exit(0)
    return()

  def display_inv(self,section=[]): 
    display.debug("Entering display_inv keys {} in {}".format(section,self.inv.keys()))
    for sect in self.inv.keys():
      if section == [] or sect in section:
        print("[{}]".format(sect))
        for val in self.inv[sect]:
          print(val)
    return(0)

  def display_args(self):
    display.verbose("Display args of {}".format(self.argument))
    shortcut={ "md":"runners_metadata", "s3":"runners_s3"}
    if self.argument == None:
      return(None)
    l=self.argument.split()
    for i in l:
      if i in shortcut.keys():
        l.remove(i)
        l.append(shortcut[i])
    self.display_inv(l)  

  def display_wsb(self):
    display.debug("Wsb server list : {}".format(self.inv['wsb'])),
    wsbstr=""
    for i in self.inv['wsb']:
      if wsbstr != "":
        wsbstr=wsbstr+","+i
      else:
        wsbstr+=i
    display.raw("[WSB]\n{}".format(wsbstr))

  def get_grains(self,target,grains):
    display.verbose("Checking grains {0} on {1}".format(grains,target))
    resp=local.cmd(target,'grains.get',[grains])
    display.debug('response check {0} {1}'.format(target,resp))
    return(resp)


def main(file):
  inventory=Inventory(args)
  inventory.parse_env()
  #inventory.display_inv(["minority","majority"])
  #inventory.display_inv(["wsb"])
  inventory.display_args()
if __name__ == '__main__':
  main(file)
else:
  print("loaded")

