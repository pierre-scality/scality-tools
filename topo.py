#!/bin/python3

import json
import sys 
if len(sys.argv) > 1:
  file=sys.argv[1]
else:
  file="/root/topology.json"
try: 
  fd=open(file)
except: 
  print("cannot open file {}".format(file))
  print("syntax :\n{} : <topologyfile>".format(sys.argv[0]))
  print("You need to copy topo file : HOST=XX ; SSD=ssd1 ; scp $HOST:/scality/$SSD/s3/scality-metadata-bucket/conf/topology.json .")
  exit(9)

d=json.load(fd)

res={}
for session in d.keys():
  if session not in res.keys():
    res[session]=[]
  for role in ['repds', 'wsbs']:
    for entry in d[session][role]:
      infostring="{} : {} : {} : {}".format(session,role,entry['display_name'],entry['site'])
      res[session].append(infostring)

for session in res:
  for entry in res[session]:
    print("{}".format(entry))
