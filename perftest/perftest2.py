#!/usr/bin/python3
import json
from datetime import datetime
import sys
from optparse import OptionParser

etalon_directory="/usr/share/scality-perftest/etalon"

def DD(msg,label="DD"):
  if debug == True:
    print("{} {}".format(label,msg))

parser = OptionParser()
parser.add_option("-b", "--baseline", dest="baseline",
   default="1site", help="Choose the baseline profile (1site|2sites|3sites|3nodes) (the default is 1site)")
parser.add_option("-d", "--debug", dest="debug", action="store_true",
   default=False, help="Enable debug mode")
parser.add_option("-e", "--exportfile", dest="exportfile",
   default="/tmp/export.json", help="pass the export.json file path (the default is /tmp/export.json)")
parser.add_option("-n", "--number", dest="number", action="store_true",
   default=False, help="Show performance number summary as tables")
parser.add_option("-p", "--profile", dest="profile",
   default="Average", help="Select the profile (Average|Acceptable|Worst|Best|Optimal) (the default is Average)")
parser.add_option("-r", "--getrt", dest="getrt", action="store_true",
   default=False, help="Get all the run timestamps")
parser.add_option("-s", "--state", dest="state",
   default="NOK", help="Choose all|NOK|OK to select the statuses (by defaut it prints only the NOK states)")
parser.add_option("-t", "--timestamp", dest="timestamp",
   default=None, help="Filter on timestamp (eg of accepted format: 2019-12-23 11)")
parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
   default=False, help="Print the details")
(options, args) = parser.parse_args()

debug=options.debug

connectors = []
connector_state = {}
countstats = {}
profiles = ['iops','bandwidth']

if options.state == "all":
    status_to_display = ("NOK","OK")
elif options.state == "NOK":
    status_to_display = ("NOK","MM")
elif options.state == "OK":
    status_to_display = ("OK","MM")

if options.baseline == '1site':
    baseline_file = "baseline_server-6nodes-1site.json"
elif options.baseline == '2sites':
    baseline_file = "baseline_server-6nodes-2sites.json"
elif options.baseline == '3sites':
    baseline_file = "baseline_server-6nodes-3sites.json"
elif options.baseline == '3nodes':
    baseline_file = "baseline_server-3nodes-1site.json"

prof = {"Optimal":1,"Best":1.5,"Average":2,"Acceptable":3,"Worst":5}
multiplier = prof[options.profile]

with open(options.exportfile) as docs:
    data = docs.readlines()

for con in data:
    c = json.loads(con)["connector"]
    profile = json.loads(con)['config']['profile']
    if "disk" in c:
            connectors.append("disk")
            p = '%s_%s' % ( "disk", profile )
            connector_state[p] = []
    elif "ssd" in c:
            connectors.append("ssd")
            p = '%s_%s' % ( "ssd", profile )
            connector_state[p] = []
    else:
        connectors.append(c)
        # c = target (disk/node ..) p = iop/BW 
        p = '%s_%s' % ( c, profile )
        connector_state[p] = []

connectors = set(connectors)

with open("{}/{}".format(etalon_directory,baseline_file)) as etalon:
    etalon_dict = json.load(etalon)

def evdoc(d):
  try:
      wavg = d["Write"]["avg_latency"]
      wmbps = d["Write"]["mbps"]
      ravg = d["Read"]["avg_latency"]
      rmbps = d["Read"]["mbps"]
      return (wavg,wmbps,ravg,rmbps)
  except:
      # why 10000 ? 
      return (10000,0,0,0)

def retetal():
    ewavg = etalon_dict[pcon]['write_avg']
    ewmbps = etalon_dict[pcon]['write_mbps']
    eravg = etalon_dict[pcon]['read_avg']
    ermbps = etalon_dict[pcon]['read_mbps']
    return (ewavg,ewmbps,eravg,ermbps)


def compare(base, etal, band=1):
    if band:
        if base*multiplier > etal:
            return  0
        else:
            return  1
    else:
        if base > etal*multiplier:
            return  1
        else:
            return  0

def check_state(d):
  ewavg,ewmbps,eravg,ermbps = retetal()
  wavg,wmbps,ravg,rmbps = evdoc(d)
  state = 0
  state += compare(wavg,ewavg,0)
  state += compare(wmbps,ewmbps,1)
  if state == 0:
     state = "OK"
  else:
      state = "NOK"
  return (state)

def parse_state(c):
  for con in c:
    if len(c[con]) == 0: output = "None"
    else: output = 'OK| The overall performances are better than the "%s" baseline profile' % options.profile
    for state in c[con]:
      if "NOK" in state['state']:
        output = 'NOK| The overall performances are worst than the "%s" baseline profile' % options.profile
    if "None" not in output:
      print("%s:%s" %  (con, output))

