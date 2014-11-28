#!/usr/bin/python2

import os 
import sys 
import getopt


PRGNAME=os.path.basename(sys.argv[0])


"""
ringStatus 
Node: node1-n4 192.177.1.11:8087 0000000000000000000000000000000000000000 RUN
ringsh.tx
supervisor nodeAssignId RING Server10 8085 CE38E38EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA40

"""

def usage(code=0):
        message="usage : "+PRGNAME
        add="""
        -f supervisor ringStatus format file
        -F sprov ringsh.txt format file
"""
        print(message+add)
        if __name__ != "__main__":
            #exit(code)
            print "exit"

def parseargs(argv):
        if len(argv)==0:
                print "ERROR : Need Arg"
                usage(1)
                #sys.exit(1)
        if len(argv)==1:
                k=sys.argv[1] 
        try:
                opts, args = getopt.getopt(argv, "hf:F:", ["help"])
        except getopt.GetoptError:
                print "Argument error"
                usage()
        #for i,el in enumerate(opts):
        for opt, arg in opts:
                if opt in ("-h", "--help"):
                        usage(0)
                elif opt == '-f':
                        files[arg]='T1'
                elif opt == '-F':
                        files[arg]='T2'



files={}
parseargs(sys.argv[1:])
keyspace=[]
node={}
FF='F'*40

# T1 type supervisor ringStatus (need to strip on Node:)
# Node: bgsc409139-node4 172.27.206.130:8087 8000000000000000000000000000000000000080 RUN, BAL(DST)
# T2 sprov keyspace output
# supervisor nodeAssignId DSO Server8 8086 2E38E38EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA80
# keyspace struct is KEY IP:PORT NAME (if defined only with ringstatus) 

class KS:
        def __init__(self):
            self.keyspace=[]

        def keyAdd(self,el,type):
            this=[]
            if len(el) == 0:
                return self.keyspace
            if type == 'T1':
                if el[0] != 'Node:':
                    #print "not Node: "+str(line)
                    return self
                this.append(el[3])
                this.append(el[2])
                this.append(el[1])
                servername=el[1].split('-')[0]
                this.append(servername)
                self.keyspace.append(this)
            elif type == 'T2': 
                this.append(el[5])
                this.append(el[3]+":"+el[4])
                this.append(el[3]+"-"+el[4])
                #this.append(None)
                this.append(el[3])
                self.keyspace.append(this)
            #print this
            return self.keyspace
        
        def ordered(self):
            self.keyspace.sort()

        def show(self,entry=-1):
            if entry == -1:
                for el in self.keyspace:
                    #print el
                    print "{0:45s}{1:45s}{2:45s}{3}".format(el[0],el[1],el[2],el[3])
            else:
                return self.keyspace[entry]

        def size(self):
            return len(self.keyspace)

        def load(self,file,type):
            try:
                f = open(file)
            except IOError as e :
                print e
                print 'impossible to open %s for read' % file
                exit(9)
            while True:
                l=f.readline()
                if not l:
                    break
                else:
                    line=l.split()
                    self.keyAdd(line,type)
            

keyspace=KS()

for file in files.keys():
    keyspace.load(file,files[file])

keyspace.ordered()
keyspace.show()
#['B8E38E39AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA80', '172.27.206.133:8085', 'bgsc409142-node2', 'bgsc409142']

serverkey={}
# serverkey[server]=[nb,??]

for i in range(keyspace.size()):
        # Calculate keyrange
        # Last element add K to 0 then 0 to first K.
        #if i == len(keyspace)-1:
        if i == keyspace.size()-1:
            succ=keyspace.show(i)[0]
            nb=int(FF,16)-int(keyspace.show(i)[0],16)+int(keyspace.show(0)[0],16)
        else:
            succ=keyspace.show(i+1)[0]
            #succ=keyspace[i+1][0]
            nb=int(succ,16)-int(keyspace.show(i)[0],16)
        # if node name exist diaplay else display ip:port
        ### >>> check if entry already exists
        if keyspace.show(i) not in serverkey.keys():
            serverkey[keyspace.show(i)[0]]=nb
            serverkey[keyspace.show(i)[3]]=keyspace.show(i)[0]
        else:
            serverkey[keyspace.show(i)]=serverkey[node[keyspace.show(i)]]+nb
        print keyspace.show(i)[2],"\t",keyspace.show(i)[0],succ,nb

if __name__ == "__main__":
    exit()

