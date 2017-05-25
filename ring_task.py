#!/usr/bin/python

import sys
import logging 
import time

sys.path.append('/usr/local/scality-ringsh/ringsh/modules')
sys.path.append('/usr/local/scality-ringsh/ringsh')
from scality.node import Node
from scality.supervisor import Supervisor
from scality.daemon import DaemonFactory


u="https://localhost:2443"
l="root"
p="DvEbRF8REAgz" 

logging.basicConfig(format='%(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
logger = logging.getLogger()

#logger.setLevel(logging.DEBUG)

class ring_obj():
  """ class to manipulate ring objects"""
  def __init__(self,ring="DATA",url="https://127.0.0.1:2443",l=None,p=None,timer=10):
    import config as ringsh_config
    self.url=url
    if l == None:
      self.l=ringsh_config.default_config['auth']['user']
    else:
      self.l=l
    if p == None:
      self.p=ringsh_config.default_config['auth']['password']
    else:
      self.p=p
    self.ring=ring
    self.sup = Supervisor(url=self.url, login=self.l, passwd=self.p)
    self.tasks={}
    self.timer=timer
    self.prev={}
    self.current={}
    
  def getconf(self):
    try:
      self.config=self.sup.supervisorConfigDso(action="view",dsoname=self.ring)
    except Exception, err:
      logger.info("Unable to connect to supervisor")
      print err
      sys.exit(1)
    logger.debug("Get conf for ring : {0}".format(self.ring))
    #return(0)

  def get_task_list(self,type="all"):
    dict={}
    try:
      self.tasks=self.sup.supervisorTasksDso(dsoname="OWRING")
    except Exception as e:
      logger.info("Error getting tasks")
      print e
    #tasks=self.sup.supervisorTasksDso(ringname)
    for task in self.tasks["tasks"]:
      if task['type'] not in dict.keys():
        dict[task['type']]=[]
      dict[task['type']].append(task)
    #if int(task["flag_diskrebuild"]) != 0:
    #  type_ = "repair"
    #print "%s %s objects=%d/%d size=%d/%d dest=%s start=%d tid=%s" % (task["node"]["addr"], type_, int(task["done"]), int(task["total"]), int(task["size_done"]), int(task["est_size_total"]), task["dest"], int(task["starting_time"]), task["tid"])
    self.task=dict
  
  def print_task(self,type="all"):
    for i in self.task.keys():
      if type == "all" or i == type:
        logger.debug('Displaying task type {0}'.format(i))
        for j in self.task[i]:
          logger.debug('Displaying task type {0}'.format(str(j.keys)))
    return(0)

  def print_task_stat(self,type="all"): 
    logger.debug("Enter print_task_stat")
    for task in self.tasks['tasks']:
      cur=task['type']
      if cur == 'move' or cur == 'rebuild':
        self.print_task_stat_move(task,cur)
    return(0)

  def print_task_stat_move(self,task,type):
    logger.debug("Enter print_task_stat_move {0}".format(str(task)))
    node=task['node']['name']
    total=int(task['total'])
    current=int(task['done'])
    remain=total-current
    tid=task['tid']+":"+node
    if not tid in self.prev.keys():
      print "Task {0:10} {1:35} current {2:8} total {3:8} NEW TASK".format(type,tid,current,total) 
      self.prev[tid]={}
      self.prev[tid]['prev']=current
    else:
      prev=self.prev[tid]['prev']
      keysec=((current-prev)/self.timer)
      keytogo=total-current
      if keysec == 0:
        timetogo = 'undefined'
      else:
        timetogo=keytogo/keysec/60
      #print "Task {0:10} {1:35} current {2} (prev) {6:8} total {3:8} key/sec {4:7} time to go {5} minutes".format(type,tid,current,total,keysec,timetogo,prev)
      print "Task {0}\t {1}\t current {2} (prev) {6}\t total {3}\t key/sec {4}\t time to go {5} minutes".format(type,tid,current,total,keysec,timetogo,prev)
      self.prev[tid]['prev']=current
      
  def wait_iter(self):
    time.sleep(self.timer) 
    print

def main():
  o=ring_obj(ring="OWRING",timer=5)
  o.getconf()
  while True:
    o.get_task_list()
    o.print_task()
    o.print_task_stat()
    o.wait_iter()  
  sys.exit(0)

if __name__ == '__main__':
  main()
else:
  print "loaded"
