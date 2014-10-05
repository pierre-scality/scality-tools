#!/usr/bin/python2
"""
Get the URL and acces site
Gives summary of page load and size
"""



import urllib2
import sys
import os
import getopt 
import subprocess
import requests
from time import *

PRGNAME=os.path.basename(sys.argv[0])
#print PRGNAME

SLEEP=2
URI="cdmi1/blob2/"
OP="PUT"
HTTPTIMEOUT=3
URL='http://'+URI
RRRRR="."
HEADERS=0



def __print(level,prgname,message,option=""): 
	print '%30s : %10s : %30s' % (level,prgname,message)

def usage():
	global PRGNAME
	print PRGNAME,"usage"
	print "debug sys args",sys.argv
	#for arg in sys.argv:
	#	print arg

def parseargs(argv):
	grammar = "kant.xml"
	global URL
	#print "Parsing args",argv,"loop"
	try:
		opts, args = getopt.getopt(argv, "dhHp:u:", ["help", "url="])
	except getopt.GetoptError:
		usage()
		sys.exit(2)
	#print "Parsing opt",opts,"arg",args
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			usage()
			sys.exit()
		elif opt == '-d':
			global DEBUG
			DEBUG = 1 
		elif opt == '-H':
			global HEADERS
			HEADERS = 1 
		elif opt in ("-u", "--url"):
			URL = arg
			print "using URL",URL
			#remain = "".join(args)
			#print "remainingargs",remain
			#URL=remain
		elif opt in ("-p", "--path"):
			global RRRRR
			RRRRR = arg
			print "using PATH ",RRRRR

def format_filename(fullname):
	""" return formated directory as list [ dir, file ] dir is stripped from ./"""
	if fullname[:2] == './' : fullname=fullname[2:]	
	if '/' not in fullname:
		rez=["",fullname]
	else:
		(dir,file)=os.path.split(fullname)
		rez=[dir,file]
	return(rez)
	

def create_container(root,path,recurse=1):
	""" create container can recurse down"""
	url=root+"/"+path
	response=requests.put(url)
	if response.status_code == 201:
		print "URL created "+url
	else:
		relative=""
		for i in path.split('/'):
			relative=relative+i+"/"
			print "Creating "+URL+relative	
			response=requests.put(URL+relative)
		if response.status_code != 201:
			print "Failed to create "+url
			return response.status_code
	return response.status_code	


def put_file(url,datafile="none",option=""):
	""" put file if container do not exist call create_conainer"""
	#datafile="/root/scality-tools/"+datafile
	#print "put "+url+","+datafile
	#try:
	with open(datafile,'rb') as fd:
    		response=requests.put(url,data=fd)
		#print str(response.status_code)+","+str(response.headers)
		#print response.status_code
	#except:
	#	print "Error openning file "+datafile
	#	return "Error"
	if response.status_code == 404 : 
		dir=format_filename(datafile)[0]
		print "Creating intermediate containers "+dir
		rez=create_container(URL,dir)
		if rez != 201 :
			print "FAILED to create file"+datafile
			return 500 	
		with open(datafile,'rb') as fd:
    			response=requests.put(url,data=fd)
			if str(response.status_code)[0] != 2 :
				print "FAILED to create file"+datafile
				return 500 
	#else:
	#	print "AERAZERAZER"	
				
	if HEADERS == 1:
		for i in response.headers:
			print i+" "+response.headers[i]
		print "End Headers"

		
	return str(response.status_code)
		

if (len(sys.argv) != 1) : 
#	print "Using default URL %s" % URL
#else:
	parseargs(sys.argv[1:])

try:
	page=requests.get(URL,timeout=HTTPTIMEOUT)
except requests.HTTPError as e:
	print "code",e.code
	print "read",e.read() 
	print "len",len(e.read())
except requests.Timeout	 as e:
	print "Timeout processing page "+URL
except requests.exceptions.ConnectionError: 
	print "Cannot connect to "+URL
#except :
#	print page.status_code
#	print "error processing page URL"
else:
	code=page.status_code
	if str(code)[0] != "2" :
		print "page not accessible "+str(code)
		exit(1)

def main():
	print "loaded"
	return

if __name__ != "__main__":
    sys.exit(main())



cmd="/usr/bin/find "+RRRRR+" -type f" 
print RRRRR+" "+URL
cmd=cmd.split()
#(output, err) = p.communicate()
count=0
ps=subprocess.Popen(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
# shell=True)
while True:
	try:
		nextline = next(ps.stdout)
	except StopIteration:
		print "End of list"
		break
	count+=1
	line=nextline.decode('utf-8').rstrip('\n')
	if line[:2] == './' : line=line[2:]
	this_line=format_filename(line)
	if this_line[1] == "" :
		print "Putting container"+line
		create_container(this_line[0])
	else:
		print "Putting file"+line
		if URL[-1:] != "/" : URL=URL+"/"	
		rez=put_file(URL+line,line)
		print str(count)+" "+str(rez)+" "+line
	print
	sleep(SLEEP)
