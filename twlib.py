import twitter as tw
from pdb import set_trace
import time
import re
import numpy as np
import urllib2
import smtplib

class twSocket:

    def __init__(self, ibsock):
        self.auths = \
            [ tw.OAuth( \
              consumer_key='lbXi5nIK19eQy608cKqQ0BlXt', \
              consumer_secret='xk5UN9VxS2IKVNF3nFFeXftIvO3ZUvZHq3aN5GbrLgkmJE3YME', \
              token='2776510801-rbNCNtaWsLL4wUfadYMozdXZ5kfZntor0k7smpz', \
              token_secret='l6T3CQZEHPUzqwe6OkKcQOJ2jRAi88BEGuF01hDZvPaao' ), \
              tw.OAuth( \
              consumer_key='tLQ7mqTw9efbhtZwnSlZaNPmj', \
              consumer_secret='rNbvnEc8kMaSNsJTJSKN5VcycdN8AFeWz0GyDxxk4MOIIgNZkq', \
              token='2776510801-X69JIpQ7RrZY11V0RE231aidIFkMpfLaATxBWdD', \
              token_secret='s2VWTOKCSGfPwZVwBanuLy6raBglZmhjLooZPfIMlM4Gn' ), \
              tw.OAuth( \
              consumer_key='Sz3VruE25rxIXiryEjdioyWdJ', \
              consumer_secret='HUDbzAoyJtJnxCoaK4XYyj1IRpwDtsISBZg6x7m6Sh0mg2oW7r', \
              token='2776510801-EVBOEmy1rdyTf8G3FBabRUhuiv5ov7vBbfPpKuk', \
              token_secret='FT4SREVvx7VZetn2LuoEZIbjA33SfK7V9NHZFu4kDWie7' ), \
              tw.OAuth( \
              consumer_key='wiV8QgaxW8eBSk1tA9IpuMIhk', \
              consumer_secret='SbI3ffECMirxNv4XlT7LIOSKsSgGqEjjR9rJCWIK6DK6LLinoa', \
              token='2776510801-eOIS6G2BHvhDyCa07NmwYNPbzGSolDD0GD7ZXsp', \
              token_secret='eIc0VBaHTVkckC7usAjOZBtdjMpKwwh2NEvxHxIzdDdh6' ) ]

        self.twauth = [ tw.Twitter(auth=self.auths[0]), \
                        tw.Twitter(auth=self.auths[1]), \
                        tw.Twitter(auth=self.auths[2]), \
                        tw.Twitter(auth=self.auths[3])  ]
        self.active_auth = 0
        self.auth_wakeup_time = np.zeros(len(self.twauth))

        self.ibsock = ibsock    # use ibsock to reqCurrentTime / ping to maintain ib connectivity
        self.gmt_min = 0
        self.ib_server_time = 0
        self.ib_connect = True

        self.last_twid = np.loadtxt('last_twid.log')
        self.trade_symbol = [re.compile('TRADE'), re.compile('ES'), re.compile('ADJ.'), \
                             re.compile('ADJUST'), re.compile('MOVE'), re.compile('CLOSED'), re.compile('PLACED')]
        self.default_stop = 4.
        self.max_stop = 10.
        self.sleep_time = 5.1

    def errorHandler(self, err):
        """ twitter HTTP error handler """
        print(time.ctime())
        print('TW', err.message)
        code_loc = re.search('status', err.message).start()
        errcode = int( err.message[code_loc:].split()[1] )
        if errcode in [420,429]:
            print('TW Error: rate limit excessed, retry in 15 min')
            time.sleep(15*60.+1.)
        elif errcode in [500,502,503,504]:
            print('TW Error: Twitter unavailable for now, retry in 1 min')
            time.sleep(60.)
        else:
            print('TW Error: other error, retry in 1 min')
            time.sleep(60.)

    def detectTrade(self, text):
        """ detect if the message is an ES trade """
        if self.trade_symbol[0].search(text) is not None:
            if self.trade_symbol[1].search(text) is not None:
                return True
        if self.trade_symbol[1].search(text) is not None:
            if (self.trade_symbol[2].search(text.upper()) is not None) or \
               (self.trade_symbol[3].search(text.upper()) is not None) or \
               (self.trade_symbol[4].search(text.upper()) is not None) or \
               (self.trade_symbol[5].search(text.upper()) is not None) or \
               (self.trade_symbol[6].search(text.upper()) is not None):
                return True

    def send_alert(self, alert, message):
        alert_server = smtplib.SMTP('smtp.gmail.com',587)
        alert_server.starttls()
        alert_server.login(alert['username'], alert['password'])
        msg = 'From: %s To: %s Subject: %s' % \
              (alert['username'], alert['to'], message)
        alert_server.sendmail(alert['username'], alert['to'], msg)
        alert_server.quit()

    def listener(self, alert):
        alert_count = 0
        time.sleep(self.sleep_time)
        while True:
            # check ib connectivity
            if time.gmtime().tm_min != self.gmt_min:    # ping IB every minute
                self.gmt_min = time.gmtime().tm_min
                self.ibsock.tws.reqCurrentTime()
                time.sleep(.75)
                if self.ib_server_time != self.ibsock.server_time[-1]:    # connection OK
                    self.ib_server_time = self.ibsock.server_time[-1]
                    if not self.ib_connect:
                        self.ib_connect = True
                        print('IB connection re-established.')
                else:                                                     # connection lost
                    print(time.ctime())
                    print('IB connection lost! Retrying connection in 10 sec ...')
                    if alert_count < 3:
                        self.send_alert(alert, 'IB connection lost!')
                        alert_count += 1

                    self.ib_connect = False
                    self.ibsock.tws.disconnect()
                    time.sleep(10.)
                    self.ibsock.tws.connect()
                    time.sleep(5.)
            
            if self.ib_connect:
                # check twitter updates
                try:
                    msg = self.twauth[self.active_auth].statuses.user_timeline( \
                          screen_name='premiumtrades', count=1)
                    if msg[0]['id'] != self.last_twid:
                        self.last_twid = msg[0]['id']
                        f = open('last_twid.log','w')
                        f.write(str(self.last_twid))
                        f.close()
                        # replace 'SWING' by 'TRADE'
                        msg[0]['text'] = re.sub('SWING','TRADE', msg[0]['text'])
                        if self.detectTrade(msg[0]['text']):
                            return msg[0]['text']
                    time.sleep(self.sleep_time)
                except tw.api.TwitterHTTPError as err0:
                    if alert_count < 10:
                        self.send_alert(alert, err0.message[:50])
                        alert_count += 1
                    self.errorHandler(err0)

                except urllib2.URLError as err1:
                    print(time.ctime())
                    print('URLError 110: connection timed out on auth: ', self.active_auth)
                    self.auth_wakeup_time[self.active_auth] = time.time() + 15.*60. + 5.
                    self.active_auth = np.argmin(self.auth_wakeup_time)
                    if self.auth_wakeup_time[self.active_auth] < time.time():
                        print('Switch to auth: ', self.active_auth)
                    else:
                        delay = self.auth_wakeup_time[self.active_auth] - time.time()
                        print('All auth lost, retry in sec: ', delay+.1)
                        if alert_count < 10:
                            self.send_alert(alert, 'All auth lost!')
                            alert_count += 1
                        time.sleep(delay+.1)
                    

    def actionParser(self, msg):
        """ parse raw trade action """
        action = {}
	msg = re.sub(' of ', ' ', msg)
        msg = re.sub(' on ', ' ', msg)
        msg = re.sub(' at ', ' ', msg)
        msg = re.sub('-', ' ', msg)
        msg = re.sub('\n', ' ', msg)
        msg = re.split(':|,|\ |;', msg)
        filter_empty = lambda txt: txt!=u''
        msg = [word for word in msg if filter_empty(word)]

        TRADEloc = 0
        for ii in range(len(msg)):    # locate TRADE
            if re.search('TRADE', msg[ii]) is not None:
                TRADEloc = ii
                break
        for ii in np.r_[TRADEloc:len(msg)]:    # locate $ES
            if re.search('ES', msg[ii]) is not None:
                ESloc = ii
                break
        if 'ESloc' not in vars():
            return None

        # position close, action: type, percent, side
        try:
            for jj in np.r_[TRADEloc:len(msg)]:
                if re.search('CLOSE', msg[jj].upper()) is not None:
                    action['type'] = 'CLOSE'
                    percent = 100.    # default: close all remaining position
                    for ii in np.r_[2:ESloc]:
                        percent_str = re.findall(r'\d*\%', msg[ii])
                        if percent_str != []:
                            percent = float(percent_str[0][:-1])
                            break
                    action['percent'] = min(percent,100.)
    
                    if re.search('LONG', msg[ESloc+1].upper()) is not None:
                        action['side'] = 'BUY'
                    elif re.search('SHORT', msg[ESloc+1].upper()) is not None:
                        action['side'] = 'SELL'
                    else:
                        print('TW warning: close position side absent.')
                        action['side'] = None
                    return action
        except IndexError:
            print('TW warning: ambiguous post.')
            if ('percent' in action.keys()) and ('side' not in action.keys()):
                action['side'] = None
                return action
            if ('percent' not in action.keys()) and ('side' not in action.keys()):
                action['percent'] = 100.
                action['side'] = None
                return action
            else:
                return None

        # trade initiation, action: type, entry_price, stop_price, side
        try:
            if re.search('LONG', msg[ESloc-1].upper()) is not None:
                action['type'] = 'INIT'
                action['side'] = 'BUY'
            elif re.search('SHORT', msg[ESloc-1].upper()) is not None:
                action['type'] = 'INIT'
                action['side'] = 'SELL'
            elif re.search('LONG', msg[ESloc-2].upper()) is not None:
                action['type'] = 'INIT'
                action['side'] = 'BUY'
            elif re.search('SHORT', msg[ESloc-2].upper()) is not None:
                action['type'] = 'INIT'
                action['side'] = 'SELL'
        except IndexError:
            pass

        if ('type' in action.keys()) and (action['type']=='INIT'):
            ENTRYloc = 0
            for ii in [1,2,3]:    # entry price
                try:
                    entry_price = re.findall(r'\d*\.\d+|\d+', msg[ESloc+ii])
                    if len(entry_price) == 1:
                        ENTRYloc = ESloc+ii
                        action['entry_price'] = float(entry_price[0])
                        break
                except IndexError:
                    break
            if 'entry_price' not in action.keys():
                action['entry_price'] = None

            for ii in np.r_[ESloc+1:len(msg)]:    # stop price
                if (re.search('STOP', msg[ii].upper()) is not None) or \
                   (re.search('STO', msg[ii].upper()) is not None) or \
                   (re.search('STP', msg[ii].upper()) is not None) or \
                   (re.search('TOP', msg[ii].upper()) is not None):
                    STPloc = ii
                    break
            if 'STPloc' in vars():
                for ii in np.r_[max(STPloc-2, ESloc+1, ENTRYloc+1) : STPloc+2]:
                    try:
                        stop_price = re.findall(r'\d*\.\d+|\d+', msg[ii])
                        if len(stop_price) == 1:
                            if float(stop_price[0]) <= self.max_stop:
                                action['stop_price'] = float(stop_price[0])
                                break
                    except (IndexError, UnboundLocalError):
                        break
            if 'stop_price' in action.keys():
                return action
            else:
                action = {}

        # move stop, action: [type] OR [type, percent, side]
        has_stop, has_flat = False, False
        for ii in range(len(msg)):
            if (re.search('STO', msg[ii].upper()) is not None) or \
               (re.search('STP', msg[ii].upper()) is not None) or \
               (re.search('TOP', msg[ii].upper()) is not None):
                has_stop = True
            if re.search('FLAT', msg[ii].upper()) is not None:
                has_flat = True

        if has_flat and has_stop:    # move stop to flat
            action['type'] = 'FLAT_STP'
            return action
        if has_stop and not has_flat:    # stopped, close position
            action['type'] = 'CLOSE'
            action['percent'] = 100.
            action['side'] = None
            return action

        return None
       
  

if __name__ =='__main__':
    socket = twSocket()
    while True:
        msg = socket.listener()
        if not isinstance(msg, bool):
            action = socket.actionParser(msg)
            print(action)
