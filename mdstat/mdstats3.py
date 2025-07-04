#!/usr/bin/python3

import os
import sys
from datetime import datetime
import requests
import json
import argparse
import time
from urllib.parse import urlparse, urlunparse
from collections import namedtuple

# Ansible-specific imports
# Ensure the Ansible library is installed (pip install ansible)
try:
    from ansible.parsing.dataloader import DataLoader
    from ansible.vars.manager import VariableManager
    from ansible.inventory.manager import InventoryManager
    from ansible.playbook.play import Play
    from ansible.executor.task_queue_manager import TaskQueueManager
    from ansible.plugins.callback import CallbackBase
    import ansible.constants as C
    from ansible import context
except ImportError:
    print("Error: The Ansible library is not installed or accessible.")
    print("Please install it with: pip install ansible")
    sys.exit(1)


try:
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''
    Check server's process status
    mdstat.py <option> <command>
    There are 2 commands type bucket, session and a watch mode to follow a given session
    You need to point an S3 server for the initial request to be done.
    mdstat.py -s server1                                    => Display raft sessions with leader
    mdstat.py -s server1 session                            => Get the leader for each session
    mdstat.py -s server1 session [ bucket] <session id>     => Display information about this specific session (from the leader). if bucket is added it will show bucket for this session
    mdstat.py -s server1 bucket <bucketname>                => Display the raft session for the bucket with servers and seq details
    mdstat.py -s server1 watch  <session id>  <interval>    => Display seq numbers about a give raft session
