#!/usr/bin/python3

import os
import sys
from datetime import datetime
import requests
import json
import argparse
import salt.client
import salt.config
import salt.runner 
import time


try:
  parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''
  Check server's process status
  mdstat.py <option> <command>
  There are 2 commands type bucket, session and a watch mode to follow a given session
  You need to point an S3 server for the initial request to be done.
  mdstat.py -s server1                        => Display raft sessions with leader
  mdstat.py -s server1 session                => Get the leader for each session 
  mdstat.py -s server1 session <session id>   => Display information about this specific session (from the leader) 
  mdstat.py -s server1 bucket <bucketname>    => Display the raft session for the bucket with servers and seq details
  mdstat.py -s server1 watch  <session id>  <interval>  => Display seq numbers about a give raft session 
''')
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-s', '--server', default="localhost" , help='Display a given raft session menbers')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='It will display the request to repd')
  parser.add_argument('-w', '--wsb', dest='wsb',default=None ,help='Set the WSB ip to add to the query for watch functionality')
  parser.add_argument('-i', '--ignore', dest='ignore',action="store_true", default=False ,help='Ignore connection error.')
  #args=parser.parse_args()
except SystemExit:
#  bad = sys.exc_info()[1]
#  parser.print_help(sys.stderr)
  exit(9)

MD_SUB_SESSION=('bucket')
MD_SUB_BUCKET=('leader')


MD_CMD=('session','bucket','watch')
MD_BUCKET=('leader')
MD_SESSION=('leader','session','bucket')


class Command():
  def __init__(self,arguments,raft):
    self.args=arguments
    self.raft=raft

  def getCmd(self):
    display.debug("Running getCmd with arg {0}".format(self.args))
    if len(self.args) == 0:
      self.raft.getSessionLeaders()
      return(0)
    self.cmd=self.args[0]
    if self.cmd not in MD_CMD:
      display.error("Command is not supported {0}".format(self.cmd))
      exit(1)
    self.remaining=self.args[1:]
    self.filterCmd()
    return(0) 

  def filterCmd(self):
    display.debug("Running filterCmd on {}".format(self.remaining))
    if self.cmd == "session": 
      if len(self.remaining) == 0:
        self.raft.getRaftAll()
        self.raft.displayRaft()
        exit(0)
      else:
        self.doSessionOperation()
    if self.cmd == "bucket":
      if len(self.remaining) == 0:
        display.error("Need argument for command {0} : bucketname and {1}".format(self.cmd,MD_BUCKET))
        exit(9)
      else:
        self.bucket=self.remaining.pop(0)
        try:
          self.query=self.remaining.pop(0)  
        except IndexError:
          out=self.raft.getBucketInformation(self.bucket) 
          if out == None:
            exit(9)
          else:
            exit(0) 
        self.doBucketOperation()
    if self.cmd == "watch":
      self.raft.getRaftAll()
      if len(self.remaining) == 0:
        display.error("You must tell the raft session number")
      rs=int(self.remaining[0])
      if len(self.remaining) == 1:
        self.raft.watchRaft(rs)
      else:
        timer=int(self.remaining[1])
        self.raft.watchRaft(rs,timer)
    return(0) 

  def doBucketOperation(self):
    display.debug("Running doBucketOperation {0} {1}".format(self.bucket,self.query))
    if self.query not in MD_BUCKET:
      display.error("Need operation for bucket {0}".format(self.bucket),fatal=True)
    if self.query == 'leader':
        display.debug("Getting leader for bucket {0}".format(self.bucket))
        out=self.raft.getBucketLeader(self.bucket)
        if out == None:
          exit(9)
        else:
          exit(0) 
    elif self.query == 'leader':
        display.debug("Getting leader for bucket {0}".format(self.bucket))


  def doSessionOperation(self):
    display.debug("Running doSessionOperation {0}".format(self.remaining))
    try:
      number=int(self.remaining[0])
    except ValueError:
      number=-1
    if number != -1:
      self.raft.displaySessionInfo(number)
      exit(0)
    if self.remaining[0] == "bucket":
      if self.remaining.__len__() < 2:
        display.error("Need at least one argument : sessions number",fatal=True)
      self.raft.getSessionBucket(self.remaining[1])
    else:
      display.debug("Nothing to do")
      exit(0)
# Salt client breaks logging class.
# Simple msg display class
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
  def __init__(self,args,raft=-1):
    display.debug("Raft instance creation with {0} {1}".format(args,cli))
    self.server=args.server
    self.raftsession={}
    self.raft=raft
    self.wsb=args.wsb
    self.ignore=args.ignore
    self.RAFTCOUNT=9
    self.RAFTMBR=5

  def setServer(self):
    display.verbose("Using {0} as endpoint".format(self.server))

  def query_url(self,url,fatal=False):
    display.verbose("Querying url {}".format(url))
    try:
      r = requests.get(url)
    except requests.exceptions.RequestException as e:
      if self.ignore:
        display.verbose("Ignore error connecting to : {0}".format(url))
        return(None)
      else:
        display.error("Error connecting to : {0}".format(url))
        display.debug("Error is  : \n{0}\n".format(e))
        exit(1)
    if r.status_code == 200:
      #status=json.loads(r.text)
      return(r.text)
    else:
      display.error("You request return non 200 response {0} for : {1}".format(r.status_code,url))
      if fatal == True:
        exit(9)
      return(None)
  
  def getBucketInformation(self,bucket,full=False):
    display.verbose("getBucketInformation {0}".format(bucket))
    url="http://"+str(self.server)+":9000/default/informations/"+str(bucket)
    out=self.query_url(url)
    if out == None:
      return(False)     
    struct=json.loads(out)
    display.debug("Bulk output getBucketLeader \n {}\n".format(struct))
    leader=[]
    follower=[]
    info={}
    for i in range(0,len(struct)):
      info[struct[i]['ip']]={}
      for key in list(struct[i].keys()):
        if key == 'isLeader':
          if struct[i]['isLeader'] == True: 
            display.debug("leader {}".format(struct[i]))
            leader.append(struct[i]['ip'])
            session=struct[i]['raftSessionId']
          else:
            display.debug("follower {}".format(struct[i]))
            follower.append(struct[i]['ip'])
        else:
          info[struct[i]['ip']].update({key:struct[i][key]})
    display.raw("Leader : {0} (session {1})".format(leader[0],session))
    f=""
    for i in follower:
      f+="{0},".format(i)
    f=f[:-1]
    display.raw("Follower : {0}".format(f))
    #if long == true:
    max=-1
    for ip in list(info.keys()):
      display.raw("Server : {0} aseq {1} cseq {2} vseq {3} bseq {4}".format(ip,info[ip]['aseq'],info[ip]['cseq'],info[ip]['vseq'],info[ip]['bseq']))
    
  def getBucketLeader(self,bucket):
    display.debug("Entering getBucketLeader")
    url="http://"+str(self.server)+":9000/default/leader/"+str(bucket)
    display.verbose("Querying {0}".format(url))
    out=self.query_url(url)
    if out == None:
      return(False)     
    struct=json.loads(out)
    display.debug("Bulk output getBucketLeader {}".format(struct))
    leader=struct['host']
    url="http://"+str(self.server)+":9000/_/buckets/"+str(bucket)+"/id"
    out=json.loads(self.query_url(url))
    print("Leader {} : Raft session {}".format(leader,out))

  def getSessionBucket(self,sessionnb,show=True):
    display.debug("Entering getSessionBucket for session {0}".format(sessionnb))
    if self.isRaftNumber(sessionnb):
      url="http://"+str(self.server)+":9000/_/raft_sessions/"+str(sessionnb)+"/bucket"
      out=self.query_url(url)
    else:
      display.error("Invalid session number {0}".format(sessionnb),fatal=True)
    if show == True:
      display.raw(out)
    return(out)

  def isRaftNumber(self,nb,fatal=True):
    try: 
      sessionnb=int(nb)
    except:
      display.error("{0} is not an integer".format(nb),fatal=True)
    if  sessionnb not in list(range(0,self.RAFTCOUNT)):
      display.error("Raft session number must be bewteen 0 and {0}, got {1}".format(self.RAFTCOUNT-1,sessionnb),fatal=True)
    else:
      display.debug("{0} is a valid raft session number".format(nb))
      return(True) 

  def getSessionLeaders(self,show=True):
    display.debug("Entering getSessionLeaders")
    ret={}
    for i in range(0,self.RAFTCOUNT):
      if self.raft==-1 or self.raft==i:
        out=self.query_url("http://"+self.server+":9000/_/raft_sessions/"+str(i)+"/leader")
        if out == None:
          display.error("getSessionLeaders fails because request did not complete")
          return(99)
        out=json.loads(out)
      ret[i]=out['host']
      if show == True:
        display.raw("Session {0} : Leader {1}".format(i,out['host']))
    return ret
    

  def getRaftSession(self,id):
    url="http://"+str(self.server)+":9000/_/raft_sessions/"+str(id)+"/leader"
    leader=self.query_url(url)
    #leader=json.loads(leader)[0]['host']
    leader=json.loads(leader)
    url="http://"+str(self.server)+":9000/_/raft_sessions/"
    out=self.query_url(url)
    out=json.loads(out)
    print("Members for session {0} (leader is {1}) : ".format(id,leader['host']))
    for el in out[id]['raftMembers']:
      print(el['display_name'],el['site'])

  def getRaftAll(self):
    display.debug("Entering function getRaftAll")
    url="http://"+str(self.server)+":9000/_/raft_sessions/"
    out=self.query_url(url)
    out=json.loads(out)
    for i in out:
      session=i['id']
      display.debug("Adding session {0}".format(session))
      self.raftsession[session]={}
      self.raftsession[session]['connectedToLeader']=i['connectedToLeader']
      self.raftsession[session]['members']={}
      for j in i['raftMembers']:
        # not very elegant but all port should be same
        self.raftsession[session]['port']=j['port']
        self.raftsession[session]['adminport']=j['adminPort']
        host=j['host']
        self.raftsession[session]['members'][host]=j

  def displayRaft(self):
    display.debug("Entering function displayRaft")
    leaders=self.getSessionLeaders(show=False)
    for session in self.raftsession:
      string="Session id {0} : Leader {1:<15} : ".format(session,leaders[session])
      for el in list(self.raftsession[session].keys()):
        if el == 'members':
          substring="members : "
          for el2 in list(self.raftsession[session]['members'].keys()):
            substring+="{0} ".format(self.raftsession[session]['members'][el2]['host'])
        else:
          string+="{0} {1} : ".format(el,self.raftsession[session][el])  
      string+=substring
      display.raw(string)
    return 0

  def getWsbList(self):
    display.debug("Entering function getWsbList {}".format(self.wsb))
    l=self.wsb.split(",")
    return(l)

  def displaySessionInfo(self,nb):
    display.debug("Entering function displaySessionInfo {}".format(nb))
    url="http://"+str(self.server)+":9000/_/raft_sessions/"+str(nb)+"/info"
    display.debug(url)
    out=self.query_url(url)
    out=json.loads(out)
    if out['leader'] == {}:
      display.error("No leader for session {} -> {}".format(nb,out['leader']))
      exit(9)
    raft_state=self.getRaftState(out['leader']['host'],out['leader']['adminPort'])
    display.raw("Leader {}:{} => {}".format(out['leader']['host'],out['leader']['adminPort'],raft_state))
    if len(out['connected'])==0:
      display.error("No host connected to session {} ({})".format(nb,out['connected']))
    elif len(out['connected'])!=self.RAFTMBR:
      warn="WARNING not enough members (min {})".format(self.RAFTMBR)
    else:
      warn=""
    connected="" 
    for i in out['connected']:
      connected+="{}:{} ".format(i['host'],i['port'])
    display.raw("Members : {} {}".format(connected,warn))  
    if out['disconnected'] == []:
      display.debug("No disconnected member")
    else:
      disconnected=""
      for i in out['disconnected']:
        disconnected+="{}:{} ".format(i['host'],i['port'])
      display.raw("Disconnected members : {}".format(disconnected))  

  def getRaftState(self,ip,port):
    display.debug("Entering function getRaftState {}:{}".format(ip,port))
    url="http://{}:{}/_/raft/state".format(ip,port)
    out=self.query_url(url)
    return(out)

  def watchRaft(self,session=0,tt=10,vault=False):
    display.debug("Entering function watchRaft session {} timer {}".format(session,tt))
    rez={} 
    self.isRaftNumber(session,fatal=True)

    while True:
      for k in self.raftsession:
        if int(k) == int(session):
          display.debug("analysing session {}".format(self.raftsession[k]))
          for i in list(self.raftsession[k]['members'].keys()):
            h=self.raftsession[k]['members'][i]['host']
            p=self.raftsession[k]['members'][i]['adminPort']
            dn=self.raftsession[k]['members'][i]['display_name']
            url="http://{}:{}/_/raft/state".format(h,p)
            q=self.query_url(url) 
            rez[dn]=q
      wsbindex=1
      if self.wsb != None:
        wsblist=self.getWsbList()
        for wsb in wsblist:
          display.debug("Adding wsb session {}".format(wsblist))
          url="http://{}:{}/_/raft/state".format(wsb,p)
          q=self.query_url(url)
          wsblabel="(wsb-{})".format(wsbindex)
          wsblabel=wsblabel.ljust(14," ")
          dn="{}:{} {}".format(wsb,p-100,wsblabel)
          rez[dn]=q
          wsbindex+=1
      for i in sorted(rez.keys()):
        display.raw("{} : {}".format(i,rez[i]))
      display.raw("")
      time.sleep(float(tt))

  
 
def main():
  disable_proxy()
  raft=Raft(args)
  raft.setServer()
  cmd=Command(cli,raft)
  cmd.getCmd()



if __name__ == '__main__':
  main()
else:
  print("loaded")


