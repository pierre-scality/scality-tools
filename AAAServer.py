#!/usr/bin/python 

import sys
import getopt
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import pprint
import multiprocessing as mp # to start XML-RPC servers in the background
import time
import httplib
import hmac as HMAC# RS2 signature for generating REST queries
import base64  # RS2 signature for generating REST queries
from hashlib import  sha1 as sha # RS2 signature for generating REST queries

import sqlalchemy

def usage():
		# This program is originally dev by MSDC.
                global PRGNAME
                print PRGNAME,"usage"
                print '''
                AAAServer.py 
                -d	Debug
		-s 	server 
		Start in server mode (control C to quit), non server related options are ignored.

		Option for the AAA server is following this format 
		-o	option=value

		option are : 
		user, secretkey, brs2domain, bucket 	

		
                '''


def parseargs(argv):
                try:
                                opts, args = getopt.getopt(argv, "dho:", ["help"])
                except getopt.GetoptError:
                                usage()
                                sys.exit(2)
                #Message.setlevel('info')
                global option
                global DEBUG
                for i,el in enumerate(opts):
                    #print 'enum : '+str(i),el
                    if '-d' in el:
                        "remove -d arg from opts string and go debug"
                        opts.pop(i)
                        #Message.setlevel('debug')
                        #Message.debug(PRGNAME,"going debug, remaining args "+str(opts)+" "+str(args))
                for opt, arg in opts:
                    if opt in ("-h", "--help"):
                        usage()
                        sys.exit()
                    elif opt == '-o':
                        parameter(arg)
		    elif opt == '-s' :
			server=1
		if args.__len__() == 0:
			log(INFO,"no args")
		else:
			command=args
			#read_command(args)

def log(level,message):
	FATAL=["ERROR","FATAL"]
	print level.upper(),message
	if level.lower in FATAL:
		exit()


def read_command(arg):
	cat=arg[0]
	arg=arg[1:]
	if  cat == "user":
		user_func(arg)
	elif cat == "bucket":
		bucket_func(arg)
	else:
		log("WARNING","Unknow function "+cat)
		exit(1)


def parameter(arg):
	LIST=["user","secretkey","admin", "brs2domain","bucket"]
	if arg not in LIST:
		MSG="Argument "+arg+" is not valid, ignoring" 
		log("WARNING",MSG)
		return(False)
	if arg == "user" :
		USER=user
	elif arg == "secretkey" : 
		ADMIN_SECRET_KEY=arg
	elif arg == "admin" : 
		ADMIN_ACCESS_KEY=arg
		 
def user_func(arg=[]):
	log("DUMMY","This is my user_func")

def bucket_func(arg=[]):
	log("DUMMY","This is my bucket_func")

#--------------------------------------------
# Some constants
#--------------------------------------------
DATABASE=./AAA.db

