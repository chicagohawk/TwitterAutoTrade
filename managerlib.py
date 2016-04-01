from twlib import *
from iblib import *

"""
    To guarantee stability, the position / order must be empty before launching the code!
"""

class localPosition:
    """ local copy of positions, shall track IB """
    def __init__(self):
        self.entry_price = None    # scalar, one price for all positions
        self.stop_price = None     # scalar
        self.size = 0              # + Long, - Short
        self.stop_id = []          # list of stop ids
        self.bid = None
        self.ask = None
        self.netliq = None         # scalar float
        self.maxSize = 0
        self.marginPerES = 3500.

    def displayPosition(self):
        print('-'*10, 'position update', '-'*10)
        print('Net Liq:', self.netliq)
        print('Pos Size:', self.size)
        print('Entry:', self.entry_price)
        print('Stop:', self.stop_price)
        # print('Stop Ids:', self.stop_id)
        print('Max Size:', self.maxSize)
        print('Bid:', self.bid)
        print('Ask:', self.ask)

class externalParam:
    """ external parameters like Darshan and CFTC, used to filter trade initiation """
    def __init__(self):
        self.cftc_bias = 0          # 1 buy, -1 sell, 0 neutral
        self.dd_bias = 0      
        self.dd_low_lim   = None    # DD's forward buy price (A5)
        self.dd_high_lim  = None    # DD's forward sell price (A5)

    def update(self, fn):
        fn = open(fn)
        txt = fn.readlines()
        if (txt[0].split()[0]=='CFTC') and (txt[1].split()[0]=='DD') and \
           (txt[2].split()[0]=='BUY') and (txt[3].split()[0]=='SELL'):
            self.cftc_bias = float( txt[0].split()[1] )
            self.dd_bias = float( txt[1].split()[1] )
            self.dd_low_lim = float( txt[2].split()[1] )
            self.dd_high_lim = float( txt[3].split()[1] )
            if self.dd_low_lim >= self.dd_high_lim:
                pass
        fn.close()


