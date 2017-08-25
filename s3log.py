#! /usr/bin/python

import sys
import json
import datetime,time

def logerror(line):
  print line

class logInput():
  def __init__(self,line,pipe=True,strip={}):
    self.count=0
    self.pipe=pipe
    self.type="repd"
    self.debug=0
    self.line=line
    self.counter=0
    self.tz=time.strftime('%Z')
    self.strip=strip

  def readLine(self):
    if self.pipe == True:
      self.line=sys.stdin.readline()

  def putLine(self,string="line"):
    if string == "line":
      print self.line
    elif string == "struct":
      print self.struct
    else:
      print 'no  line to display'
  
  def deserLine(self,format="standard"):
    self.counter+=1
    try:
      self.struct=json.loads(self.line)
    except ValueError as e:
      print "Error analsying line #{0}".format(self.counter)
      print self.line
      
  def setType(self):
    self.type="repd"
  
  def getValue(self,param,struct=None,keep=False):
    if not param in self.struct.keys():
      logerror("Structure is not as expected {0} line".format(self.count))
      self.putLine()
      return()
    if not keep:
      ret=self.struct.pop(param)
    else:
      ret=self.struct[param]
    return(ret)

  def convertDate(self,epoch):
    ms=str(epoch)[-3:]
    epoch=epoch/1000
    ret="[{2}-{0}-{1}ms]".format(str(datetime.datetime.fromtimestamp(epoch)),ms,self.tz)
    return(ret)

  def stripData(self):
    field=self.field
    k=self.struct.keys()
    for f in field.keys():
      if f in k:
        if field[f] == Null:
          return 1
        elif field[f] == self.struct[f]:
          return 1
    return 0    
    

  def defaultExtract(self):
    out=""
    skip=0
    if self.strip != {} :
      skip=self.stripData()
    if skip:
      return None
    if 'level' in self.struct.keys():
      out=self.struct.pop('level').upper()+" "+out
    if 'hostname' in self.struct.keys():
      out=self.struct.pop('hostname').upper()+" "+out
    out+=" % "
    for el in self.struct.keys():
      cur="{0} : {1} ".format(str(el),str(self.struct[el]))
      out+=cur
    return(out)
    

  def analyseStruct(self):
    if self.type == "repd":
      #if name == "Connection":
      self.name = self.getValue("name")
      if self.name == "Blob":
        payload = "Machine {0} {1} {2} port {3}".format(self.getValue("hostname"),self.getValue("message"),self.getValue("host"),self.getValue("port"))
      else:
        payload = self.defaultExtract()
      if payload == None:
        logerror("Line skipped")
      self.date = self.getValue("time") 
      self.fulldate = self.convertDate(self.date)
      print "{0}:{1} {2} {3}".format(self.date,self.fulldate,self.name,payload)
    else:
      print "type {} not implemented".format(type)

 
def main():
  for line in  sys.stdin:
    Cur=logInput(line,strip={})
    #Cur.readLine()
    #Cur.putLine()
    Cur.deserLine()
    Cur.analyseStruct()
  
if __name__ == '__main__':
  main()
