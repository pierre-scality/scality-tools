#!/bin/python


import subprocess
import logging

logging.addLevelName(15, "VERBOSE")
logging.addLevelName(5, 'TRACE')
logging.basicConfig(format='%(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
logger = logging.getLogger()

@property
def log(obj):
    logging.addLevelName(15, 'VERBOSE')
    myLogger = logging.getLogger(obj.__class__.__name__)
    setattr(myLogger, 'verbose', lambda *args: myLogger.log(15, *args))
    logging.addLevelName(5, 'TRACE')
    myLogger = logging.getLogger(obj.__class__.__name__)
    setattr(myLogger, 'trace', lambda *args: myLogger.log(15, *args))
    return myLogger

def execute(cmd,force_method=None,**option):
  p=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  stdout,stderr=p.communicate()
  rc = p.returncode
  return rc,stdout,stderr

class os_obj():
  def __init__(self):
    self.id=""
    self.cmd=""
    self.out=()
   
  def set_cmd(self,string):
    self.cmd=string
 
  def execute(self,force_method=None,**option):
    p=subprocess.Popen(self.cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    stdout,stderr=p.communicate()
    rc = p.returncode
    return rc,stdout,stderr

  # get the openstack result command and split \n
  # return a structure
  # banner containing headers of os result 
  # data for data as a list of lines 
  def serialize(self,dict):
    struct={}
    # split result by \n and remove head |
    # then split again by pipe
    struct['banner']=dict[1].split('\n')[1][2:].split('|')
    # process data 
    struct['data']=[]
    cells=len(dict[1][3:])
    for idx,el in enumerate(dict[1].split('\n')[3:]):
      logger.trace('serialize %s %s'.format(idx,el))
      if idx >= cells:
        break
      struct['data'].append(el.split('|'))
    return struct
    

  def show_result(self,dict,type=all):
    for i in dict.keys():
      if i == "banner" and type == 'all':
        print i['banner']
      if i == "data" and type == 'all':
        for j in i['data']:
          print j 

def main():
  print "No luck no main"

if __name__ == '__main__':
  main()


