#! /usr/bin/python

import sys
import json
import datetime,time
import getopt
import logging

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(funcName)s: %(message)s',level=logging.INFO)
@property
def log(obj):
    logging.addLevelName(5, 'TRACE')
    myLogger = logging.getLogger(obj.__class__.__name__)
    setattr(myLogger, 'trace', lambda *args: myLogger.log(5, *args))
    return myLogger

logger = logging.getLogger()


def usage():
  print """
  Usage : cat file | s3log.py [ -s|-k field[= [+/-]string]] [-p field]
  where -s/-k is to strip or keep line which field match the string (can = and string can be prefixed with + or - to filter value) 
  and -p is the field to display 
  out put format will always contains the following :
  1506501858910:[JST-2017-09-27 17:44:18-910ms]: S3 OBJSTOHKGFDC03 TRACE
  epoc/time/type/hostname/level

  Sample :
  cat s3-0.log | /root/Dev/scality-tools/s3log.py -k name=S3  -s httpURL=/_/healthcheck/deep -p bodyLength
  To keep only name=S3 striping from result those with healcheck url and display the bodylength
  """
  sys.exit(0) 

def parseargs(argv):
  option={}
  try:
    opts, args = getopt.getopt(argv, "dhk:p:s:", ["help"])
  except getopt.GetoptError:
    print "Argument error"
    usage()
    sys.exit(9)
  for i,el in enumerate(opts):
    if '-d' in el:
      opts.pop(i)
      logger.setLevel(logging.DEBUG)
  for opt, arg in opts:
    #dummy.append(opt)
    if opt in ("-h", "--help"):
      usage()
      end(0)
    elif opt == '-s':
      if "strip" not in option.keys():
        option["strip"]={}
      if '=' in arg:
        option["strip"][arg.split('=')[0]]=arg.split('=')[1]
      else:
        option["strip"][arg]=""
    elif opt == '-k':
      if "keep" not in option.keys():
        option["keep"]={}
      if '=' in arg:
        option["keep"][arg.split('=')[0]]=arg.split('=')[1]
      else:
        option["keep"][arg]=""
    elif opt == '-p':
      if 'print' not in option.keys():
        option["print"]={}
      if '=' in arg:
        option["print"][arg.split('=')[0]]=arg.split('=')[1]
      else:
        option["print"][arg]=""
  return option




class logInput():
  def __init__(self,line="",option={}):
    self.count=0
    self.skip=0
    self.type="repd"
    self.debug=0
    self.line=line
    self.counter=0
    self.tz=time.strftime('%Z')
    self.struct={}
    self.strip={}
    self.keep={}
    self.option={}
    self.display={}
    self.lastValid=True
    if 'strip' in option:
      self.strip=option['strip']
    if 'keep' in option:
      self.keep=option['keep']
    if 'print' in option:
      self.display=option['print']
 
  def readLine(self,line):
    self.lastValid=True
    self.counter+=1
    self.line=line
    #logger.trace("Line {0}".format(self.line))

  def putLine(self,string="line"):
    if string == "line":
      print self.line
    elif string == "struct":
      print self.struct
    else:
      print 'no  line to display'
  
  def deserLine(self,format="standard"):
    try:
      self.struct=json.loads(self.line)
    except ValueError as e:
      logger.debug("Error parsing line #{0} : {1}".format(self.counter,self.line))
      self.lastValid=False
      
  def setType(self):
    self.type="repd"
  
  def getValue(self,param,struct=None,keep=True):
    if not param in self.struct.keys():
      logger.debug("Param not found {0} line {1}".format(self.count,param,self.line))
      #self.putLine()
      return()
    if not keep:
      ret=self.struct.pop(param)
    else:
      ret=self.struct[param]
    return(ret)

  def convertDate(self,epoch):
    ms=str(epoch)[-3:]
    epoch=int(epoch)/1000
    ret="[{2}-{0}-{1}ms]:".format(str(datetime.datetime.fromtimestamp(epoch)),ms,self.tz)
    return(ret)


  ''' 
  return true if condition match
  first letter of asked value can be math operator in which case values must be int
  '''
  def compareValue(self,asked,have):
    operator=asked[:1]
    if operator =="+":
      operator=">"
      asked=asked[1:]
    elif operator =="-":
      operator="<"
      asked=asked[1:]
    if operator not in ('>','<'):
      if str(asked) == str(have):
        return True
    else:
      ''' verify values before comparison '''
      for i in asked,have:
        try:
          int(i)
        except ValueError:
          logger.debug("{0} is not integer".format(i))
          return False
      if operator == '>':
        if int(have) > int(asked):
          return True
      else:
        if int(have) < int(asked):
          return True
    return False     
    
  def definedRules(self):
    line=self.line
  
  ''' parse field and return True if condition is meet
      return True if :
        what = skip and one field match
        what = keep and one field doesn't match
  '''
  def checkData(self,field,what):
    match=False
    k=self.struct.keys()
    ''' check all elements of field in line struct '''
    for f in field.keys():
      ''' look if strip value is in line struct. '''
      if f in k:
        ''' if there is no value for this just test existence in the struct '''
        if field[f] == "":
          logger.debug("field {0} empty stripped out from results {1}\n".format(f,field[f]))
          match=True
        #elif field[f] == self.struct[f]:
        elif self.compareValue(field[f],self.struct[f]):
          match=True
      if what == "strip" and match == True:
        return False 
      if what == "keep" and match == False:
        return False
      else:
        match=False
    return True   
    
  def defaultExtract(self):
    out=""
    if self.keep != {} :
      ret=self.checkData(self.keep,"keep")
      if ret == False:
        self.skip+=1
        return None
    if self.strip != {} :
      ret=self.checkData(self.strip,"strip")
      if not ret:
        self.skip+=1
        return None
    if 'level' in self.struct.keys():
      out=self.struct.pop('level').upper()+" "+out
    if 'hostname' in self.struct.keys():
      #out=self.struct.pop('hostname').upper()+" "+out
      out=self.struct['hostname'].upper()+" "+out
    out+=" % "
    ''' dont do yet content check for display option 
        Just display values in display oprion.
    '''
    filter=[]
    if self.display != {}:
      for i in self.display:
        value=self.getValue(i,keep=True)
        if value != None:
          cur="{0} : {1} ".format(str(i),value)
        out+=cur
      return(out)
    for el in self.struct.keys():
      cur="{0} : {1} ".format(str(el),str(self.struct[el]))
      out+=cur
    return(out)
    
  # Analyse the parsed result and display
  def analyseStruct(self):
    if self.lastValid == False:
      logger.error('Line {0} is not valid\n'.format(self.counter),level=self.error)
      return 9
    if self.type == "repd":
      self.name = self.getValue("name")
      if self.name == "Blob":
        payload = "Machine {0} {1} {2} port {3}".format(self.getValue("hostname"),self.getValue("message"),self.getValue("host"),self.getValue("port"))
      else:
        payload = self.defaultExtract()
      if payload == None:
        return None
      self.date = self.getValue("time",keep=False) 
      self.fulldate = self.convertDate(self.date)
      #print "{0}:{1} {2} {3}".format(self.date,self.fulldate,self.name,payload)
      print "{0}:{1} {2}".format(self.fulldate,self.name,payload)
    else:
      print "type {} not implemented".format(type)

 
def main():
  strip={}
  keep={}
  option={}
  option=parseargs(sys.argv[1:])
  Cur=logInput(option=option)
  for line in  sys.stdin:
    Cur.readLine(line)
    #Cur.putLine()
    Cur.deserLine()
    Cur.analyseStruct()
  
if __name__ == '__main__':
  main()
