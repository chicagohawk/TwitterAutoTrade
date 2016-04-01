import numpy as np
import time
from ib.opt import ibConnection, message, messagetools
from ib.ext.Contract import Contract
from ib.ext.Order import Order
from ib.ext.ContractDetails import ContractDetails
from pdb import set_trace

class ibSocket:
 
    def __init__(self):
        self.tws = ibConnection(port=4001, clientId=999)
        self.tws.register(self.bidaskHandler, message.tickPrice)
        # ib poses a ~1min/req rate limit on updateAccountValue and orderStatus
        self.tws.register(self.accountHandler, message.updateAccountValue)
        self.tws.register(self.portfolioHandler, message.updatePortfolio)
        self.tws.register(self.orderStatusHandler, message.orderStatus)
        self.tws.register(self.openOrderHandler, message.openOrder)
        self.tws.register(self.validIdHandler, message.nextValidId)
        self.tws.register(self.serverTimeHandler, message.currentTime)
        self.tws.connect()

        self.netliq = []
        self.pSym = []
        self.pSiz = []
        self.pVal = []
        self.bids = []
        self.asks = []

        self.openOrderIds  = []
        self.openParentIds = []
        self.openAuxPrices = []    # stop prices

        self.reqId = 0
        self.orderId = []

        self.server_time = []    # used to ping IB periodically in case of lost connection
    
    # ------------------------ callback handlers --------------------------
    def bidaskHandler(self, msg):
        if msg.field==1: #9:
            self.bids.append(msg.price)
        elif msg.field==2: #14:
            self.asks.append(msg.price)
    
    def accountHandler(self, msg):
        if msg.key=='NetLiquidation':
            self.netliq.append(float(msg.value))
    
    def portfolioHandler(self, msg):
        self.pSym.append(msg.contract.m_symbol)
        self.pSiz.append(msg.position)
        self.pVal.append(msg.marketValue)

    def orderStatusHandler(self, msg):
        """ Callback whenever the status of an order changes. Returns all active orders. 
            Delete openOrderIds, openParentIds everytime before modifying orders! """
        if ( msg.status in ['Submitted','Inactive','PendingSubmit','PreSubmitted'] ) and \
           ( not msg.filled ):
            self.openOrderIds.append(msg.orderId)
            self.openParentIds.append(msg.parentId)

    def openOrderHandler(self, msg):
        """ use self.cleanList() before updating! """
        if msg.order.m_auxPrice != 0.:
            self.openAuxPrices.append(msg.order.m_auxPrice)

    def validIdHandler(self, msg):
        self.orderId.append( msg.orderId )

    def serverTimeHandler(self, msg):
        self.server_time.append(msg.time)

    # -------------------------------------------------------------------

    def makeContract(self, contractTuple):
        newContract = Contract()
        newContract.m_symbol = contractTuple[0]
        newContract.m_secType = contractTuple[1]
        newContract.m_exchange = contractTuple[2]
        newContract.m_currency = contractTuple[3]
        newContract.m_expiry = contractTuple[4]
        return newContract
    
    def makeOrder(self, action, orderId, tif, orderType, price, transmit, parentId):
        newOrder = Order()
        newOrder.m_orderId = orderId
        newOrder.m_transmit = transmit
        newOrder.m_lmtPrice = price
        newOrder.m_tif = tif
        newOrder.m_action = action
        newOrder.m_orderType = orderType
        if parentId is not None:
            newOrder.m_parentId = parentId

        newOrder.m_hidden = False
        newOrder.m_outsideRth = True
        newOrder.m_clientId = 999
        newOrder.m_permid = 0
        if orderType == 'LMT':
            newOrder.m_auxPrice = 0
        elif orderType == 'STP' or orderType == 'MIT':
            newOrder.m_auxPrice = price
        newOrder.m_totalQuantity = 1
        
        return newOrder
    

    def reqOrderStatus(self):
        del self.openOrderIds[:], self.openParentIds[:]
        self.tws.reqAllOpenOrders()
        self.reqId += 1

    def reqAccount(self):
        self.tws.reqAccountUpdates(True, '')
        self.reqId += 1

    def reqTick(self, contract):
        self.tws.reqMktData(self.reqId, contract, '', False)
        self.reqId += 1

    def cleanList(self):
        self.netliq = []
        self.pSym = [] 
        self.pSiz = []
        self.pVal = []
        self.bids = []
        self.asks = []
        self.openOrderIds = []
        self.openParentIds = []
        self.openAuxPrices = []
        self.orderId = []

    def placeBracket(self, contract, entry, target, stop, entryside):
        """ bracket order with limit order entry (RTH), 
            market-if-touched target (outside RTH), and
            stop exit (outside RTH)                         
        """
        del self.openOrderIds[:], self.openParentIds[:]
        if entryside == 'BUY':
            exitside = 'SELL'
            if not (target>entry and entry>stop):
                print('IB invalid bracket, order rejected')
        else:
            exitside = 'BUY'
            if not (target<entry and entry<stop):
                print('IB invalid bracket, order rejected')
        if len(self.orderId) < 1:
            print('IB orderId not available, possibly caused by latency, use sleep')
            exit(1)
        orderEntry = \
            self.makeOrder(entryside, self.orderId[-1], 'GTC', 'LMT', entry, False, None)
        orderTarget = \
            self.makeOrder(exitside, self.orderId[-1]+1, 'GTC', 'MIT', target, False, self.orderId[-1])
        orderStop = \
            self.makeOrder(exitside, self.orderId[-1]+2, 'GTC', 'STP', stop, True, self.orderId[-1])
        self.tws.placeOrder(self.orderId[-1], contract, orderEntry)
        self.tws.placeOrder(self.orderId[-1]+1, contract, orderTarget)
        self.tws.placeOrder(self.orderId[-1]+2, contract, orderStop)
        self.orderId[-1] += 3
        return [ self.orderId[-1]-3, self.orderId[-1]-2, self.orderId[-1]-1 ]

    def placeMarket(self, contract, entryside):
        del self.openOrderIds[:], self.openParentIds[:]
        orderEntry = self.makeOrder(entryside, self.orderId[-1], 'DAY', 'MKT', 0, True, None)
        self.tws.placeOrder(self.orderId[-1], contract, orderEntry)
        self.orderId[-1] += 1
        return [ self.orderId[-1]-1 ]

    def placeStop(self, contract, stop, side):
        del self.openOrderIds[:], self.openParentIds[:]
        if len(self.orderId) < 1:
            print('IB orderId not available, possibly caused by latency, use sleep')
            exit(1)
        orderStop = \
            self.makeOrder(side, self.orderId[-1], 'GTC', 'STP', stop, True, None)
        self.tws.placeOrder(self.orderId[-1], contract, orderStop)
        self.orderId[-1] += 1
        return [ self.orderId[-1]-1 ]


    def placeMITEntryStop(self, contract, entry, stop, entryside):
        del self.openOrderIds[:], self.openParentIds[:]
        """ MIT entry, hard stop """
        if entryside == 'BUY':
            exitside = 'SELL'
            if not entry>stop:
                print('IB invalid entry stop, order rejected')
        else:
            exitside = 'BUY'
            if not entry<stop:
                print('IB invalid entry stop, order rejected')
        if len(self.orderId) < 1:
            print('IB orderId not available, possibly caused by latency, use sleep')
            exit(1)
        orderEntry = \
            self.makeOrder(entryside, self.orderId[-1], 'DAY', 'MIT', entry, False, None)
        orderStop = \
            self.makeOrder(exitside, self.orderId[-1]+1, 'DAY', 'STP', stop, True, self.orderId[-1])
        self.tws.placeOrder(self.orderId[-1], contract, orderEntry)
        self.tws.placeOrder(self.orderId[-1]+1, contract, orderStop)
        self.orderId[-1] += 2
        return [ self.orderId[-1]-2, self.orderId[-1]-1 ]

    def placeMKTEntryStop(self, contract, stop, entryside):
        del self.openOrderIds[:], self.openParentIds[:]
        """ MIT entry, hard stop """
        if entryside == 'BUY':
            exitside = 'SELL'
        else:
            exitside = 'BUY'
        if len(self.orderId) < 1:
            print('IB orderId not available, possibly caused by latency, use sleep')
            exit(1)
        orderEntry = \
            self.makeOrder(entryside, self.orderId[-1], 'GTC', 'MKT', 0., False, None)
        orderStop = \
            self.makeOrder(exitside, self.orderId[-1]+1, 'GTC', 'STP', stop, True, self.orderId[-1])
        self.tws.placeOrder(self.orderId[-1], contract, orderEntry)
        self.tws.placeOrder(self.orderId[-1]+1, contract, orderStop)
        self.orderId[-1] += 2
        return [ self.orderId[-1]-2, self.orderId[-1]-1 ]

    def cancelOrder(self, orderId_list):
        for Id in orderId_list:
            self.tws.cancelOrder(Id)
            time.sleep(.75)  



if __name__ == '__main__' :
    """ warning: remember to sleep after EVERY request """
    socket = ibSocket()
    time.sleep(.5)    # wait for nextValidId request
    #socket.tws.reqCurrentTime()
    for i in range(10):
        socket.reqAccount()
        time.sleep(1.)
        print socket.netliq
    
    
    """
    cTuple = ('ES', 'FUT', 'GLOBEX', 'USD', '201603',)
    contract = socket.makeContract(cTuple)
    socket.reqTick(contract)
    time.sleep(.5)

    Id1 = socket.placeMKTEntryStop(contract, 2001, 'BUY')
    time.sleep(.5)

    socket.cancelOrder([Id[0]])
    time.sleep(.5)

    Id2 = socket.placeMKTEntryStop(contract, 2111, 'SELL')
    time.sleep(.5)

    socket.cleanList()
    socket.reqAccount()
    socket.reqOrderStatus()
    time.sleep(.5)
    #socket.tws.disconnect()
    """

