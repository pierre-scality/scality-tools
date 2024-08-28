# Simple tool to interact with ec2 labs

## General purpose
Purpose of this tool is to get ride of GUI to do base ec2 operations list, start, stop and terminate instances (it doesn't clean up anything).
It does list only instances from a given user (based on user tag). 
The username is hardcoded in the script.
You can change it by modifying this variable OWNER='pierre.merle@scality.com'

The default region is ap-northeast-1 but you have -r option to change it.


## Usage 

```
usage: ec2tool.py [-h] [-d] [-v]

  Display and trigger actions against ec2 instances
  ec2tools.py                           => No args display all machines for a given owner (hardcoded for now)
  ec2tools.py <action> <expr>           => Start machines matching pattern for a given owner (hardcoded for now)
        --> expr is a string that will be matched against the instance name tag

 possible action are ('start', 'stop', 'terminate')

options:
  -h, --help     show this help message and exit
  -d, --debug    Set script in DEBUG mode
  -v, --verbose  It will display the request to repd

```

## Default view 
When running command without option it will show you a view with all instances info belonging to the owner with the EIP when one is available and the autostop tag.

```
Manjaro ec2tool  [master] $ ./ec2tool.py 
INFO            : Getting instances list ap-northeast-1
i-0234ecfdeb2e52996 State : running    Name : pme-arte6demostorage-1 Owner : pierre.merle@scality.com Autostop : nightly_ap_tokyo : Private 10.0.11.220      [ EIP 52.69.234.89 ]
i-01cf67a919a616dcf State : running    Name : pme-arte6demostorage-2 Owner : pierre.merle@scality.com Autostop : nightly_ap_tokyo : Private 10.0.1.149      
i-002c6ec8487144cd8 State : running    Name : pme-arte6demostorage-3 Owner : pierre.merle@scality.com Autostop : nightly_ap_tokyo : Private 10.0.1.132      
```
