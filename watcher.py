from twlib import *
from iblib import *
from managerlib import *
import smtplib

"""
    WARNING: 
    1. Do not enter / exit trades manually when
       watcher is running. Exit watcher, do it manually, 
       then restart watcher.
    2. Always clean all positions / orders before launching watcher.
"""

alert = {'username': 'voilasept@gmail.com', \
         'password': 'Al#4Vic!hAnMa', \
         'to': '6177687947@txt.att.net'}

ib_connection_time = 2.
param_filename = 'param.txt'

ibsock = ibSocket()
twsock = twSocket(ibsock)
time.sleep(ib_connection_time)
manager = tradeManager(ibsock, param_filename)

while True:
    msg = twsock.listener(alert)
    if not isinstance(msg, bool):
        action = twsock.actionParser(msg)
        if (action is not None) and ( len(action.keys()) > 0 ):
            print('WT raw action detected: ', action)
            manager.param.update( param_filename )
            manager.synthesize_action(action)
