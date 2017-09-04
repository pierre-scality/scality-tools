#! /usr/bin/python

import sys
import json
import datetime,time
import getopt

def logerror(line):
  sys.stderr.write('{0}'.format(line))

def usage():
  print "cat file | s3log.py [ -s field[:string]]"
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
      option["debug"]="debug"
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
  def __init__(self,line="",pipe=False,option={}):
    self.count=0
    self.skip=0
    self.pipe=pipe
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
    if self.pipe == False:
      self.line=line
    else:
      logerror("readline pipe true no implemented")  

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
      logerror("Error analsying line #{0}".format(self.counter))
      logerror(self.line)
      self.lastValid=False
      
  def setType(self):
    self.type="repd"
  
  def getValue(self,param,struct=None,keep=True):
    if not param in self.struct.keys():
      logerror("Structure is not as expected {0} line {1}".format(self.count,param))
      self.putLine()
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
    #logerror("DEBUG {0} : {1} \n".format(asked,have))
    if operator not in ('>','<'):
      if str(asked) == str(have):
        return True
    else:
      #logerror("DEBUG {0} : {1} \n".format(asked,have))
      ''' verify values before comparison '''
      for i in asked,have:
        try:
          int(i)
        except ValueError:
          logerror("{0} is not integer".format(i))
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
      #logerror("DEBUG {0} : {1}  {2}\n".format(f,field[f],what))
      ''' look if strip value is in line struct. '''
      if f in k:
        ''' if there is no value for this just test existence in the struct '''
        if field[f] == "":
          logerror("field {0} stripped out from results")
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
    

  def analyseStruct(self):
    if self.lastValid == False:
      #sys.stderr.write('Line {0} is not valid\n'.format(self.counter))
      logerror('Line {0} is not valid\n'.format(self.counter))
      return 9
    if self.type == "repd":
      self.name = self.getValue("name")
      if self.name == "Blob":
        payload = "Machine {0} {1} {2} port {3}".format(self.getValue("hostname"),self.getValue("message"),self.getValue("host"),self.getValue("port"))
      else:
        payload = self.defaultExtract()
      if payload == None:
        #logerror("Line skipped")
        return None
      self.date = self.getValue("time",keep=False) 
      self.fulldate = self.convertDate(self.date)
      print "{0}:{1} {2} {3}".format(self.date,self.fulldate,self.name,payload)
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
