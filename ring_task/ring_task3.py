!/usr/bin/python3 -u

import sys
import logging
import time
import getopt
import json
from datetime import datetime

sys.path.append('/usr/local/scality-ringsh/ringsh/modules')
sys.path.append('/usr/local/scality-ringsh/ringsh')
sys.path.append('/etc/scality-ringsh/')
sys.path.append('/etc/scality/ringsh/')
from scality.node import Node
from scality.supervisor import Supervisor
from scality.daemon import DaemonFactory

logging.basicConfig(format='%(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
logger = logging.getLogger()
PRGNAME=sys.argv[0]
CREDFILE="/tmp/scality-installer-credentials"

try:
  logging.debug("Loading cred file")
  d=open(CREDFILE,'r')
  cred=json.load(d)
  l=cred['internal-management-requests']['username']
  p=cred['internal-management-requests']['password']
  d.close()
except IOError:
  logging.debug("can't open cred file")
  l="root"
  p="5vvou3rIjDc8"

u="https://localhost:2443"
ring="DATA"


def usage():
        message="""
        Check running tasks (default move) and display some stats
        default time is 60s


        usage : """+PRGNAME
        add="""
        -l list of task to display tasks (default move), list list move,rebuild ..
        -r ring on which run the check
        -t interval between checks (if set to 0 will exit after first iteration)
"""
        print((message+add))

def parseargs(argv):
        option={}
        try:
                opts, args = getopt.getopt(argv, "dl:or:t:", ["help"])
        except getopt.GetoptError:
                print("Argument error")
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
    self.tasklist=[]
    self.sort=None
    self.ring_params=[]
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
    if "timer" in list(option.keys()):
      self.timer=int(option['timer'])
    else:
      self.timer=10
    self.sup = Supervisor(url=self.url, login=self.l, passwd=self.p)
    self.tasks={}
    if "display" in list(option.keys()):
      self.display=option['display']
    else:
      self.display=['move']
    self.prev={}
    self.current={}
    self.valid_task={}
    if "outfile" in list(option.keys()):
      self.outfile="log_ring_task-{0}".format(datetime.now().strftime('%d%m_%H%M%S'))
      self.openlogfile()
    else:
      self.outfile=None

  def openlogfile(self):
    try:
      self.fd=open("./"+self.outfile,'w')
    except IOError as e:
      print("cant open log file {0}".format(e))
      exit(9)
    print("Opening log file {0}".format("./"+self.outfile))

  def print_whats_needed(self,line):
    print(line)
    if self.outfile:
      self.fd.write(line+"\n".encode("iso8859-1"))


  def getconf(self):
    try:
      self.config=self.sup.supervisorConfigDso(action="view",dsoname=self.ring)
    except Exception as err:
      logger.info("Unable to connect to supervisor")
      print(err)
      sys.exit(1)
    logger.debug("Get conf for ring : {0}".format(self.ring))
    # to get chordtasks_sendlimit/chordtasks_recvlimit
    self.ring_params=self.config['params']

  def get_conf_param(self,param):
    for i in self.ring_params:
      if i[0] == param:
        return(i[1])
    return None


  ## build task list dict ordered by task
  def get_task_list(self,type="all"):
    dict={}
    try:
      self.tasks=self.sup.supervisorTasksDso(dsoname=self.ring)
    except Exception as e:
      logger.info("Error getting tasks")
      print(e)
    for task in self.tasks["tasks"]:
      logger.debug("Initial Task {0}".format(task))
      if  task['type'] == "rebuild" and int(task["flag_diskrebuild"]) != 0:
        task['real_task'] = "repair"
      else:
        task['real_task'] = task['type']
          #print "%s %s objects=%d/%d size=%d/%d dest=%s start=%d tid=%s" % (task["node"]["addr"], type_, int(task["done"]), int(task["total"]), int(task["size_done"]), int(task["est_size_total"]), task["dest"], int(task["starting_time"]), task["tid"])
      if task['real_task'] not in list(dict.keys()):
        dict[task['real_task']]=[]
      dict[task['real_task']].append(task)
    self.task=dict


  ## debug function
  def print_task(self,type="all"):
    for i in list(self.task.keys()):
      if type == "all" or i == type:
        logger.debug('Displaying task type {0}'.format(i))
        for j in self.task[i]:
          logger.debug('Displaying task type detail {0}'.format(str(j.keys)))
    return(0)

  ## from task dict build a valid_task dict with [task type][task id] for display
  def task_filter(self,type="all"):
    logger.debug("Enter print_task_filter {0}\n{1}".format(self.display,self.task))
    if all in self.display:
      self.display=['all']
    done=0
    self.valid_task={}
    for i in list(self.task.keys()):
      for j in self.task[i]:
        cur=j['real_task']
        if cur in self.display or self.display[0]=="all":
          if cur not in list(self.valid_task.keys()):
            self.valid_task[cur]={}
          self.valid_task[cur][j['tid']]=j
          done+=1
    if done == 0:
      print("No task to display ({0})".format(','.join(self.display)))
    else:
      self.print_task_stat_chosen(cur)
    return(done)

  ## self.valid_task[type][id]=task
  def print_task_stat_chosen(self,type):
    for type in sorted(self.valid_task.keys()):
     for id in sorted(self.valid_task[type].keys()):
      task=self.valid_task[type][id]
      logger.debug("Enter print_task_stat_chosen {}".format(str(task)))
      d=datetime.now().strftime('%d%m:%H%M%S')
      node=task['node']['name']
      total=int(task['total'])
      current=int(task['done'])
      remain=total-current
      tid=task['tid']+":"+node
      if not tid in list(self.prev.keys()):
        thistask="{} {} {} {} {}".format(type,tid,current,'New',total).split()
        #self.print_whats_needed("{} Task {:<10} {:<35} current {:<8} total {:<8} NEW TASK".format(d,type,tid,current,total))
        #thistask="{} {} {} {} {}".format(type,tid,current,total,'NEW')).split()
        self.tasklist.append(thistask)
        self.prev[tid]={}
        self.prev[tid]['prev']=current
      else:
        prev=self.prev[tid]['prev']
        keysec=((current-prev)/self.timer)
        keytogo=total-current
        if keysec == 0:
          timetogo = -1
        else:
          timetogo=keytogo/keysec/60
        #if type == 'move':
          #dest=str(task['dest'])
        logger.debug("task is  {0}".format(task))
        thistask="{} {} {} {} {} {} {}".format(type,tid,current,prev,total,keysec,int(timetogo)).split()
        #else:
        #  thistask="{} {} {} {} {} {} {}".format(type,tid,current,prev,total,keysec,int(timetogo)).split()
        self.prev[tid]['prev']=current
        self.tasklist.append(thistask)
    if self.tasklist != []:
      #self.task
      self.print_pretty_task()
    self.tasklist=[]

  # only compare node with id:node format
  def sort_task(self):
    logger.debug("sorting {}".format(self.tasklist))
    # need to manage id:node
    sort_field=1
    out_list=[]
    for a in self.tasklist:
      if out_list == []:
        out_list.append(a)
      else:
        idx=0
        compare=a[sort_field].split(':')[1]
        for b in out_list:
          added=False
          #print("compare {} > {}".format( b[sort_field].split(':')[1],compare))
          if b[sort_field].split(':')[1] > compare:
            out_list.insert(idx,a)
            added=True
            break
          else:
            idx+=1
          # adding at the end if the list
        if not added:
          out_list.append(a)
    return out_list

  def print_pretty_task(self,status=True):
    logger.debug("print_pretty list : {0}".format(self.tasklist))
    d=datetime.now().strftime('%y%m%d:%H%M%S')
    self.sort="node"
    #print(self.tasklist)
    local_task_list=[]
    task_ct={}
    keysec_ct={}
    if self.sort != None:
      local_task_list=self.sort_task()
    else:
      local_task_list=self.tasklist
    for e in local_task_list:
      logger.debug("print_pretty : {0}".format(e))
      type=e[0]
      tid=e[1]
      current=e[2]
      prev=e[3]
      total=e[4]
      if type not in task_ct.keys():
        keysec_ct[type]=0
        task_ct[type]=0
      task_ct[type]+=1
      if prev == 'New':
        self.print_whats_needed("[ {} ] Task {:<5} {:<39} cur {:<12} total {:<12} NEW TASK".format(d,type,tid,current,total))
        continue
      keysec=int(float(e[5]))
      keysec_ct[type]+=keysec
      end="undefined"
      if e[6] == -1:
        end='undefined'
        continue
      estime=float(e[6])
      if estime < 24*60:
        end="{:>6} minutes".format(int(estime))
      else:
        end="{:>6} minutes ({} days)".format(int(estime),round((estime/(24*60)),2))
      #else:
      #  end="{:<6} minutes {} days {:<2} weeks".format(estime,int(estime/(24*60)),int(estime/(24*60*7)))
      self.print_whats_needed("[ {} ] Task {:<7} {:<39} cur {:<12} prev {:<12} total {:<12} key/sec {:<4} time to go {}".format(d,type,e[1],e[2],e[3],e[4],keysec,end))
    #else:
    #  self.print_whats_needed("{} Task {:<8} {:<39} cur {:<12} (prev) {:<12} total {:<12} key/sec {:<6} time to go {} minutes".format(d,type,e[1],e[2],e[3],e[4],int(e[5])))
    if len(task_ct) >0 and status:
      sendlimit,receivelimit=self.get_conf_param('chordtasks_sendlimit'),self.get_conf_param('chordtasks_recvlimit')
      line="[ {} ] Summary [ interval {} | send/recv =  {}/{} ] : ".format(d,self.timer,sendlimit,receivelimit)
      for e in task_ct.keys():
        line+="{} [ task count {} total keys/sec {}] ".format(e,task_ct[e],keysec_ct[e])
      self.print_whats_needed(line)


  def wait_iter(self):
    time.sleep(self.timer)
    print()

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
  print("loaded")
