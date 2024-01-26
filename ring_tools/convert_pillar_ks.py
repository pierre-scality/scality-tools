#!/usr/bin/python

import yaml 
import os 
import sys
import subprocess 
import getopt

name={}
newks={}
runningks={}
pillar={}


ring='DATA'

def usage():
  print sys.argv[0]+" ringsh file"
  print "Ring name must be specified with -r ringname"
  exit(0)

if (len(sys.argv) < 2) :
  usage()
  exit(5)
else:
 argv=sys.argv 


try:
  opts, args = getopt.getopt(sys.argv[1:], "hr:", ["help", "grammar="])
except getopt.GetoptError:          
        usage()                         
        exit(2) 

for opt, arg in opts:
  if opt in ("-h", "--help"):
    usage()                     
    exit()   
  elif opt in ('-r'):
    ring=arg
  else:
    print "Argument error : "+arg
    usage
    exit(1)

ringsh=args[0]

source_name="temp" 
pillar_file="/srv/scality/pillar/scality-common.sls"
output="/tmp/"+pillar_file.split('/')[-1]

if not os.path.isfile(ringsh):
  print "ERROR : cant open sprov ringsh file"+ringsh
  exit(9)

if os.path.isfile(output):
  print "WARNING : "+"Output file already exist"
  #exit()


def get_name(type='file',arg1=""):
  d={}
  if type == 'file':
    file=arg1
    with open(file) as f:
      for line in f:
        (host,ip)=line.split(",")
        #print host+":"+ip.rstrip()  
        #d[host]=ip.rstrip()
        d[ip.rstrip().lstrip()]=host
  elif type == 'ringsh' : 
    cmd="ringsh supervisor serverList |awk '{print $5,$7}' | sed s/:.*//"
    p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in p.stdout.readlines():
      (host,ip)=line.split(",")
      d[ip.rstrip().lstrip()]=host
  return d

def get_running_ks(hostfile):
  ks={}
  cmd="ringsh supervisor ringStatus OWPROD | grep Node:"
  p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  for line in p.stdout.readlines():
    list=line.split()
    ip=list[2].split(':')[0]
    nid=int(list[2].split(':')[1])-8083
    assigned=list[3]
    host=hostfile[ip]
    if newks.has_key(host):
      newks[host].update({nid:assigned})
    else:
      newks[host]={nid:assigned}
  return newks

# Build list of name:ip dict
#name=get_name('file',source_name)
name=get_name('ringsh')

def get_min_port(ringsh):
  port=[]
  with open(ringsh) as f:
    for line in f:
      port.append(line.split()[4])
  return min(port)

def create_ks_from_ksfile(ringsh,port):
  with open(ringsh) as f:
    for newline in f:
      line=newline.split()
      ip=line[3]
      host=name[ip]
      nid=int(line[4])-(int(port)-1)
      assigned=line[5]
      if newks.has_key(host):
        newks[host].update({nid:assigned})
      else:
        newks[host]={nid:assigned}    
  return(newks)


print "Using pillar : "+pillar_file
pillar=yaml.load(open(pillar_file))
existing_rings=pillar['scality']['keyspace'].keys()
if not ring in existing_rings:
  print "WARNING : ring {} not existing in original pillar {}, adding ring".format(ring,str(existing_rings)) 
pillar['scality']['keyspace'][ring]=newks



port=get_min_port(ringsh)
newks=create_ks_from_ksfile(ringsh,port)

with open(output, 'w') as fout:
  yaml.dump(pillar, fout, default_flow_style=False)
print "Created new kspace pillar to : "+output

runningks=get_running_ks(name)
pillar['scality']['keyspace'][ring]=runningks
output=output+".running"
with open(output, 'w') as fout:
  yaml.dump(pillar, fout, default_flow_style=False)
print "Created running kspace pillar to : "+output
