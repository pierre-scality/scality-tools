# Corrected version of evaluate_perfs.py

## General purpose
evaluate_perfs.py has been written in python 2 and some functions were broken.
This script uses the /tmp/exports.json to find out if the perf numbers are ok.
It doesn't show numbers which are in the json file.

This script asses both issues by adding a -n option to display the avg numbers and fixes part of code that was not working.
A simple debug mode has also been added.

## Usage 

```
Options:
  -h, --help            show this help message and exit
  -b BASELINE, --baseline=BASELINE
                        Choose the baseline profile
                        (1site|2sites|3sites|3nodes) (the default is 1site)
  -d, --debug           Enable debug mode
  -e EXPORTFILE, --exportfile=EXPORTFILE
                        pass the export.json file path (the default is
                        /tmp/export.json)
  -n, --number          Show performance number summary as tables
  -p PROFILE, --profile=PROFILE
                        Select the profile
                        (Average|Acceptable|Worst|Best|Optimal) (the default
                        is Average)
  -r, --getrt           Get all the run timestamps
  -s STATE, --state=STATE
                        Choose all|NOK|OK to select the statuses (by defaut it
                        prints only the NOK states)
  -t TIMESTAMP, --timestamp=TIMESTAMP
                        Filter on timestamp (eg of accepted format: 2019-12-23
                        11)
  -v, --verbose         Print the details

```

## Hack fixes
### cmp function 
It compares 2 things but has not been ported to py3.
A simple cmp has been added in the script
```
def cmp(a, b):
    return (a > b) - (a < b)
```
### map function 
It was broken, it has been replace by a loop on the sorted set

```
  #for i in map(print_set, set(ts)):
  for i in sorted(set(ts)):
    if i:
      print(i)
```

### Date format 
For an unknow reason the millisec length has changed in result json and do not work with date time format.
A function to remove the additional number has been added (debugging the issue would have been better ...)
```
def fixtimeformat(datestr):
    goodlenght=datestr.split('.')[1][:-1][0:5]
    trunk=datestr.split('.')[0]
    datestr2=trunk+'.'+goodlenght+'Z'
    if datestr != datestr2:
      DD('fixtimeformat out {}'.format(datestr))
    return datestr2
```
This fix enable the -r and -t option to work again

### stats display 
-n option will calculate and display stats.
This is mainly implemented in the add_stats function.
```
add_stats(profile,v,wavg,wmbps,ravg,rmbps)
```
It is then calle in this code : 
```
if options.number:
  for p in profiles:
    if p in countstats.keys():
      parse_total_stats(p,countstats[p])
    print

```



# note  
The tabs have been adjusted and gradually replaced by space
