#!/usr/bin/python3

import sys
import os
import time
import datetime
import getopt
import json 
import logging 
from getpass import getpass
 
#sys.path.insert(0,'/usr/local/scality-ringsh/ringsh/modules')
from scality.supervisor import Supervisor
from scality.node import Node
from scality.key import Key
from scality.key import KeyRandom
from scality.daemon import DaemonFactory , ScalFactoryExceptionTypeNotFound
from ringsh.utils import int32_to_uint32



PRGNAME=os.path.basename(sys.argv[0])
CREDFILE="/root/Scality/scality-installer-credentials"
LENKEY=40
COS='20'
keylist=[]
option={}
option.update(debug=False)
sup ='https://127.0.0.1:2443'
ring='DATA'
dummy=[]
file=None

def usage():
  message="""
  Check for key is exist or not and print version
  Replicas can be checked as well (-R option)


  usage : """+PRGNAME
  add="""
  KEY
  or
  
  -f file with a list of keys   
  -r ringname
  -p password 
  -P password (read from cli)
  -R Check for each key status of replicas
  -s (print replica along with key)
  -S print key information  
  -x NuMBER (random key number)
"""
  print((message+add))

def parseargs(argv):
  if len(argv)==0:
    usage()
    sys.exit(1)
  if len(argv)==1:
    k=sys.argv[1] 
  try:
    opts, args = getopt.getopt(argv, "Adf:sSl:p:Pr:Rx:z", ["help"])
  except getopt.GetoptError:
    print("Argument error")
    usage()
    sys.exit(9)
  #for i,el in enumerate(opts):
  for opt, arg in opts:
    dummy.append(opt)
    if opt in ("-h", "--help"):
      usage()
      end(0)
    elif opt == '-A':
      option.update(auto=1)
    elif opt == '-d':
      option.update(debug=True)
    elif opt == '-l':
      option.update(login=arg)
    elif opt == '-x':
      for i in range(int(arg)):
        k=KeyRandom(COS).getHexPadded()
        keylist.append(k)
    elif opt == '-p':
      option.update(p=None)
    elif opt == '-P':
      password=getpass()
    elif opt == '-r':
      option.update(ring=arg)
    elif opt == '-R':
      option.update(replica='yes')
    elif opt == '-s':
      option.update(successor='yes')  
    elif opt == '-S':
      option.update(status='yes')  
    elif opt == '-z':
      option.update(zip='yes')  
    elif opt == '-f':
      file=arg 
      try:
        fp = open(arg,"r")
      except IOError as e :
        print(e)
        print('impossible to open %s for read' % file)
        exit(9)  
      fp.close()
      option.update(file=arg)      
  if len(args) > 0:
    for i in args:
      keylist.append(i)
  return keylist 

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
logger = logging.getLogger()

if 'file' in option:
  file=option['file']


def printreplica(k):
  local=[]
  for i in k.getReplicas():
    local.append(i.getHexPadded())
  return local


