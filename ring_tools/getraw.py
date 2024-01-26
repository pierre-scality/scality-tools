#!/usr/bin/env python


import os
import sys
import base64
from scality.common import ScalDaemonException
from scality.daemon import DaemonFactory
#import getopt
ring="DATA_DEV"
passw="g00SibJQjxpq"
bootstrap="172.16.20.1"
args=sys.argv[1:]

def get_node(key, ip, adminport, chordport, ring=ring, login='root', password=passw):
    n = {'ip': ip, 'adminport': adminport, 'chordport': chordport}
    node_tmp = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=ring, passwd=password)
    node_addr = node_tmp.findSuccessor(key)['address']
    node_addr_l = node_addr.split(':')
    ip = node_addr_l[0]
    chordport = node_addr_l[1]
    adminport = int(n['adminport']) - int(n['chordport']) + int(chordport)
    n['ip'] = ip
    n['chordport'] = chordport
    n['adminport'] = adminport
    node = DaemonFactory().get_daemon("node", url='https://{0}:{1}'.format(n['ip'], n['adminport']), chord_addr=n['ip'], chord_port=n['chordport'], dso=ring, passwd=password)
    return node


class NodeException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def chunkMgrStoreGetRaw(node, op="get_raw", key="0", filename=None):
    try:
        et = node.chunkapiStoreOp(op=op, key=key, extra_params={"use_base64": "1"})
    except Exception as e:
        raise NodeException("cannot get data " + str(e))

    for s in et.findall("result"):
        status = s.find("status").text
        if status != "CHUNKAPI_STATUS_OK":
            if status == "CHUNKAPI_STATUS_NOT_FOUND":
                raise NodeException("chunk not found")
            else:
                raise NodeException("error: status %s" % status)
        data = s.find("data").text
        use_base64 = False
        umddata=None
        # uncomment below to see result struct
        #for x in s:
        #       print x
        size=s.find("size").text
        try:
            use_base64 = s.find("use_base64").text
            if int(use_base64) == 1:
                use_base64 = True
        except:
            pass
        umddata=s.find("usermd").text
        umddata=base64.b64decode(umddata).decode("iso8859-1").rstrip()
        print "key : {0} , usermd {1}".format(key,umddata)
        if use_base64 is True:
            if int(size) == 0:
                print "Empty object "+str(key)
                data=""
            else:
                data = base64.b64decode(data).decode("iso8859-1")
        if filename is not None:
            try:
                f = open(filename, "w")
                f.write(data.encode("iso8859-1"))
                f.close()
                print "%d bytes of data saved in %s" % (len(data), filename)
            except Exception, e:
                raise NodeException("Cannot save data in %s: %s" % (filename, str(e)))
        else:
            print data
        break
    else:
        raise NodeException("XCommand returned an error")

for i in args:
        KEY=i
        #KEY = "147E7E128A91DA5809E39F205C2FDC000F200720"
        n = get_node(KEY,bootstrap, 6449, 4249)
        filename="/tmp/"+i+".txt"
        chunkMgrStoreGetRaw(n, key=KEY, filename=filename)

