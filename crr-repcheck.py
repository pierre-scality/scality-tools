#!/usr/bin/python

import os
import sys
import subprocess
from datetime import datetime
import json
import argparse


try:
  parser = argparse.ArgumentParser(description="Check server's process status")
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-e', '--endpoint', default="127.0.0.1" , help='Set the endpoint')
  parser.add_argument('-p', '--profile', default="default" , help='Set the aws profile')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='Set script in VERBOSE mode ')
  args=parser.parse_args()
except SystemExit:
#  bad = sys.exc_info()[1]
#  parser.print_help(sys.stderr)
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

class S3op():
  def __init__(self):
    self.server="127.0.0.1"
    #self.aws='cmd='/srv/scality/s3/s3-offline/venv/bin/aws --endpoint=http://10.100.3.42 --profile pierre s3api get-bucket-replication --bucket newbucketwithdata'
    self.aws=cmd='/srv/scality/s3/s3-offline/venv/bin/aws'
    self.endpoint=self.server
    self.profile='default'
    self.ssl = False

  def setEndpoint(self,server):
    display.verbose("Using {0} as acces point".format(server))
    if self.ssl == False:
      self.endpoint="http://{}".format(server)
    else:
      self.endpoint="https://{}".format(server)
  
  def setProfile(self,profile):
    display.debug("Setting profile to {}".format(profile))
    self.profile = profile

  def runquery(self,op,*option):
    display.debug("Running query {}".format(op))
    cmd="{} --endpoint {}".format(self.aws,self.endpoint)
    if self.profile != 'default':
      cmd="{} --profile {}".format(cmd,self.profile)
    cmd="{} {}".format(cmd,op)
    display.verbose("Final query {}".format(cmd))
    p=subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout,stderr=p.communicate()
    #print("ERR {} OUT {}".format(stderr,stdout))
    rc=p.returncode
    if rc == None:
      display.error("Return code is None which probably means that command failed")
      exit(9)
    if rc != 0:
      display.verbose("cmd did return non 0 rc : {}".format(rc))
      display.debug("std err : {}".format(stderr))
      stdout=stderr
    return(stdout)
      
   
  def crr_status(self,bucketlist):
    display.debug("Entering crr_status with bucket list")
    crrenabled=[]
    crrdisabled=[]
    for b in bucketlist:
      cmd='s3api get-bucket-replication --bucket {}'.format(b)
      rez=self.runquery(cmd)
      display.debug("Check bucket replication status {}".format(cmd))
      try: j=json.loads(rez) 
      except ValueError:
        display.info("Bucket {} does not have replication configuration or not exist".format(b))
        display.debug("Output : {}".format(rez))
        crrdisabled.append(b)
        continue
      try: rez=j['ReplicationConfiguration']['Rules'][0]['Status']
      except KeyError:
        display.error('Key {} does not exist in {}'.format(operation,j))
        rez="Disable"
        #exit(9)
      if rez == "Enabled":
        crrenabled.append(b)
        display.info("Bucket {} has replication enabled".format(b))
      else:
        crrdisabled.append(b)
        display.verbose("Bucket {} has NOT replication enabled".format(b))
    display.verbose("Enabled bucket {}".format(crrenabled)) 
    display.verbose("Disabled bucket {}".format(crrdisabled)) 
    return(j)
     
  def bucket_list(self,show=False):
    display.debug("entering display_buckets")
    rez=self.runquery('s3api list-buckets')
    try: j=json.loads(rez)
    except ValueError: 
      display.error("Can not get bucket list because : {}".format(rez))
      exit(9)
    if not 'Buckets' in j:  
      display.error("It doesn't looks like a buket list {}".format(blist))
      exit(9)
    l=j['Buckets']
    display.verbose("entering display_buckets {}".format(l))
    out=[]
    for i in l:
      out.append(i['Name'].encode("utf-8"))
    if show == True:
      display.info("Bucket list is {}".format(out))
    return(out)
   
def main():
  S3=S3op()
  S3.setEndpoint(args.endpoint)
  S3.setProfile(args.profile)
  disable_proxy()
  l=S3.bucket_list(show=True)
  r=S3.crr_status(l)


if __name__ == '__main__':
  main()
else:
  print "loaded"

