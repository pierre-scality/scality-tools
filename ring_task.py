#!/usr/bin/python

import sys
import logging 
import time
import getopt

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
PRGNAME=sys.argv[0]

def usage():
        message="""
        Check running tasks (default move) and display some stats
        default time is 60s


        usage : """+PRGNAME
        add="""
	-l list of task to display tasks (default move), list list move,rebuild ..
	-r ring on which run the check 
        -t interval between checks
"""
        print(message+add)

def parseargs(argv):
        option={}
        try:
                opts, args = getopt.getopt(argv, "dl:r:t:", ["help"])
        except getopt.GetoptError:
                print "Argument error"
                usage()
                sys.exit(9)
        for i,el in enumerate(opts):
                if '-d' in el:
                        opts.pop(i)
                        logger.setLevel(logging.DEBUG)
        for opt, arg in opts:
                if opt in ("-h", "--help"):
                        usage()
                        end(0)
                elif opt == '-l':
			dummy=arg.split(',')
                        option.update(display=dummy)
                elif opt == '-t':
                        option.update(timer=arg)
                elif opt == '-r':
                        option.update(ring=arg)
        #if len(args) > 0:
        #       for i in args:
	return option

class ring_obj():
  """ class to manipulate ring objects"""
  def __init__(self,option,ring="DATA",url="https://127.0.0.1:2443",l=None,p=None):
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
    if "timer" in option.keys():
      self.timer=int(option['timer'])
    else:
      self.timer=10
    self.ring=ring
    self.sup = Supervisor(url=self.url, login=self.l, passwd=self.p)
    self.tasks={}
    if "display" in option.keys():
      self.display=option['display']
    else:
      self.display=['move']
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
      self.tasks=self.sup.supervisorTasksDso(dsoname=self.ring)
    except Exception as e:
      logger.info("Error getting tasks")
      print e
    for task in self.tasks["tasks"]:
      logger.debug("Initial Task {0}".format(task))
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
        #for j in self.task[i]:
        #  logger.debug('Displaying task type detail {0}'.format(str(j.keys)))
    return(0)

  def print_task_filter(self,type="all"): 
    logger.debug("Enter print_task_filter {0}".format(self.display))
    if all in self.display:
      self.display=['all']
    done=0
    for task in self.tasks['tasks']:
      cur=task['type']
      if cur in self.display or self.display[0]=="all":
      #if cur == 'move' or cur == 'rebuild':
        self.print_task_stat_chosen(task,cur)
	done+=1
    if done == 0:
	print "No task to display ({0})".format(','.join(self.display))
    return(done)

  def print_task_stat_chosen(self,task,type):
    logger.debug("Enter print_task_stat_chosen {0}".format(str(task)))
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
  option=parseargs(sys.argv[1:])
  o=ring_obj(option,ring="OWRING")
  o.getconf()
  while True:
    o.get_task_list()
    o.print_task()
    o.print_task_filter()
    o.wait_iter()  
  sys.exit(0)

if __name__ == '__main__':
  main()
else:
  print "loaded"
