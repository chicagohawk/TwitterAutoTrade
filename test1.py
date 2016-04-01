import twitter as tw
from pdb import set_trace
import time
import numpy as np
import re

class twSocket:

    def __init__(self):
        self.auths = [ \
            tw.OAuth( \
                consumer_key='lbXi5nIK19eQy608cKqQ0BlXt', \
                consumer_secret='xk5UN9VxS2IKVNF3nFFeXftIvO3ZUvZHq3aN5GbrLgkmJE3YME', \
                token='2776510801-rbNCNtaWsLL4wUfadYMozdXZ5kfZntor0k7smpz', \
                token_secret='l6T3CQZEHPUzqwe6OkKcQOJ2jRAi88BEGuF01hDZvPaao' ), \
            tw.OAuth( \
                consumer_key='tLQ7mqTw9efbhtZwnSlZaNPmj', \
                consumer_secret='rNbvnEc8kMaSNsJTJSKN5VcycdN8AFeWz0GyDxxk4MOIIgNZkq', \
                token='2776510801-dDb465XLDcqsMODw7y4qcSfByyrrLDf4aWVdA8G', \
                token_secret='81egIP2MqQF3aDxMsll5fX7fuDi2w0GH29o5ey39ghqJv' ), \
            tw.OAuth( \
                consumer_key='tcisclFNiZzG461eZoOIunGuG', \
                consumer_secret='XMSZjIo1KHzXTLmU8nqALc40coSBs1WDqb52rxS6OZgusbLEXU', \
                token='2776510801-EVBOEmy1rdyTf8G3FBabRUhuiv5ov7vBbfPpKuk', \
                token_secret='FT4SREVvx7VZetn2LuoEZIbjA33SfK7V9NHZFu4kDWie7' ), \
            tw.OAuth( \
                consumer_key='GlCjgzCpezgKbhBNVVAVI8UUk', \
                consumer_secret='lIcyR3tQEaBw2SCtPdeNr1neY6U2wnJNpIZLhFwRskN3FGmfhg', \
                token='2776510801-eOIS6G2BHvhDyCa07NmwYNPbzGSolDD0GD7ZXsp', \
                token_secret='eIc0VBaHTVkckC7usAjOZBtdjMpKwwh2NEvxHxIzdDdh6' ) ]

        self.tws = [ tw.Twitter(auth=self.auths[0]), \
                     tw.Twitter(auth=self.auths[1]), \
                     tw.Twitter(auth=self.auths[2]), \
                     tw.Twitter(auth=self.auths[3]) ]

        self.last_twid = 0
        self.trade_symbol = [re.compile('TRADE:'), re.compile('\$ES')]
        self.default_stop = 4.
        self.max_stop = 8.
        

    def errorHandler(self, err):
        """ twitter HTTP error handler """
        print(err.message)
        code_loc = re.search('status', err.message).start()
        errcode = int( err.message[code_loc:].split()[1] )
        if code in [420,429]:
            print('Error: rate limit excessed!')
        elif code in [500,502,503,504]:
            print('Error: Twitter unavailable for now!')
        else:
            print('Error: other error!')
        set_trace()

    def detectTrade(self, text):
        """ detect if the message is an ES trade """
        if self.trade_symbol[0].search(text) is not None:
            if self.trade_symbol[0].search(text).start() in [0,1]:
                if (self.trade_symbol[1].search(text) is not None):
                    return True

    def listener(self):
        msg = self.tws[0].statuses.user_timeline(screen_name='premiumtrades', count=200)
        # 678581894594850816
        for ii in range(len(msg)):
            if self.detectTrade( msg[ii]['text'] ):
                print re.sub('\n', ' ', msg[ii]['text'])

    def actionParser(self, msg):
        """ parse raw trade action """
        action = {}
	msg = re.sub(' of ', ' ', msg)
        msg = re.sub(' on ', ' ', msg)
        msg = re.sub(' at ', ' ', msg)
        msg = re.sub(' - ', ' ', msg)
        msg = msg.split()
        for ii in range(len(msg)):    # location $ES
            if re.search('\$ES', msg[ii]) is not None:
                ESloc = ii
                break

        # trade initiation
        if re.search('LONG', msg[ESloc-1].upper()) is not None:
            action['type'] = 'INIT'
            action['side'] = 'LONG'
        elif re.search('SHORT', msg[ESloc-1].upper()) is not None:
            action['type'] = 'INIT'
            action['side'] = 'SHORT'
        elif re.search('LONG', msg[ESloc+1].upper()) is not None:
            action['type'] = 'INIT'
            action['side'] = 'LONG'
        elif re.search('SHORT', msg[ESloc+1].upper()) is not None:
            action['type'] = 'INIT'
            action['side'] = 'SHORT'

        if ('type' in action.keys()) and (action['type']=='INIT'):
            for ii in [1,2,3]:    # entry price
                try:
                    entry_price = re.findall(r'\d*\.\d+|d+', msg[ESloc+ii])
                    if entry_price is not None:
                        action['entry_price'] = float(entry_price)
                        break
                except IndexError;
                    break
            if 'entry_price' not in action.keys():
                action['entry_price'] = None

            for ii in np.r_[ESloc+1:len(msg)]:    # stop price
                if re.search('STOP', msg[ii].upper()) is not None:
                    STPloc = ii
                    break
            for ii in [-2,-1,1,2]:
                try:
                    stop_price = re.findall(r'\d*\.\d+|d+', msg[STPloc+ii])
                    if stop_price is not None:
                        if float(stop_price) < self.max_stop:
                            action['stop_price'] = float(stop_price)
                            break
                except IndexError:
                    action['stop_price'] = self.default_stop
                    break
        return action
       

if __name__ =='__main__':
    socket = twSocket()
    msg = socket.listener()
