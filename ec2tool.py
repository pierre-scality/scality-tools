#!/bin/python3 

import boto3
import argparse 
import re

REGION='ap-northeast-1'
OWNER='pierre.merle@scality.com'

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
  parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''
  Display and start ec2 instances
  ec2tools.py                                 => No args display all machines for a given owner (hardcoded for now)
  ec2tools.py start <expr>                    => Start machines matching pattern for a given owner (hardcoded for now)
        --> expr is a string that will be matched against the instance name tag
''')
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='It will display the request to repd')
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

  def query_all(self):
    display.debug("enter ec2query_all")
    display.info("Getting instances list")
    response = self.ec2.describe_instances()
    return(response)

  def ec2kickstart(self,list,ask=True):
    l=""
    tostart=[]
    count=0
    if ask: 
      for i in list:
        tostart.append(i[0])
        if count == 0:
          l+="{}".format(i[1])
        else:
          l+=" {}".format(i[1])
        count+=1
      display.info("Do you want to start this {} vm(s) ? (ctrl C to abort)\n{}\n".format(count,l))
      answer=input()
      s=self.ec2.start_instances(InstanceIds=tostart)
      display.debug("Result {}".format(s))
    exit() 
  
  def ec2start(self,instances,pattern):
    display.debug("Start instance")
    display.verbose("Starting machines with pattern {}".format(pattern))
    tostart=[]
    for i in instances:
      name=instances[i]['Name']
      display.debug("matching {} {}".format(pattern,name))
      if re.search(pattern,name):
        tostart.append((i,name))
    self.ec2kickstart(tostart)


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
      t=extract_tag(e['Tags'],tag_query)
      for e in t.keys():
        d[id][e]=t[e]
      if owner:
        d=strip_owner(d,OWNER)
  return(d)
    
 
def display_result(dict):
  maxl=20
  for e in dict:
    if 'owner' in dict[e].keys():
      if len(dict[e]['Name']) > maxl:
        maxl=len(dict[e]['Name'])
       
  for e in dict:
    if 'owner' not in dict[e].keys():
      display.verbose("error {}".format(e))
      continue
    if dict[e]['owner'] == OWNER:
      str="instance {} State : {} Name : {:{L}} Owner : {} Autostop : {}".format(e,dict[e]['State'],dict[e]['Name'],dict[e]['owner'],dict[e]['lifecycle_autostop'],L=maxl)
      display.raw(str)

def action(cli,instances,ec2):
  if cli == []:
    display_result(instances)
    exit(0)
  elif cli[0] == 'start':
    if len(cli) < 2:
      display.fatal("With start you need to speficy a pattern")
    ec2.ec2start(instances,cli[1])
    exit(0)
  else:
      display.fatal("Unknow param {}".format(cli))
      

def main():
  display.debug("cli {}".format(cli))
  ec2=MyEc2()
  rez=ec2.query_all()
  instances=parse_result(rez)
  action(cli,instances,ec2)

if __name__ == '__main__':
  main()
else:
  print("loaded")

