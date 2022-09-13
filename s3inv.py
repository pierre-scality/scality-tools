#!/bin/python3

import argparse
import configparser

DEFAULT="/srv/scality/s3/s3-offline/federation/env/s3config/inventory"

try:
  parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''
  s3inv.py <inventory file>
''')
  parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
  parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='It will display the request to repd')
except SystemExit:
  exit(9)


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

args,cli=parser.parse_known_args()
if args.verbose == True:
  print('v')
  display.set('verbose')
if args.debug==True:
  print('d')
  display.set('debug')

if cli == []:
  file=DEFAULT
else:
  file=cli[0]



def open_env(invfile):
  display.verbose("Opening {}".format(file))
  try:
    fd=open(file)
  except FileNotFoundError:
    display.error("Can't open file {}".format(file))
    exit(9)
  return(fd)

def parse_env(fd):
  sect='default'
  inv={}
  server={}
  wsb=[]
  inv[sect]=[]
  for line in fd.readlines():
    if line[0] == "#":
      continue
    if len(line) == 1:
      continue
    if line[0] == '[':
      sect=line[1:].split(']')[0].rstrip()
      display.debug("New section {}".format(sect))
      inv[sect]=[]
      continue
    else:
      display.debug("add in section {} :  {}".format(sect,line.rstrip()))
      entry=line.rstrip()
      if entry in server.keys():
        display.debug("Matched {} and {}".format(entry,server[entry]))
        entry="{} ({})".format(entry,server[entry]) 
      inv[sect].append(entry) 
    if sect == 'default':
      explode=line.split()
      s=explode[0]
      n=explode[1].split("=")[1]
      display.debug("s3 name : {} realname : {}".format(s,n))
      server[s]=n
      if s[:3] == 'wsb':
        display.debug("Adding {} to wsb list {}".format(n,wsb))
        wsb.append(n)
  return(inv,wsb)

def display_inv(inv,section=[]): 
  for sect in inv.keys():
    if section == [] or sect in section:
      print("[{}]".format(sect))
      for val in inv[sect]:
        print(val)
  return(0)

def main(file):
  fd=open_env(file)
  messyinput,wsb=parse_env(fd)
  display.debug("sections found {}".format(messyinput.keys()))
  #for i in messyinput.keys():
  #  print("section {} : \n".format(i))
  # print(messyinput[i])
  display_inv(messyinput,["minority","majority"])
  print("Wsb server list : "),
  wsbstr=""
  for i in wsb:
    if wsbstr != "":
      wsbstr=wsbstr+","+i
    else:
      wsbstr+=i
  print(wsbstr)

if __name__ == '__main__':
  main(file)
else:
  print("loaded")

