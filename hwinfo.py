#!/usr/bin/python

import os
from datetime import datetime
import argparse
import salt.client
import salt.config
import salt.runner 

parser = argparse.ArgumentParser(description="Check server's GEO replication status")
parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target daemon to check queue')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')


local = salt.client.LocalClient()
args,cli=parser.parse_known_args()

def disable_proxy():
  done=0
  for k in list(os.environ.keys()):
    if k.lower().endswith('_proxy'):
      del os.environ[k]
      done=1
  if done != 0:
    display.debug("Proxy has been disabled")

serverinfo=["nodename","productname","mem_total","os","osrelease"]
hdd=["rot_count","rot_size"]
sdd=["ssd_count","ssd_size"]

def main():
  disable_proxy()
  target=args.target[0]
  grains=local.cmd(args.target[0],'grains.items')
  grains=grains[target]
  for i in serverinfo:
    print "{0} : {1}".format(i,grains[i])

  print "#disk : {0} size : {1}".format(grains["rot_count"],grains["rot_size"]/grains["rot_count"]/10e11)  
  print "#ssd : {0} size : {1}".format(grains["ssd_count"],grains["ssd_size"]/grains["ssd_count"]/10e11)  
  

if __name__ == '__main__':
  main()
else:
  print "loaded"