def print_dtm(dtm):
    return "%s-%s-%s %s" % (dtm.year, dtm.month, dtm.day, dtm.hour)

def str_to_dtm(datetime_str):
    return datetime.strptime(datetime_str, '%Y-%m-%d %H')

def timestamp_to_dtm(datetime_str):
    return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%fZ')

def ensure_datetime(d):
    return datetime(d.year, d.month, d.day, d.hour)

def compare_dtm(d1, d2):
    output =  cmp(ensure_datetime(d1), ensure_datetime(d2))
    if output == 0:  return True
    else: return False


def print_set(s):
    print('Date:%s' % s)

def fixtimeformat(datestr):
    #print('fixtimeformat {}'.format(datestr))
    goodlenght=datestr.split('.')[1][:-1][0:5]
    trunk=datestr.split('.')[0]
    datestr2=trunk+'.'+goodlenght+'Z' 
    if datestr != datestr2:
      DD('fixtimeformat out {}'.format(datestr))
    return datestr2 

def cmp(a, b):
    return (a > b) - (a < b)

def check_ts(dtm1, dtm2):
    if options.timestamp:
        #d1 = timestamp_to_dtm(dtm1)
        d1 = timestamp_to_dtm(fixtimeformat(dtm1))
        d2 = str_to_dtm(dtm2)
        if compare_dtm(d1, d2) == False:
            return True

if options.getrt:
  ts = []
  for i in  data:
    for v in connectors:
        d = json.loads(i)
        #d1 = timestamp_to_dtm(d["@timestamp"])
        d1 = timestamp_to_dtm(fixtimeformat(d["@timestamp"]))
        # change format 2025-02-10 01:11:04.686130 -> 2025-02-10 01:00:00
        df = ensure_datetime(d1)
        ts.append(print_dtm(df))
  #for i in map(print_set, set(ts)):
  for i in sorted(set(ts)):
    if i:
      print(i)

  sys.exit()

def parse_total_stats(p,stats):
  label="{} (lat/BW)".format(p)
  print('{:20}: {:>10} {:>10} {:>10} {:>10}'.format(label,'wavg','wmbps','ravg','rmbps'))
  for cat in stats.keys():
    count=stats[cat]['count']
    wavg=stats[cat]['wavg']
    wmbps=stats[cat]['wmbps']
    ravg=stats[cat]['ravg']
    rmbps=stats[cat]['rmbps']
    if count == 0:
      print('Error {}'.format(cat))
    else:
      label="{} [{}]".format(cat,count)
      print('{:20}: {:10} {:10} {:10} {:10}'.format(label,int(wavg/count),int(wmbps/count),int(ravg/count),int(rmbps/count)))

def add_stats(profile,v,wavg,wmbps,ravg,rmbps):
  if profile not in countstats.keys():
    countstats[profile] = {} 
  if v not in countstats[profile].keys():
    countstats[profile][v]={}
    countstats[profile][v]['count']=0
    countstats[profile][v]['wavg']=0
    countstats[profile][v]['wmbps']=0
    countstats[profile][v]['ravg']=0
    countstats[profile][v]['rmbps']=0

  countstats[profile][v]['count']+=1
  countstats[profile][v]['wavg']+=wavg
  countstats[profile][v]['wmbps']+=wmbps
  countstats[profile][v]['ravg']+=ravg
  countstats[profile][v]['rmbps']+=rmbps

for i in  data:
  for v in connectors:
    d = json.loads(i)
    DD(d)
    if check_ts(d["@timestamp"], options.timestamp): break
    if v in d["connector"]:
      profile = d['config']['profile']
      pcon = '%s_%s' % ( v, profile )
      host_info = "%s_%s_%s" % ( d["host"], d["connector"] , profile)
      state = check_state(d) # ret OK/NOK
      prof = "%s_%s" % (v , profile)
      #prof = "{}:::{}".format(v , profile)
      connector_state[prof].append({'component':host_info,'state':state})
      wavg,wmbps,ravg,rmbps = evdoc(d)
      add_stats(profile,v,wavg,wmbps,ravg,rmbps)
      if options.verbose and state in status_to_display :
        ewavg,ewmbps,eravg,ermbps = retetal()
        perf = "write_avg_ms:%s,write_avg_ms_baseline:%s,write_%s:%s,write_%s_baseline:%s" % (wavg,ewavg,profile,wmbps,profile,ewmbps)
        print('ts:%s,component:%s,status:%s,%s' % (d["@timestamp"], host_info, state, perf))

parse_state(connector_state)
print()
if options.number:
  for p in profiles:
    if p in countstats.keys():
      parse_total_stats(p,countstats[p])
    print()