#configuration
PATH='/BRS2'
HOST="localhost"
ACCOUNTING_PORT=8000
AUTHENTICATION_PORT=8001
PROVISIONING_PORT=8002
DEBUG=False
# For rest provisioning
ADMIN_ACCESS_KEY="marc"
ADMIN_SECRET_KEY="thismyverysecretkey"
REST_HOST="localhost"
REST_PORT=8180
#see https://docs.scality.com/doku.php?id=rs2:brs2accounting
BUCKET="bucket" 
BUCKET_OWNER_ID="bucketOwnerId"
BUCKET_OWNER_NAME="bucketOwnerName"
BUCKET_NAME="bucketName"
FULL_VOLUME="fullVolume"
FULL_ITEMS="fullItems"
RS2_TIMESTAMP="timestamp"
REQUESTER_ID="requesterId"
REQUESTER_NAME="requesterName"
GROUP="group"  # string indicating from which network group the requests where issued
TYPE="type" #  string indicating whether reported volume applies to a regular or a copy operation. Possible values are REGULAR or COPY
VOLUME="volume" # string containing the volume downloaded for this bucket since last call to addBucketDownload() with the same (requesterId, bucketOwnerId, bucket) arguments
OPERATION="type" # string containing the type of operation (PUT_BUCKET, HEAD_BUCKET, GET_BUCKET, DELETE_BUCKET, LIST_BUCKETS, PUT_OBJECT, HEAD_OBJECT, GET_OBJECT, DELETE_OBJECT,COPY_OBJECT, PUT_BUCKETACL, PUT_OBJECTACL, GET_BUCKETACL, GET_OBJECTACL, PUT_BUCKETWWW, GET_BUCKETWWW, DELETE_BUCKETWWW)
NUMBER_OF_OPERATION="number"
#https://docs.scality.com/doku.php?id=rs2:brs2auth&s[]=provisioning
STATUS="status" 
ID="id"
PRIVATE_KEY="privatekey"
DISPLAY_NAME="displayname"
ENABLED="enabled"
BUCKET_NBR_LIMIT="bucketnrlimit" # integer indicating the maximum number of buckets a user may create
BUCKET_SIZE_LIMIT="bucketsizelimit" #  integer indicating the maximum bucket size (per bucket quota), in megabytes. Use -1 for unlimited. 
REQUEST_LIMIT="requestlimit" # integer indicating the maximum number of requests a user may issue in a 30 second time window. Use -1 for unlimited. 
UNLIMITED=-1
USER="user"
#--------------------------------------------
# IMPLEMENTATION XML RPC SERVERS
#--------------------------------------------
# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = (PATH,)

# utilities for debugging
def show_type( arg):
    """Illustrates how types are passed in and out of server methods.
        
    Accepts one argument of any type.  
    Returns a tuple with string representation of the value, 
    the name of the type, and the value itself.
    """
    return (str(arg), str(type(arg)), arg)



    
#Accounting implementation
    
class Accounting:      
         
    def updateBucketStorage(self, arg):
        print "updateBucketStorage---------------------------------------"
        try:
            if DEBUG:
                pprint.pprint(show_type(arg)[-1])
            for update in arg :
                print "bucket: "+update[BUCKET]
                print "bucketOwnerId: "+update[BUCKET_OWNER_ID]
                print "bucketOwnerName: "+update[BUCKET_OWNER_NAME]
                print "bucketName: " +update[BUCKET_NAME]
                print "fullVolume: "+update[FULL_VOLUME]
                print "fullItems: "+update[FULL_ITEMS]
                print "timestamp: ", update[RS2_TIMESTAMP]
            print "---------------------------------------------------"
            return True # the request was processed successfully
        except Exception, e:
            print e
            return False # the request was not processed successfully 
            
                
    def addBucketUpload(self,arg):
        print "addBucketUpload---------------------------------------"
        try:  
            if DEBUG:
                pprint.pprint(show_type(arg)[-1])
            for upload in arg :
                print "requesterId: "+upload[REQUESTER_ID]
                print "requesterName:  "+upload[REQUESTER_NAME]
                print "bucketOwnerId: "+upload[BUCKET_OWNER_ID]
                print "bucketOwnerName: "+upload[BUCKET_OWNER_NAME]
                print "bucket: "+upload[BUCKET]
                print "bucketName: " +upload[BUCKET_NAME]
                print "group: " +upload[GROUP]
                print "type: " +upload[TYPE]
                print "volume: " +upload[VOLUME]
            print "---------------------------------------------------"
            return True # the request was processed successfully
        except Exception, e:
            print e
            return False # the request was not processed successfully 
    
    def addBucketDownload(self, arg):
        print "addBucketDownload---------------------------------------"
        try:  
            if DEBUG:
                pprint.pprint(show_type(arg)[-1])
            for download in arg :
                print "requesterId: "+download[REQUESTER_ID]
                print "requesterName:  "+download[REQUESTER_NAME]
                print "bucketOwnerId: "+download[BUCKET_OWNER_ID]
                print "bucketOwnerName: "+download[BUCKET_OWNER_NAME]
                print "bucket: "+download[BUCKET]
                print "bucketName: " +download[BUCKET_NAME]
                print "group: " +download[GROUP]
                print "type: " +download[TYPE]
                print "volume: " +download[VOLUME]
            print "---------------------------------------------------"
            return True # the request was processed successfully
        except Exception, e:
            print e
            return False # the request was not processed successfully 
    
    
    def addBucketRequest(self, arg):
        print  "addBucketRequest---------------------------------------"
        try:  
            if DEBUG:
                pprint.pprint(show_type(arg)[-1])
            for request in arg :
                print "requesterId: "+request[REQUESTER_ID]
                print "requesterName:  "+request[REQUESTER_NAME]
                print "bucketOwnerId: "+request[BUCKET_OWNER_ID]
                print "bucketOwnerName: "+request[BUCKET_OWNER_NAME]
                print "bucket: "+request[BUCKET]
                print "bucketName: " +request[BUCKET_NAME]
                print "group: " +request[GROUP]
                print "Operation: " +request[OPERATION]
                print "Number of operation: " +request[NUMBER_OF_OPERATION]
            print "---------------------------------------------------"
            return True # the request was processed successfully
        except Exception, e:
            print e
            return False # the request was not processed successfully 

