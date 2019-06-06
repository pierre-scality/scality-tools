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


try:
  parser = argparse.ArgumentParser(description="Check server's process status")
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  #parser.add_argument('-t', '--target', nargs=1, const=None ,help='Specify target daemon to check queue')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')
  parser.add_argument('-L', '--leaders', dest='leaders', action="store_true", default=False ,help='Display all 8 raft sessions leaders')
  parser.add_argument('-b', '--bucket', nargs=1, const=None, help='Display leader for a given bucket')
  parser.add_argument('--zkcount', dest='zkcount',default=5 ,help='Specify number of ZK hosts')
  args=parser.parse_args()
except SystemExit:
  bad = sys.exc_info()[1]
  #print(bad)
  parser.print_help(sys.stderr)
  exit(9)


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
    print "Error level is {0} : ".format(self.level)

display=Msg('info')


#args = parser.parse_args()
args,cli=parser.parse_known_args()
if args.verbose == True:
  display.set('verbose')
if args.debug==True:
  display.set('debug')

#display.showlevel()

def disable_proxy():
  done=0
  for k in list(os.environ.keys()):
    if k.lower().endswith('_proxy'):
      del os.environ[k]
      done=1
  if done != 0:
    display.debug("Proxy has been disabled")

class Raft():
  def __init__(self):
    self.server="sghk1-node1"

  def query_url(self,url):
    display.verbose("Querying url {}".format(url))
    #url="http://{0}/api/v0.1/es_proxy/_cluster/health?pretty".format(target)
    try:
      r = requests.get(url)
    except requests.exceptions.RequestException as e:
      display.error("Error connecting to supervisor on localhost: {0}".format(target))
      display.debug("Error is  : \n{0}\n".format(e))
      return(1)
    if r.status_code == 200:
      #status=json.loads(r.text)
      return(r.text)
    else:
      display.error("You request return non 200 response {0} for \n {1}".format(r.status_code,url))
      return(r.status_code)
  
  def getBucketInformation(self,bucket):
    display.verbose("getBucketInformation {0}".format(bucket))
    url="http://"+str(self.server)+":9000/default/informations/"+str(bucket)
    out=self.query_url(url)
    struct=json.loads(out)
    display.debug("Bulk output getBucketLeader \n {}\n".format(struct))
    leader=[]
    follower=[]
    for i in range(0,len(struct)):
      if struct[i]['isLeader'] == True: 
        leader.append(struct[0]['ip'])
      else:
        follower.append(struct[0]['ip'])
    print "Leader : {0}".format(leader)  
    print "Follower : {0}".format(follower) 
  
  def getBucketLeader(self,bucket):
    url="http://"+str(self.server)+":9000/default/leader/"+str(bucket)
    display.verbose("Querying {0}".format(url))
    out=self.query_url(url)
    struct=json.loads(out)
    display.debug("Bulk output getBucketLeader {}".format(struct))
    leader=struct['host']
    url="http://"+str(self.server)+":9000/_/buckets/"+str(bucket)+"/id"
    out=json.loads(self.query_url(url))
    print "Leader {} : Raft session {}".format(leader,out)

  def getAllLeaders(self):
    for i in range(0,7):
      display.debug("http://"+str(self.server)+":9000//_/raft_sessions/"+str(i)+"/leader")
      out=self.query_url("http://sghk1-node1:9000/_/raft_sessions/"+str(i)+"/leader")
      out=json.loads(out)
      print "Session {0} : Leader {1}".format(i,out['host'])

 
def main():
  raft=Raft()
  disable_proxy()
  if args.bucket != None:
    raft.getBucketLeader(args.bucket[0])
    # Not sure how to interpret that 
    raft.getBucketInformation(args.bucket[0])
  if args.leaders == True:
    raft.getAllLeaders()



if __name__ == '__main__':
  main()
else:
  print "loaded"

