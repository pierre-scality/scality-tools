
"""
Get the URL and acces site
Gives summary of page load and size
"""



import urllib2
import sys
import os
import getopt 
from BeautifulSoup import BeautifulSoup

PRGNAME=os.path.basename(sys.argv[0])
#print PRGNAME
URL='http://onair-pprd.corp.airliquide.com/'

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
	soup=BeautifulSoup(page)
	# At this step soup contains the cleaned source html code
	#print soup
	#print dir(req)
	SIZE=len(page.read())
	CODE=page.getcode()
	print "code: %s , size : %s" % (CODE,SIZE)

print "Image list :"
for line in soup.findAll('img') :
	print line	
