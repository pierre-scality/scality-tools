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

PRGNAME=os.path.basename(sys.argv[0])
#print PRGNAME

SLEEP=0.1
URI="cdmi1/blob2/"
OP="PUT"

URL='http://'+URI


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
		opts, args = getopt.getopt(argv, "hu:d", ["help", "url="])
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
		elif opt in ("-u", "--url"):
			print "using URL",URL
			URL = arg
			remain = "".join(args)
			print "remainingargs",remain
			URL=remain
	print "URL",URL

if (len(sys.argv) == 1) : 
	print "Using default URL %s" % URL
else:
	parseargs(sys.argv[1:])

#print "req url",URL
#req=urllib2.Request(URL) 

#print "full",req.get_full_url()
#print "method",req.get_method()

try:
	page=urllib2.urlopen(URL)
except urllib2.HTTPError as e:
	print "code",e.code
	print "read",e.read() 
	print "len",len(e.read())
else:
	code=page.getcode()
	print "return code "+str(code)
	if str(code)[0] != "2" :
		print "page not accessible "+str(code)

cmd="/usr/bin/find"
cmd="/usr/bin/find . -type f" 
#(output, err) = p.communicate()
count=0
ps=subprocess.Popen(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
# shell=True)
while True:
	if ps.poll() != None:
		break
	try:
		# fsarchiver do write on stderr
		nextline = next(ps.stdout)
	except StopIteration:
		break
	count+=1
	line=nextline.decode('utf-8').rstrip('\n')
	print str(count)+" "+line


