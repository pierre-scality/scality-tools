# Simple tool to interact with ec2 labs

## General purpose
Purpose of this tool is to get ride of GUI to do base ec2 operations list, start, stop and terminate instances (it doesn't clean up anything).
It does list only instances from a given user (based on user tag). 
The default region is ap-northeast-1 and user pierre.merle@scality.com

You can change the region with -r flag

You can also use environement variables to change both region and owner 
```
$ export MYOWNER=me.myself@scality.com 
$ export MYREGION=us-east-1 
```

## EC2 creds 
Before running the tool you need to get creds from onelogin (ie : export AWS_ACCESS_KEY_ID="ASIAYKVURKFXQAAARYOQ" ...)
It should be working with aws sso setting as well.

## Usage 

```
usage: ec2tool.py [-h] [-d] [-r REGION] [-v]

  Display and trigger actions against ec2 instances
  ec2tools.py                                 => No args display all machines for a given owner (hardcoded for now)
  ec2tools.py <action> <expr>                    => Start machines matching pattern for a given owner (hardcoded for now)
        --> expr is a string that will be matched against the instance name tag

  Possible action are ('start', 'stop', 'terminate')
  Region/User hardcoded you can use env variable MYREGION/MYOWNER.
  Supported regions are : ['eu-north-1', 'us-west-2', 'ap-northeast-1', 'ap-southeast-2']

options:
  -h, --help            show this help message and exit
  -d, --debug           Set script in DEBUG mode
  -r REGION, --region REGION
                        Set script in DEBUG mode
  -v, --verbose         verbose mode

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

## Regex query 
To get a given lab machine just choose a part of the machine name (it works stop/start/terminate).
```
Manjaro ec2tool  [master] $ ./ec2tool.py start ceg
INFO            : Getting instances list ap-northeast-1
QUERY           : Do you want to start this 13 vm(s) ? (ctrl C to abort)
pme_ceg_cifs-1 pme_ceg_store-6 pme_ceg_wit-2 pme_ceg_store-4 pme_ceg_supervisor pme_ceg_store-5 pme_ceg_cifs-0 pme_ceg-new1 pme_ceg-new3 pme_ceg-new2 pme_ceg-new4 pme_ceg-s3c1 pme_ceg-sup2 : 

```

## Operation confirmation 
When you run an operation, you just have to type enter to validate it. Only terminate requires to confirm with "yes"
```
Manjaro ec2tool  [master] $ ./ec2tool.py terminate pme_ceg_wit-2
INFO            : Getting instances list ap-northeast-1
QUERY           : Do you want to terminate this 1 vm(s) ? (ctrl C to abort)
pme_ceg_wit-2 : 
QUERY           : Do you really want to terminate ['i-02253818f5f6b8b36'].
Type 'yes' to confirm : 
```