#Authentication implementation    
class Authentication:

    def getUserSecretKey(self, arg):
        print "getUserSecretKey---------------------------------------"
        try:
            if DEBUG:
                pprint.pprint(show_type(arg)[-1])
            print "User: "+arg
            result=dict()
            result[STATUS] = True
            user =dict()
            user[ID]=str(arg)
            user[PRIVATE_KEY]="thismyverysecretkey"
            user[DISPLAY_NAME]=str(arg)
            user[ENABLED]=True
            user[BUCKET_NBR_LIMIT]=20
            user[BUCKET_SIZE_LIMIT]=UNLIMITED
            user[REQUEST_LIMIT]=UNLIMITED
            result[USER]=user
            print "---------------------------------------------------"
            return result # the request was processed successfully
        except Exception, e:
            print e
            result =dict()
            result[STATUS] = False 
            return result # the request was not processed successfully

#Provisioning implementation 
#same signature than  Authentication.getUserSecretKey 
class Provisionning:


    def getUserAdminSecretKey(self, arg):
        print "getUserAdminSecretKey---------------------------------------"
        try:
            if DEBUG:
                pprint.pprint(show_type(arg)[-1])
            print "User: "+arg
            result=dict()
            result[STATUS] = True
            user =dict()
            user[ID]=str(arg)
            user[PRIVATE_KEY]=ADMIN_SECRET_KEY
            user[DISPLAY_NAME]=ADMIN_ACCESS_KEY
            user[ENABLED]=True
            user[BUCKET_NBR_LIMIT]=20
            user[BUCKET_SIZE_LIMIT]=UNLIMITED
            user[REQUEST_LIMIT]=UNLIMITED
            result[USER]=user
            print "---------------------------------------------------"
            return result # the request was processed successfully
        except Exception, e:
            print e
            result =dict()
            result[STATUS] = False 
            return result # the request was not processed successfully

#Utility method to start a server
# start server
def start(server,port):
    xserver =  SimpleXMLRPCServer((HOST, port), requestHandler=RequestHandler)
    xserver.register_introspection_functions()
    xserver.register_instance(server)
    process = mp.Process(target=xserver.serve_forever)
    process.start()
    return process

