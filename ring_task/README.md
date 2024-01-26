# ring_tasks.py

## Summary

Wrapper around ringsh supervisor ringTasks to follow task advancement with task pace. Work by default with balance but any task can be monitored. 
The speed calculation is a simple calculation between previous and current step / time interval (default 60s)

### Usage

'''
        ./ring_task3.py
        -l list of task to display tasks (default move), list list move,rebuild ..
        -r ring on which run the check 
        -t interval between checks (if set to 0 will exit after first iteration)
'''

To see all task use -l all 

## Version

'''
ring_task3.py -> python3 
ring_task3.py -> initial python2 (not maintained)
'''

## Sample 