class mynode():
  def __init__(self,option,ring='DATA',url="https://127.0.0.1:2443",login='admin',password='scality'):
    logger.debug("mynode {}".format(login))
    self.nodes={}
    self.nodestatus={}
    self.names={}
    self.status={}
    self.rez=[]
    self.node=""

    s = Supervisor(url=sup,login=login,passwd=password)
    ringstat=s.supervisorConfigDso(action="view", dsoname=ring)
    logger.info("Gathering ring informations")
    for n in ringstat['nodes']:
      logger.debug("Loading node : {0} {1}".format(n['name'],n['addr']))
      a=n
      nid = '%s:%s' % (n['ip'], n['chordport'])
      self.nodes[nid] = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=ring, login=login, passwd=password)
      self.names[nid]=n['name']
      self.nodestatus[nid]=self.nodes[nid].nodeGetStatus()[0]
      if not self.node: self.node = self.nodes[nid]

  def getExtKeyInfo(self,node,key):
    logger.debug("Getting Ext key : {0}".format(key))
    try:
      et = node.chunkapiStoreOp(op="stat", key=key, extra_params={"use_base64": "1"})
    except Exception as e:
      logger.error("Damned")
    for s in et.findall("result"):
      status = s.find("status").text
      if status == "CHUNKAPI_STATUS_OK":
        #datetime.datetime.fromtimestamp(t).strftime("%Y/%m/%d-%H:%M:%S")
        atime = datetime.datetime.fromtimestamp(int(s.find("atime").text)).strftime("%Y/%m/%d-%H:%M:%S")
        mtime = datetime.datetime.fromtimestamp(int(s.find("mtime").text)).strftime("%Y/%m/%d-%H:%M:%S")
        ctime = datetime.datetime.fromtimestamp(int(s.find("ctime").text)).strftime("%Y/%m/%d-%H:%M:%S")
        version = s.find("version").text
        dataversion = s.find("dataversion").text
        crc = s.find("crc32").text
        size = s.find("size").text
        print("{} [ a {} | m {} | c {} ] {} {} {} {}".format(key,atime,mtime,ctime,version,dataversion,crc,size))

  def getkeyinfo(self,key):
    logger.info("Getting key : {0}".format(key))
    rez=[]
    try: 
      k=Key(key) 
    except ValueError:
      print("%s is not a valid Key" % key)
      return()
    if len(key) != LENKEY :
      print("%s is not a valid Key length" % key)
      return()
    if 'replica' in option:
      rez=printreplica(k)
    rez.append(key)
    zip=[]
    PRESENT=0
    NOTPRESENT=0
    #rez=sorted(rez,key=lambda d: d[LENKEY-2:])
    for K in rez:
      logger.debug("Analyzing key : {0}".format(K))
      DISPLAY=""
      if 'successor' in option:
        suc=self.node.findSuccessor(K)['address']
        self.name=self.names[suc]
        DISPLAY=self.name
      if 'status' in option:
        suc=self.node.findSuccessor(K)['address']
        n=self.nodes[suc]
        status=n.checkLocal(K)
        #print(status)
        logger.debug("{} -> {}".format(K,status))
        if status['status'] == 'free' :
          DISPLAY=DISPLAY+" NOTEXIST "
          zip.append('N')
          NOTPRESENT=NOTPRESENT+1
        elif status['deleted'] == False :
          #print K,status['status'],"NOTDELETED",status['version']
          #DISPLAY=DISPLAY+" NOTDELETED "+str(status['version'])+str(status['size'])
          DISPLAY="{} NOTDELETED {} {}".format(DISPLAY,str(status['version']),str(status['size']))
          zip.append('D')
          PRESENT=PRESENT+1
        else:
          #print K,status['status'],"DELETE",status['version']
          DISPLAY=DISPLAY+" DELETE "+str(status['version'])
          zip.append('Y')
          PRESENT=PRESENT+1
      if 'zip' not in  option:
        print(K+" "+DISPLAY)

      if 'zip' in option:
        s=""
        for i in zip:
          s=s+i
        print(K+":"+str(PRESENT)+":"+str(NOTPRESENT)+":"+s)
      self.getExtKeyInfo(n,K)
def main():
  if file == None:
    for key in keylist :
      node.getkeyinfo(key)
  else:
    with open(file, 'r') as fd:
      for key in fd:
        key=key.strip()
        #print key,len(key)
        if len(key) == LENKEY:
          print('key {}'.format(key))
          node.getkeyinfo(key)
    fd.close()

if __name__ == '__main__':
  parseargs(sys.argv[1:])
  if "ring" in option :
    ring=option['ring']
  else:
    ring='ring'

  if 'login' in option:
    login=option['login']
  else:
    login='admin'

  if 'p' in option:
    password=option['p']
  else:
    password='scality'

  if option['debug']==True:
    logger.setLevel(logging.DEBUG)

  logger.debug("Opening credfile  : {0}".format(CREDFILE))
  try:
    d=open(CREDFILE,'r')
    cred=json.load(d)
    login=cred['internal-management-requests']['username']
    password=cred['internal-management-requests']['password']
    d.close()
  except IOError as e:
    print("Can''t open cred file {0}".format(e))
  node=mynode(option,login=login,password=password)
  main()
else:
  print("loaded")