#--------------------------------------------
# IMPLEMENTATION REST CLIENTS
#--------------------------------------------        
class RestClient:
    #see  https://docs.scality.com/doku.php?id=rs2:brs2prov#user_creation
    # the REST URI is of the form
    # http://brs2.domainname.com:8180/users/myuser?dname=displayname
    # but you must be RS2 authenticated...
    def createUser(self,user,dname):
        conn = httplib.HTTPConnection(REST_HOST,REST_PORT)
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT",   time.gmtime())
        header={}
        header['Date'] = date
        method="PUT"
        path="/users/" +  user + "?dname=" + dname
        hmac = HMAC.new(ADMIN_SECRET_KEY, digestmod=sha)
        c_string = method +'\n'+'\n'+'\n' + date + '\n' +  path
        hmacl = hmac.copy()
        hmacl.update(c_string)
        b64_hmac = base64.encodestring(hmacl.digest()).strip()
        header['Authorization'] = "AWS %s:%s" % ( ADMIN_ACCESS_KEY, b64_hmac)
        conn.request(method, path , '' , header)
        resp = conn.getresponse()
        if resp.status != 200:
            print "User creation failed"
            print resp.read()
            quit() # in production you probably want to raise an exception
        print "User creation successfull"
        print resp.read()
        
    # see https://docs.scality.com/doku.php?id=rs2:brs2prov#user_deletion 
    # the REST URI is of the form
    #http://brs2.domainname.com:8180/users/myuser
    # but you must be RS2 authenticated...
    def deleteUser(self,user):
        conn = httplib.HTTPConnection(REST_HOST,REST_PORT)
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT",time.gmtime())
        header={}
        header['Date'] = date
        method="DELETE"
        path="/users/" +  user
        hmac = HMAC.new(ADMIN_SECRET_KEY, digestmod=sha)
        c_string = method +'\n'+'\n'+'\n' + date + '\n' +  path
        hmacl = hmac.copy()
        hmacl.update(c_string)
        b64_hmac = base64.encodestring(hmacl.digest()).strip()
        header['Authorization'] = "AWS %s:%s" % ( ADMIN_ACCESS_KEY, b64_hmac)
        conn.request(method, path , '' , header)
        resp = conn.getresponse()
        if resp.status != 200:
            print "User deletion failed"
            print resp.read()
            quit() # in production you probably want to raise an exception
        print "User deletion successfull"
        print resp.read()
        

    def getUser(self,user):
        conn = httplib.HTTPConnection(REST_HOST,REST_PORT)
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT",time.gmtime())
        header={}
        header['Date'] = date
        method="GET"
        path="/users/" +  user
        hmac = HMAC.new(ADMIN_SECRET_KEY, digestmod=sha)
        c_string = method +'\n'+'\n'+'\n' + date + '\n' +  path
        hmacl = hmac.copy()
        hmacl.update(c_string)
        b64_hmac = base64.encodestring(hmacl.digest()).strip()
        header['Authorization'] = "AWS %s:%s" % ( ADMIN_ACCESS_KEY, b64_hmac)
        conn.request(method, path , '' , header)
        resp = conn.getresponse()
        if resp.status != 200:
            print "Failed to get user"
            print resp.read()
            quit() # in production you probably want to raise an exception 
        print "Get user successfull"
        print resp.read()

# SQL stff
def init_db(db):     
	

if __name__ == '__main__':
    init()
    if (len(sys.argv) != 1) :
      log("DEBUG","read arg")
      parseargs(sys.argv[1:])
    else:
      log("DEBUG","Starting without args") 



	
    #start the servers
    accounting=start(Accounting(),ACCOUNTING_PORT)
    authentication=start(Authentication(),AUTHENTICATION_PORT)
    provisionning=start(Provisionning(),PROVISIONING_PORT)
    time.sleep( 15 ) # let the system initialize
    # play with the rest provisioning API
    client=RestClient()
    print "*******creating user toto***********"
    client.createUser("toto", "thismyverysecretkey")
    print "*******getting user toto***********"
    client.getUser("toto")
    print "*******deleting user toto***********"
    client.deleteUser("toto")
    #wait
    raw_input("Press a key to stop dummy server")
    #stop everything
    accounting.terminate()
    authentication.terminate()
    provisionning.terminate()
    pass