class tradeManager:
    
    def __init__(self, ibsocket, param_fn):
        self.ibsock = ibsocket
        self.localPos = localPosition()
        self.ib_latency = .75

        cTuple = ('ES', 'FUT', 'GLOBEX', 'USD', '201603',)
        self.contract = self.ibsock.makeContract(cTuple)
        self.param = externalParam()
        self.param.update(param_fn)

    def syncLocalPortfolio(self):
        self.ibsock.cleanList()
        self.ibsock.tws.disconnect()
        time.sleep(self.ib_latency)
        self.ibsock.tws.connect()
        time.sleep(self.ib_latency)

        self.ibsock.reqTick(self.contract)    # request bid ask
        time.sleep(self.ib_latency)

        self.ibsock.reqAccount()              # request net liq and portfolio
        time.sleep(self.ib_latency*2)

        self.ibsock.reqOrderStatus()          # request open orders
        time.sleep(self.ib_latency) 

        try:
            self.localPos.netliq = self.ibsock.netliq[-1]
            self.localPos.maxSize = \
                int( np.floor( self.localPos.netliq / self.localPos.marginPerES ) )
            if len(self.ibsock.pSiz) > 0:
                self.localPos.size = self.ibsock.pSiz[-1]
            else:
                self.localPos.size = 0

            if len(self.ibsock.openAuxPrices) > 0:
                if self.localPos.size > 0:
                    self.localPos.stop_price = max(self.ibsock.openAuxPrices)
                elif self.localPos.size < 0:
                    self.localPos.stop_price = min(self.ibsock.openAuxPrices)
            elif self.localPos.size != 0:
                print('MG warning: unprotected position (without stop) detected!')
            if len(self.ibsock.openAuxPrices) > abs(self.localPos.size):
                print('MG warning: number of stop orders exceed position size!')
    
            # assume all open orders are stop orders
            self.localPos.stop_id = self.ibsock.openOrderIds
            if len(self.localPos.stop_id) != abs( self.localPos.size ):
                print('MG warning: stop_id length not match position size!')

            self.localPos.bid = self.ibsock.bids[-1]
            self.localPos.ask = self.ibsock.asks[-1]

            self.localPos.displayPosition()

        except IndexError:
            print('MG serious warning: IB declines to update. Still proceed, but \
                   stability not guaranteed!')

       
    def synthesize_action(self, action):
        """ synthesize and trade actual action from raw action """
        self.syncLocalPortfolio()
        if (action is None) or ('type' not in action.keys()):
            print('MG invalid action, do nothing.')
            return

        """ close position """
        if action['type'] == 'CLOSE':
            # check if previous sides match
            if action['side'] == 'BUY' and self.localPos.size < 0.:
                print('MG position side not match, do nothing.')
                return
            if action['side'] == 'SELL' and self.localPos.size > 0:
                print('MG position side not match, do nothing.')
                return
            if self.localPos.size == 0:
                print('MG no open position, no need to close. do nothing.')
                return
            true_action_size = \
                min( abs(self.localPos.size), \
                     max( int( np.ceil( action['percent']/100.*self.localPos.maxSize ) ), 1 ) )
            if abs(self.localPos.size)>self.localPos.maxSize:
                true_action_size += abs(self.localPos.size) - self.localPos.maxSize 

            self.ibsock.cancelOrder(self.localPos.stop_id[:true_action_size])
            time.sleep(self.ib_latency)
            self.localPos.stop_id = self.localPos.stop_id[true_action_size:]

            if self.localPos.size > 0:
                side = 'SELL' # if was long, closing should be short
            else:
                side = 'BUY'
                
            for ii in range(true_action_size):
                self.ibsock.placeMarket(self.contract, side)
                time.sleep(self.ib_latency)

            if self.localPos.size > 0:
                self.localPos.size -= true_action_size
            elif self.localPos.size < 0:
                self.localPos.size += true_action_size

            self.localPos.displayPosition()
            return

        """ initialize position """
        if action['type'] == 'INIT':
            # if reverse position exist, close it first
            if action['side'] == 'BUY' and self.localPos.size < 0.:
                self.ibsock.cancelOrder(self.localPos.stop_id)
                time.sleep(self.ib_latency)
                self.localPos.stop_id = []
                for ii in range(abs(self.localPos.size)):
                    self.ibsock.placeMarket(self.contract, 'BUY')
                    time.sleep(self.ib_latency)
                self.localPos.size = 0

            if action['side'] == 'SELL' and self.localPos.size > 0.:
                self.ibsock.cancelOrder(self.localPos.stop_id)
                time.sleep(self.ib_latency)
                self.localPos.stop_id = []
                for ii in range(abs(self.localPos.size)):
                    self.ibsock.placeMarket(self.contract, 'SELL')
                    time.sleep(self.ib_latency)
                self.localPos.size = 0

            # safe guard initiation by external parameters
            bias = self.param.cftc_bias + self.param.dd_bias
            if (action['side'] == 'BUY') and (bias >= 0):
                if self.localPos.ask < self.param.dd_low_lim:
                    pass
                else:
                    print('MG buy initiation filtered, A5 not satisfied')
                    return
            elif (action['side'] == 'SELL') and (bias <= 0):
                if self.localPos.bid > self.param.dd_high_lim:
                    pass
                else:
                    print('MG sell initiation filtered, A5 not satisfied')
                    return
            else:
                print('MG trade initiation filtered, bias not satisfied')
                return

            # calculate true stop price
            if ('entry_price' in action.keys()) and ('stop_price' in action.keys()):
                pass
            else:
                print('MG entry / stop price key absent! do nothing.')
                return

            if action['entry_price'] is None:    # in case twitter does not specify entry price
                if action['side'] == 'BUY':
                    action['entry_price'] = self.localPos.ask
                elif action['side'] == 'SELL':
                    action['entry_price'] = self.localPos.bid

            if action['side'] == 'BUY':
                true_stop_price = action['entry_price'] - action['stop_price']
                if true_stop_price >= self.localPos.bid - .5:
                    print('MG twitter stop >= IB bid -.5! do nothing.')
                    return
            elif action['side'] == 'SELL':
                true_stop_price = action['entry_price'] + action['stop_price']
                if true_stop_price <= self.localPos.ask + .5:
                    print('MG twitter stop <= IB ask + .5! do nothing.')
                    return
            else:
                print('MG action side absent! do nothing.')
                return

            # add position to full maxSize
            true_action_size = self.localPos.maxSize - abs(self.localPos.size)
            if true_action_size <= 0:
                print('MG position size already maxed! no more initiation, do nothing.')
                return

            # safeguard entry_price / bid-ask not wide
            midprice = (self.localPos.bid + self.localPos.ask) / 2.
            if abs(action['entry_price'] - midprice) > 3.:
                print('MG twitter entry_price / bid-ask too wide! do nothing.')
                return

            for ii in range(true_action_size):
                Ids = self.ibsock.placeMKTEntryStop(self.contract, true_stop_price, action['side'])
                time.sleep(self.ib_latency)
                self.localPos.stop_id.append(Ids[-1])
            self.localPos.entry_price = action['entry_price']
            self.localPos.stop_price = true_stop_price
            if action['side'] == 'BUY':
                self.localPos.size = self.localPos.maxSize
            elif action['side'] == 'SELL':
                self.localPos.size = - self.localPos.maxSize
            
            self.localPos.displayPosition()
           
            return

        """ move stop """
        if action['type'] == 'FLAT_STP':
            if self.localPos.entry_price is None:
                print('MG entry_price absent! possibly caused by existing positions \
                       before code lauching. do nothing.')
                return
            self.ibsock.cancelOrder(self.localPos.stop_id)
            time.sleep(self.ib_latency)
            del self.localPos.stop_id[:]
            
            if self.localPos.size > 0:      # was longing, use sell stop
                for ii in range(abs(self.localPos.size)):
                    Ids = self.ibsock.placeStop(self.contract, self.localPos.entry_price, 'SELL')
                    time.sleep(self.ib_latency)
                    self.localPos.stop_id.append(Ids[-1])
                self.localPos.stop_price = self.localPos.entry_price

            elif self.localPos.size < 0:    # was shorting, use buy stop
                for ii in range(abs(self.localPos.size)):
                    Ids = self.ibsock.placeStop(self.contract, self.localPos.entry_price, 'BUY')
                    time.sleep(self.ib_latency)
                    self.localPos.stop_id.append(Ids[-1])
                self.localPos.stop_price = self.localPos.entry_price

            else:                           # had no position, do nothing
                print('MG no existing position to flat stop. do nothing.')

            self.localPos.displayPosition()
            return

        else:
            print('MG invalid action type! do nothing.')
            