''')
    parser.add_argument('-a', '--all', dest='all', action="store_true", default=False ,help='Display all raft sessions members for this host')
    parser.add_argument('-d', '--debug', dest='debug', action="store_true", default=False ,help='Set script in DEBUG mode ')
    parser.add_argument('-s', '--server', default="localhost" , help='Target server for direct queries, or Ansible SSH host if -A is used.')
    parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False ,help='It will display the request to repd')
    parser.add_argument('-w', '--wsb', dest='wsb',default=None ,help='Set the WSB ip to add to the query for watch functionality')
    parser.add_argument('-i', '--ignore', dest='ignore',action="store_true", default=False ,help='Ignore connection error.')
    parser.add_argument('-A', '--ansible', dest='ansible', action="store_true", default=False,
                        help='Execute HTTP requests via Ansible on the host specified by -s (requests will target localhost on that remote host).')
except SystemExit:
    sys.exit(9)

MD_SUB_SESSION=('bucket')
MD_SUB_BUCKET=('leader')

MD_CMD=('session','bucket','watch')
MD_BUCKET=('leader')
MD_SESSION=('leader','session','bucket')

# Global variable for the Ansible inventory path
ANSIBLE_INVENTORY_PATH = '/srv/scality/s3/s3-offline/federation/env/s3config/inventory'


class Command():
    def __init__(self,arguments,raft):
        self.args=arguments
        self.raft=raft

    def getCmd(self):
        display.debug(f"Running getCmd with arg {self.args}")
        if self.raft.getAll():
            sessions=self.raft.getAllSessions()
            self.printAllSessions(sessions)
            return(0)
        if len(self.args) == 0:
            self.raft.getSessionLeaders()
            return(0)
        self.cmd=self.args[0]
        if self.cmd not in MD_CMD:
            display.error(f"Command is not supported {self.cmd}")
            sys.exit(1)
        self.remaining=self.args[1:]
        self.filterCmd()
        return(0)

    def filterCmd(self):
        display.debug(f"Running filterCmd on {self.remaining}")
        if self.cmd == "session":
            if len(self.remaining) == 0:
                self.raft.getRaftAll()
                self.raft.displayRaft()
                sys.exit(0)
            else:
                self.doSessionOperation()
        elif self.cmd == "bucket": # Using 'elif' to avoid executing other blocks if 'session' is handled
            if len(self.remaining) == 0:
                display.error(f"Need argument for command {self.cmd} : <bucketname> or <session_id>") # Updated error message
                sys.exit(9)
            else:
                target_arg = self.remaining.pop(0) # Capture the argument after 'bucket'
                
                # --- NEW LOGIC TO HANDLE SESSION ID ---
                try:
                    session_id = int(target_arg)
                    # If conversion to integer succeeds, it's a session ID
                    display.verbose(f"Interpreting '{target_arg}' as a session ID for bucket command.")
                    self.raft.getSessionBucket(session_id)
                    sys.exit(0) # Exit the script after processing the session request
                except ValueError:
                    # If it's not an integer, it's a bucket name, continue with original logic
                    self.bucket = target_arg # Assign to self.bucket for subsequent logic
                    display.verbose(f"Interpreting '{target_arg}' as a bucket name.")

                # --- ORIGINAL LOGIC FOR BUCKET NAMES (if not handled by new logic) ---
                try:
                    self.query=self.remaining.pop(0) # Check if a sub-command (like 'leader') is present
                except IndexError:
                    # If no sub-command, execute getBucketInformation
                    out=self.raft.getBucketInformation(self.bucket)
                    if out == None:
                        sys.exit(9)
                    else:
                        sys.exit(0)
                # If a sub-command is present (e.g., 'leader'), handle it via doBucketOperation
                self.doBucketOperation()
        elif self.cmd == "watch": # Using 'elif'
            self.raft.getRaftAll()
            if len(self.remaining) == 0:
                display.error("You must tell the raft session number")
            rs=int(self.remaining[0])
            if len(self.remaining) == 1:
                self.raft.watchRaft(rs)
            else:
                timer=int(self.remaining[1])
                self.raft.watchRaft(rs,timer)
        return(0)

    def printAllSessions(self,sessions):
        display.debug(f"print All sessions : \n {sessions} \n")
        s=json.loads(sessions)
        hosts=[]
        for e in s:
            id=e['id']
            for i in e['raftMembers']:
                hosts.append(i['host'])
            print(f"{id:<2d}: {hosts}")
            hosts=[]
        return(0)

    def doBucketOperation(self):
        display.debug(f"Running doBucketOperation {self.bucket} {self.query}")
        if self.query not in MD_BUCKET:
            display.error(f"Need operation for bucket {self.bucket}",fatal=True)
        if self.query == 'leader':
            display.debug(f"Getting leader for bucket {self.bucket}")
            out=self.raft.getBucketLeader(self.bucket)
            if out == None:
                sys.exit(9)
            else:
                sys.exit(0)
        elif self.query == 'leader':
            display.debug(f"Getting leader for bucket {self.bucket}")


    def doSessionOperation(self):
        display.debug(f"Running doSessionOperation {self.remaining}")
        try:
            number=int(self.remaining[0])
        except ValueError:
            number=-1
        if number != -1:
            self.raft.displaySessionInfo(number)
            sys.exit(0)
        if self.remaining[0] == "bucket":
            if self.remaining.__len__() < 2:
                display.error("Need at least one argument : sessions number",fatal=True)
            self.raft.getSessionBucket(self.remaining[1])
        else:
            display.debug("Nothing to do")
            sys.exit(0)

class Msg():
    def __init__(self,level='info'):
        self.level=level
        self.valid=['info','debug','verbose','warning']

    def set(self,level):
        print(f"{'INFO':<15} : Setting loglevel to {level}")
        if level not in self.valid:
            self.display(f"not a valid level {level}")
            return(9)
        self.level=level

    def verbose(self,msg,label=None):
        if self.level != 'info':
            header=label if label else 'VERBOSE'
            print(f"{header:<15} : {msg}")

    def info(self,msg,label=None):
        header=label if label else "INFO"
        print(f"{header:<15} : {msg}")

    def error(self,msg,fatal=False):
        header="ERROR"
        print(f"{header:<15} : {msg}")
        if fatal:
            sys.exit(9)

    def warning(self,msg,fatal=False):
        header="WARNING"
        print(f"{header:<15} : {msg}")
        if fatal:
            sys.exit(9)

    def debug(self,msg):
        if self.level == "debug":
            header="DEBUG"
            print(f"{header:<15} : {msg}")

    def raw(self,msg):
        print(f"{msg}")

    def showlevel(self):
        print(f"Error level is {self.level} : ")

display=Msg('info')

args,cli=parser.parse_known_args()
if args.verbose:
    display.set('verbose')
if args.debug:
    display.set('debug')

def disable_proxy():
    done=0
    for k in list(os.environ.keys()):
        if k.lower().endswith('_proxy'):
            del os.environ[k]
            done=1
    if done != 0:
        display.debug("Proxy has been disabled")

class Raft():
    def __init__(self,args,raft=-1, ansible_runner=None):
        display.debug(f"Raft instance creation with {args} {cli}")
        self.server=args.server
        self.raftsession={}
        self.raft=raft
        self.wsb=args.wsb
        self.ignore=args.ignore
        self.RAFTCOUNT=9
        self.RAFTMBR=5
        self.all=args.all
        self.use_ansible = args.ansible
        self.ansible_runner = ansible_runner

    def getAll(self):
        """
        Returns the value of the 'all' attribute, indicating if all sessions should be displayed.
        """
        return self.all

    def setServer(self):
        if self.use_ansible:
            # Reverted to INFO: Information about Ansible proxying
            display.verbose(f"Requests will be proxied via Ansible on {self.server}, targeting 127.0.0.1 on the remote host.")
        else:
            display.verbose(f"Using {self.server} as direct endpoint.")


    def getAllSessions(self):
        display.debug("Entering function getAllSessions")
        url_to_query = f"http://{self.server}:9000/_/raft_sessions/"
        out = self.query_url(url_to_query)
        if out == None:
            display.error(f"Error analyzing {url_to_query}")
            return(None)
        return(out)

    def query_url(self,url_to_target_raft,fatal=False):
        if self.use_ansible and self.ansible_runner:
            parsed_url = urlparse(url_to_target_raft)
            ansible_uri_url = urlunparse(('http', f'127.0.0.1:{parsed_url.port or 9000}', parsed_url.path, parsed_url.params, parsed_url.query, parsed_url.fragment))

            display.verbose(f"Executing HTTP GET via Ansible on SSH host {self.server} to fetch {ansible_uri_url} from remote localhost.")

            module_args = f"url='{ansible_uri_url}' method=GET return_content=yes"
            ansible_results = self.ansible_runner.run_module(self.server, 'uri', module_args)

            if ansible_results["ok"]:
                for host, result in ansible_results["ok"].items():
                    if result.get('status') == 200 and result.get('content') is not None:
                        display.debug(f"Ansible URI module success on {host} for {ansible_uri_url}")
                        return result['content']
                    else:
                        display.error(f"Ansible URI module returned non-200 status {result.get('status')} or no content for {ansible_uri_url} on {host}")
                        if fatal: sys.exit(9)
                        return None
            elif ansible_results["failed"]:
                for host, result in ansible_results["failed"].items():
                    display.error(f"Ansible URI module FAILED on {host} for {ansible_uri_url}: {result}")
                if fatal: sys.exit(9)
                return None
            elif ansible_results["unreachable"]:
                for host, result in ansible_results["unreachable"].items():
                    display.error(f"Ansible URI module UNREACHABLE on {host} for {ansible_uri_url}: {result}")
                if fatal: sys.exit(9)
                return None
            else:
                display.error(f"No successful result from Ansible URI module for {ansible_uri_url} on {self.server}")
                if fatal: sys.exit(9)
                return None
        else:
            display.verbose(f"Executing direct HTTP GET from script to {url_to_target_raft}")
            try:
                r = requests.get(url_to_target_raft)
            except requests.exceptions.RequestException as e:
                if self.ignore:
                    display.verbose(f"Ignore error connecting to : {url_to_target_raft}")
                    return(None)
                else:
                    display.error(f"Error connecting to : {url_to_target_raft}")
                    display.debug(f"Error is : \n{e}\n")
                    sys.exit(1)
            if r.status_code == 200:
                return(r.text)
            else:
                display.error(f"Request returned non-200 response {r.status_code} for : {url_to_target_raft}")
                if fatal:
                    sys.exit(9)
                return(None)

    def getBucketInformation(self,bucket,full=False):
        display.verbose(f"getBucketInformation {bucket}")
        url_to_query = f"http://{self.server}:9000/default/informations/{bucket}"
        out=self.query_url(url_to_query)
        if out == None:
            return(False)
        struct=json.loads(out)
        display.debug(f"Bulk output getBucketLeader \n {struct}\n")
        leader=[]
        follower=[]
        info={}
        for i in range(0,len(struct)):
            info[struct[i]['ip']]={}
            for key in list(struct[i].keys()):
                if key == 'isLeader':
                    if struct[i]['isLeader'] == True:
                        display.debug(f"leader {struct[i]}")
                        leader.append(struct[i]['ip'])
                        session=struct[i]['raftSessionId']
                    else:
                        display.debug(f"follower {struct[i]}")
                        follower.append(struct[i]['ip'])
                else:
                    info[struct[i]['ip']].update({key:struct[i][key]})
        display.raw(f"Leader : {leader[0]} (session {session})")
        f=""
        for i in follower:
            f+=f"{i},"
        f=f[:-1]
        display.raw(f"Follower : {f}")
        for ip in list(info.keys()):
            display.raw(f"Server : {ip} aseq {info[ip]['aseq']} cseq {info[ip]['cseq']} vseq {info[ip]['vseq']} bseq {info[ip]['bseq']}")

    def getBucketLeader(self,bucket):
        display.debug("Entering getBucketLeader")
        url_to_query = f"http://{self.server}:9000/default/leader/{bucket}"
        display.verbose(f"Querying {url_to_query}")
        out=self.query_url(url_to_query)
        if out == None:
            return(False)
        struct=json.loads(out)
        display.debug(f"Bulk output getBucketLeader {struct}")
        leader=struct['host']
        url_to_query_id = f"http://{self.server}:9000/_/buckets/{bucket}/id"
        out=json.loads(self.query_url(url_to_query_id))
        print(f"Leader {leader} : Raft session {out}")

    def getSessionBucket(self,sessionnb,show=True):
        display.debug(f"Entering getSessionBucket for session {sessionnb}")
        if self.isRaftNumber(sessionnb):
            url_to_query = f"http://{self.server}:9000/_/raft_sessions/{sessionnb}/bucket"
            out=self.query_url(url_to_query)
        else:
            display.error(f"Invalid session number {sessionnb}",fatal=True)
        if show == True:
            display.raw(out)
        return(out)

    def isRaftNumber(self,nb,fatal=True):
        try:
            sessionnb=int(nb)
        except ValueError:
            display.error(f"{nb} is not an integer",fatal=True)
        if  sessionnb not in list(range(0,self.RAFTCOUNT)):
            display.error(f"Raft session number must be between 0 and {self.RAFTCOUNT-1}, got {sessionnb}",fatal=True)
        else:
            display.debug(f"{nb} is a valid raft session number")
            return(True)

    def getSessionLeaders(self,show=True):
        display.debug("Entering getSessionLeaders")
        ret={}
        for i in range(0,self.RAFTCOUNT):
            if self.raft==-1 or self.raft==i:
                url_to_query = f"http://{self.server}:9000/_/raft_sessions/{i}/leader"
                out=self.query_url(url_to_query)
                if out == None:
                    display.error("getSessionLeaders fails because request did not complete")
                    return(99)
                out=json.loads(out)
            ret[i]=out['host']
            if show == True:
                display.raw(f"Session {i} : Leader {out['host']}")
        return ret

    def getRaftSession(self,id):
        url_leader = f"http://{self.server}:9000/_/raft_sessions/{id}/leader"
        leader=self.query_url(url_leader)
        leader=json.loads(leader)
        url_sessions = f"http://{self.server}:9000/_/raft_sessions/"
        out=self.query_url(url_sessions)
        out=json.loads(out)
        print(f"Members for session {id} (leader is {leader['host']}) : ")
        for el in out[id]['raftMembers']:
            print(el['display_name'],el['site'])

    def getRaftAll(self):
        display.debug("Entering function getRaftAll")
        url_to_query = f"http://{self.server}:9000/_/raft_sessions/"
        out=self.query_url(url_to_query)
        if out == None:
            display.error(f"Error analyzing {url_to_query}")
            return(None)
        out=json.loads(out)
        for i in out:
            session=i['id']
            display.debug(f"Adding session {session}")
            self.raftsession[session]={}
            self.raftsession[session]['connectedToLeader']=i['connectedToLeader']
            self.raftsession[session]['members']={}
            for j in i['raftMembers']:
                self.raftsession[session]['port']=j['port']
                self.raftsession[session]['adminport']=j['adminPort']
                host=j['host']
                self.raftsession[session]['members'][host]=j

    def displayRaft(self):
        display.debug("Entering function displayRaft")
        leaders=self.getSessionLeaders(show=False)
        for session in self.raftsession:
            string=f"Session id {session} : Leader {leaders[session]:<15} : "
            substring=""
            for el in list(self.raftsession[session].keys()):
                if el == 'members':
                    substring="members : "
                    for el2 in list(self.raftsession[session]['members'].keys()):
                        substring+=f"{self.raftsession[session]['members'][el2]['host']} "
                else:
                    string+=f"{el} {self.raftsession[session][el]} : "
            string+=substring
            display.raw(string)
        return 0

    def getWsbList(self):
        display.debug(f"Entering function getWsbList {self.wsb}")
        l=self.wsb.split(",")
        return(l)

    def displaySessionInfo(self,nb):
        display.debug(f"Entering function displaySessionInfo {nb}")
        url_to_query = f"http://{self.server}:9000/_/raft_sessions/{nb}/info"
        display.debug(url_to_query)
        out=self.query_url(url_to_query)
        out=json.loads(out)
        if out['leader'] == {}:
            display.error(f"No leader for session {nb} -> {out['leader']}")
            sys.exit(9)
        raft_state=self.getRaftState(out['leader']['host'],out['leader']['adminPort'])
        display.raw(f"Leader {out['leader']['host']}:{out['leader']['adminPort']} => {raft_state}")
        if len(out['connected'])==0:
            display.error(f"No host connected to session {nb} ({out['connected']})")
        elif len(out['connected'])!=self.RAFTMBR:
            warn=f"WARNING not enough members (min {self.RAFTMBR})"
        else:
            warn=""
        connected=""
        for i in out['connected']:
            connected+=f"{i['host']}:{i['port']} "
        display.raw(f"Members : {connected} {warn}")
        if out['disconnected'] == []:
            display.debug("No disconnected member")
        else:
            disconnected=""
            for i in out['disconnected']:
                disconnected+=f"{i['host']}:{i['port']} "
            display.raw(f"Disconnected members : {disconnected}")

    def getRaftState(self,ip,port):
        display.debug(f"Entering function getRaftState {ip}:{port}")
        url_to_query = f"http://{ip}:{port}/_/raft/state"
        out=self.query_url(url_to_query)
        return(out)

    def watchRaft(self,session=0,tt=10,vault=False):
        display.debug(f"Entering function watchRaft session {session} timer {tt}")
        rez={}
        self.isRaftNumber(session,fatal=True)

        while True:
            for k in self.raftsession:
                if int(k) == int(session):
                    display.debug(f"analysing session {self.raftsession[k]}")
                    for i in list(self.raftsession[k]['members'].keys()):
                        h=self.raftsession[k]['members'][i]['host']
                        p=self.raftsession[k]['members'][i]['adminPort']
                        dn=self.raftsession[k]['members'][i]['display_name']
                        url_to_query=f"http://{h}:{p}/_/raft/state"
                        q=self.query_url(url_to_query)
                        rez[dn]=q
            wsbindex=1
            if self.wsb != None:
                wsblist=self.getWsbList()
                for wsb in wsblist:
                    display.debug(f"Adding wsb session {wsblist}")
                    wsb_port = 9000
                    url_to_query=f"http://{wsb}:{wsb_port}/_/raft/state"
                    q=self.query_url(url_to_query)
                    wsblabel=f"(wsb-{wsbindex})"
                    wsblabel=wsblabel.ljust(14," ")
                    dn=f"{wsb}:{wsb_port} {wsblabel}"
                    rez[dn]=q
                    wsbindex+=1
            for i in sorted(rez.keys()):
                display.raw(f"{i} : {rez[i]}")
            display.raw("")
            time.sleep(float(tt))

class ResultsCollector(CallbackBase):
    """
    A simple callback plugin to capture results.
    """
    def __init__(self, *args, **kwargs):
        super(ResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_failed = {}
        self.host_unreachable = {}
        self.host_skipped = {}
        self.host_artifact = {}

    def v2_runner_on_ok(self, result, **kwargs):
        host = result._host.get_name()
        self.host_ok[host] = result._result
        display.debug(f"Ansible OK: {host} => {result._result}")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        host = result._host.get_name()
        self.host_failed[host] = result._result
        display.error(f"Ansible FAILED: {host} => {result._result}")

    def v2_runner_on_unreachable(self, result):
        host = result._host.get_name()
        self.host_unreachable[host] = result._result
        display.error(f"Ansible UNREACHABLE: {host} => {result._result}")

    def v2_runner_on_skipped(self, result):
        host = result._host.get_name()
        self.host_skipped[host] = result._result
        display.info(f"Ansible SKIPPED: {host} => {result._result}")

class AnsibleRunner:
    def __init__(self, inventory_path, target_host_to_verify=None, verbosity=0):
        """
        Initialise AnsibleRunner.
        :param inventory_path: Path to the Ansible inventory file.
        :param target_host_to_verify: The specific host name/IP that must be present in the inventory.
        :param verbosity: Verbosity level (0 to 5, 0 being minimal)
        """
        self.loader = DataLoader()

        # Check if the inventory file exists
        if not os.path.exists(inventory_path):
            display.error(f"Error: Ansible inventory file not found at '{inventory_path}'.")
            sys.exit(1)

        self.inventory = InventoryManager(loader=self.loader, sources=inventory_path)
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)
        self.results_collector = ResultsCollector()

        # --- Define Ansible options via a custom class ---
        class AnsibleOptions: # Class to mimic argparse.Namespace with dict-like behavior
            def __init__(self, verbosity_level):
                self.connection = 'smart'
                self.module_path = C.DEFAULT_MODULE_PATH
                self.forks = 5
                self.become = False
                self.become_method = None
                self.become_user = None
                self.check = False
                self.diff = False
                self.verbosity = verbosity_level
                self.private_key_file = None
                self.ssh_common_args = None
                self.ssh_extra_args = None
                self.sftp_extra_args = None
                self.scp_extra_args = None
                self.roles_path = C.DEFAULT_ROLES_PATH
                self.ask_vault_pass = False
                self.vault_password_file = None
                self.new_vault_password_file = None
                self.output_file = None
                self.tags = []
                self.skip_tags = []
                self.host_key_checking = C.HOST_KEY_CHECKING
                self.remote_user = None
                self.remote_port = None
            
            # Implements __getitem__ for subscript access (obj['key'])
            def __getitem__(self, key):
                if hasattr(self, key):
                    return getattr(self, key)
                raise KeyError(f"'{key}' not found in AnsibleOptions.")

            # Implements .get() for dictionary-like access (obj.get('key', default))
            def get(self, key, default=None):
                return getattr(self, key, default)
            
            # Implements __setitem__ to allow modification via obj['key'] = value
            def __setitem__(self, key, value):
                setattr(self, key, value)

            # Optional: for better representation during debugging
            def __repr__(self):
                return f"<{self.__class__.__name__}({self.__dict__})>"


        self.options = AnsibleOptions(verbosity_level=verbosity) # Instance of the custom class

        # --- Verify presence of target host in inventory ---
        self.target_host_for_run = None
        if target_host_to_verify:
            host_obj = self.inventory.get_host(target_host_to_verify)
            if not host_obj:
                display.error(f"Error: Host '{target_host_to_verify}' not found in Ansible inventory '{inventory_path}'. Please ensure it is defined.")
                sys.exit(1)
            display.debug(f"Host '{target_host_to_verify}' successfully found in inventory '{inventory_path}'.")
            self.target_host_for_run = target_host_to_verify


    def run_module(self, host_pattern, module_name, module_args=None):
        """
        Run a single Ansible module against a host pattern.
        :param host_pattern: Hosts to run the module against (e.g., 'all', 'server1').
                             This must be a host defined in the inventory loaded during __init__.
        :param module_name: Name of the Ansible module (e.g., 'ping', 'shell')
        :param module_args: Arguments for the module (e.g., 'cmd="ls -l"')
        :return: Dictionary containing results (ok, failed, unreachable, skipped hosts)
        """
        # Set CLIARGS context for Ansible BEFORE loading the play
        # This line ensures compatibility with Ansible's requirements.
        context.CLIARGS = self.options

        play_source = dict(
            name="Ansible Ad-Hoc Command",
            hosts=host_pattern,
            gather_facts='no',
            tasks=[
                dict(action=dict(module=module_name, args=module_args), register='module_out'),
            ]
        )
        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)

        tqm = None
        try:
            tqm = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                passwords={},
                stdout_callback=self.results_collector,
            )
            result = tqm.run(play)
        finally:
            if tqm is not None:
                tqm.cleanup()
            # The cleanup_files() method of DataLoader no longer exists and has been removed.

        return {
            "ok": self.results_collector.host_ok,
            "failed": self.results_collector.host_failed,
            "unreachable": self.results_collector.host_unreachable,
            "skipped": self.results_collector.host_skipped
        }


def main():
    disable_proxy()

    ansible_runner = None
    if args.ansible: # If -A is enabled
        ansible_target_for_ssh = args.server # Host to verify and target
        ansible_inventory_path = ANSIBLE_INVENTORY_PATH # Use the global variable

        # Create AnsibleRunner instance, which verifies if ansible_target_for_ssh is in the inventory
        ansible_runner = AnsibleRunner(ansible_inventory_path, ansible_target_for_ssh, verbosity=args.debug)

        # IMPORTANT: Configure SSH connection options for Ansible here
        # These options will apply to the connection to ansible_target_for_ssh
        # Example:
        # ansible_runner.options.remote_user = 'your_ssh_user'
        # ansible_runner.options.private_key_file = '/path/to/your/ssh_key'
        # ansible_runner.options.ssh_extra_args = '-o StrictHostKeyChecking=no' # Use with caution for testing

    raft=Raft(args, ansible_runner=ansible_runner)
    raft.setServer()
    cmd=Command(cli,raft)
    cmd.getCmd()


if __name__ == '__main__':
    main()
else:
    print("loaded")
