#!/usr/bin/python -u

import sys
import logging 
import time
import getopt
import json
from datetime import datetime 

sys.path.append('/usr/local/scality-ringsh/ringsh/modules')
sys.path.append('/usr/local/scality-ringsh/ringsh')
sys.path.append('/etc/scality-ringsh/')
from scality.node import Node
from scality.supervisor import Supervisor
from scality.daemon import DaemonFactory

CREDFILE="/tmp/scality-installer-credentials"
try:
  print "Loading cred file"
  d=open(CREDFILE,'r')
  cred=json.load(d)
  l=cred['internal-management-requests']['username']
  p=cred['internal-management-requests']['password']
  d.close()
except IOError:
  print "can't open cred file"
  l="root"
  p="5vvou3rIjDc8" 

u="https://localhost:2443"
ring="OWPROD"

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
                opts, args = getopt.getopt(argv, "dl:or:t:", ["help"])
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
		elif opt == '-o':
			option.update(outfile=True)
                elif opt == '-r':
                        option.update(ring=arg)
        #if len(args) > 0:
        #       for i in args:
	return option

class ring_obj():
  """ class to manipulate ring objects"""
  def __init__(self,option,ring="DATA",url="https://127.0.0.1:2443",l=None,p=None):
    import config as ringsh_config
    if 'ring' in option:
      self.ring=option['ring']
    else:
        self.ring=ring
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
    self.sup = Supervisor(url=self.url, login=self.l, passwd=self.p)
    self.tasks={}
    if "display" in option.keys():
      self.display=option['display']
    else:
      self.display=['move']
    self.prev={}
    self.current={}
    self.valid_task={}
    if "outfile" in option.keys():
      self.outfile="log_ring_task-{0}".format(datetime.now().strftime('%d%m_%H%M%S'))
      self.openlogfile()
    else:
      self.outfile=None

  def openlogfile(self):
    try:
      self.fd=open("./"+self.outfile,'w')
    except IOError as e:
      print "cant open log file {0}".format(e)					 
      exit(9)
    print "Opening log file {0}".format("./"+self.outfile)

  def print_whats_needed(self,line):
    print line
    if self.outfile:
      self.fd.write(line+"\n".encode("iso8859-1"))
	
 
  def getconf(self):
    try:
      self.config=self.sup.supervisorConfigDso(action="view",dsoname=self.ring)
    except Exception, err:
      logger.info("Unable to connect to supervisor")
      print err
      sys.exit(1)
    logger.debug("Get conf for ring : {0}".format(self.ring))
  
  ## build task list dict ordered by task
  def get_task_list(self,type="all"):
    dict={}
    try:
      self.tasks=self.sup.supervisorTasksDso(dsoname=self.ring)
    except Exception as e:
      logger.info("Error getting tasks")
      print e
    for task in self.tasks["tasks"]:
      logger.debug("Initial Task {0}".format(task))
      if  task['type'] == "rebuild" and int(task["flag_diskrebuild"]) != 0:
    	  task['real_task'] = "repair"
      else:
        task['real_task'] = task['type']
          #print "%s %s objects=%d/%d size=%d/%d dest=%s start=%d tid=%s" % (task["node"]["addr"], type_, int(task["done"]), int(task["total"]), int(task["size_done"]), int(task["est_size_total"]), task["dest"], int(task["starting_time"]), task["tid"])
      if task['real_task'] not in dict.keys():
        dict[task['real_task']]=[]
      dict[task['real_task']].append(task)
    self.task=dict


  ## debug function
  def print_task(self,type="all"):
    for i in self.task.keys():
      if type == "all" or i == type:
        logger.debug('Displaying task type {0}'.format(i))
        for j in self.task[i]:
          logger.debug('Displaying task type detail {0}'.format(str(j.keys)))
    return(0)

  ## from task dict build a valid_task dict with [task type][task id] for display 
  def task_filter(self,type="all"): 
    logger.debug("Enter print_task_filter {0}".format(self.display))
    if all in self.display:
      self.display=['all']
    done=0
    self.valid_task={}
    for i in self.task.keys():
      for j in self.task[i]:
        cur=j['real_task']
        if cur in self.display or self.display[0]=="all":
          if cur not in self.valid_task.keys():
            self.valid_task[cur]={}
          self.valid_task[cur][j['tid']]=j	
	  done+=1
    if done == 0:
	print "No task to display ({0})".format(','.join(self.display))
    else:
    	self.print_task_stat_chosen(cur)
    return(done)

  ## self.valid_task[type][id]=task
  def print_task_stat_chosen(self,type):
    for type in sorted(self.valid_task.keys()):
     for id in sorted(self.valid_task[type].keys()):
      task=self.valid_task[type][id]
      logger.debug("Enter print_task_stat_chosen {0}".format(str(task)))
      d=datetime.now().strftime('%d%m:%H%M%S')
      node=task['node']['name']
      total=int(task['total'])
      current=int(task['done'])
      remain=total-current
      print d+" ",
      tid=task['tid']+":"+node
      if not tid in self.prev.keys():
        self.print_whats_needed("Task {0:10} {1:35} current {2:8} total {3:8} NEW TASK".format(type,tid,current,total))
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
        if type == 'move':
          dest=str(task['dest'])
          logger.debug("task is  {0}".format(task))
          if dest != "auto":
            ip,port=dest.split(":")
            hostn=socket.gethostbyaddr(ip)[0]
            hostn=hostn.split('-')[0]
            nport=int(port)-4244+1
            dest=str(ring+"-"+hostn+"-n"+str(nport))

          self.print_whats_needed("Task {0:8} {1:30} to {7:20} cur {2:12} prev {6:12} total {3:12} key/sec {4:6} time to go {5:9} minutes".format(type,tid,current,total,keysec,timetogo,prev,dest))
        else:
      	  self.print_whats_needed("Task {0:8} {1:30} cur {2:12} (prev) {6:12} total {3:12} key/sec {4:6} time to go {5:9} minutes".format(type,tid,current,total,keysec,timetogo,prev))
        self.prev[tid]['prev']=current

 
  def wait_iter(self):
    time.sleep(self.timer) 
    print

def main():
  option=parseargs(sys.argv[1:])
  o=ring_obj(option)
  o.getconf()
  while True:
    o.get_task_list()
    #o.print_task()
    o.task_filter()
    o.wait_iter()  
  sys.exit(0)

if __name__ == '__main__':
  main()
else:
  print "loaded"
