#!/usr/bin/python

import yaml 
import os 
import subprocess 

name={}
newks={}
runningks={}
pillar={}

source_name="temp" 
ringsh="./ringsh.OWPROD-v1.txt"
pillar_file="/srv/scality/pillar/scality-common.sls"
output="/tmp/"+pillar_file.split('/')[-1]

ring='OWPROD'
#scality.keyspace.ring

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
name=get_name('file',source_name)


with open(ringsh) as f:
  for newline in f:
    line=newline.split()
    ip=line[3]
    host=name[ip]
    nid=int(line[4])-8083
    assigned=line[5]
    if newks.has_key(host):
      newks[host].update({nid:assigned})
    else:
      newks[host]={nid:assigned}    
print "Using pillar : "+pillar_file
pillar=yaml.load(open(pillar_file))
pillar['scality']['keyspace'][ring]=newks

with open(output, 'w') as fout:
  yaml.dump(pillar, fout, default_flow_style=False)
print "Created new kspace pillar to : "+output

runningks=get_running_ks(name)
pillar['scality']['keyspace'][ring]=runningks
output=output+".running"
with open(output, 'w') as fout:
  yaml.dump(pillar, fout, default_flow_style=False)
print "Created running kspace pillar to : "+output
