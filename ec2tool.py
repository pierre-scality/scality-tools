#!/bin/python3 

import boto3
import argparse 
import re
import os

# local params
SUPPORTEDREGION=['eu-north-1','us-west-2','ap-northeast-1','ap-southeast-2']
REGION='ap-northeast-1'
OWNER='pierre.merle@scality.com'

try:
  REGION=os.environ['MYREGION']
except KeyError:
  REGION=REGION

try:
  REGION=os.environ['MYOWNER']
except KeyError:
  OWNER=OWNER





# script variables
EC2ACTION=('start','stop','terminate')

# Generic class for display messages with level
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

display=Msg()

try:
  prgdesc='''
  Display and trigger actions against ec2 instances
  ec2tools.py                                 => No args display all machines for a given owner (hardcoded for now)
  ec2tools.py <action> <expr>                    => Start machines matching pattern for a given owner (hardcoded for now)
        --> expr is a string that will be matched against the instance name tag
'''
  prgdesc+="\n  Possible action are {}\n".format(EC2ACTION)
  prgdesc+="  Region/User hardcoded you can use env variable MYREGION/MYOWNER.\n  Supported regions are : {}".format(SUPPORTEDREGION)
  parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=prgdesc)
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='verbose mode')
except SystemExit:
  exit(9)

args,cli=parser.parse_known_args()
if args.verbose == True:
  display.set('verbose')
if args.debug==True:
  display.set('debug')


class MyEc2():
  def __init__(self):
    display.debug("init ec2")
    self.ec2 = boto3.client('ec2',REGION)
    self.target = []

  def query_all(self):
    display.debug("enter ec2query_all")
    display.info("Getting instances list")
    response = self.ec2.describe_instances()
    return(response)

  def filter(self,cli,instances):
    if cli == []:
      display_result(instances)
      exit(0)
    elif cli[0]  in EC2ACTION:
      display.debug("Action found {} for {}".format(cli[0],cli,fatal=True))
      if len(cli) < 2:
        display.error("With {} you need to speficy a pattern".format(cli[0],fatal=True))
      self.ec2filter(instances,cli[1])
      self.ec2action(cli[0])
      exit(0)
    else:
        display.error("Unknow param {}".format(cli),fatal=True)
   
  def ec2action(self,action,ask=True):
    display.debug("ec2action with {}".format(action))
    l=""
    tostart=[]
    count=0
    if ask: 
      for i in self.target:
        tostart.append(i[0])
        if count == 0:
          l+="{}".format(i[1])
        else:
          l+=" {}".format(i[1])
        count+=1
      #display.info("Do you want to {} this {} vm(s) ? (ctrl C to abort)\n{}\n".format(action,count,l))
      if count == 0:
        display.info("No machine selected")
        exit(0)
      msg=("Do you want to {} this {} vm(s) ? (ctrl C to abort)\n{}".format(action,count,l))
      answer=askme(msg)
      if action == 'start':
        s=self.ec2.start_instances(InstanceIds=tostart)
      elif action == 'stop':
        s=self.ec2.stop_instances(InstanceIds=tostart)
      elif action == 'terminate':
        #display.info("Do you really want to terminate {}.\nType 'yes' to confirm : ".format(tostart))
        question="Do you really want to terminate {}.\nType 'yes' to confirm : ".format(tostart)
        confirm=askme(text=question)
        if confirm == 'yes':
          s=self.ec2.terminate_instances(InstanceIds=tostart)
        else:
          display.info("Termination aborted")
          exit(0)
      else:
        display.error("Action not implemented",fatal=True)
      display.debug("Result {}".format(s))
    exit() 
  
  def ec2filter(self,instances,pattern,field='Name'):
    display.debug("Filter instance")
    for i in instances:
      name=instances[i][field]
      display.debug("matching {} {}".format(pattern,name))
      if re.search(pattern,name):
        self.target.append((i,name))

def askme(text="",thanks='ByeBye'):
  try:
    answer=input("{:15} : {} : ".format('QUERY',text))
  except KeyboardInterrupt:
    print(thanks)
    exit(0)
  return(answer) 

def extract_tag(tags,query):
  display.debug("enter extract_tag")
  r={}
  for e in tags:
    if e['Key'] in query:
      r[e['Key']]=e['Value']
  return(r)

def strip_owner(d,owner):
  out={}
  for id in d.keys():
    if 'owner' in d[id].keys():
      if d[id]['owner'] == OWNER:
        out[id]=d[id]
  return(out)  

def parse_result(rez,owner=True):
  display.debug("enter parse_result")
  d={}
  t={}
  tag_query=['owner','Name','lifecycle_autostop']
  instances=rez['Reservations']
  for i in instances:
    z=i['Instances']
    for e in z:
      display.debug("this key : {}".format(e.keys()))
      id=e['InstanceId']
      d[id]={}
      d[id]['State']=e['State']['Name'] 
      if 'PublicIpAddress' in e.keys():
        d[id]['PublicIpAddress']=e['PublicIpAddress']
      t=extract_tag(e['Tags'],tag_query)
      for tag in t.keys():
        d[id][tag]=t[tag]
      if owner:
        d=strip_owner(d,OWNER)
  return(d)
    
 
def display_result(dict):
  sdict={}
  maxl=20
  for e in dict:
    if 'owner' in dict[e].keys():
      if len(dict[e]['Name']) > maxl:
        maxl=len(dict[e]['Name'])
       
  for e in dict:
    if 'owner' not in dict[e].keys():
      display.verbose("error {}".format(e))
      continue
    display.debug("Instance {}".format(dict[e]))
    if dict[e]['owner'] == OWNER:
      str="{} State : {:10} Name : {:{L}} Owner : {} Autostop : {}".format(e,dict[e]['State'],dict[e]['Name'],dict[e]['owner'],dict[e]['lifecycle_autostop'],L=maxl)
      if 'PublicIpAddress' in dict[e].keys():
        str="{} : EIP {}".format(str,dict[e]['PublicIpAddress'])
      sdict[dict[e]['Name']]=str

  for e in sorted(sdict.keys()):
    display.raw(sdict[e])
     

def main():
  display.debug("cli {}".format(cli))
  ec2=MyEc2()
  rez=ec2.query_all()
  instances=parse_result(rez)
  ec2.filter(cli,instances)

if __name__ == '__main__':
  main()
else:
  print("loaded")

