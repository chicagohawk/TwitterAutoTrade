"""
Idea: 1. run tw_listener <-- pipe --> managerlib/iblib, redirect stdout of tw_listener
         to pipe. Run two codes separately.
      2. It's time critical to init/close position, but not time critical to move/flat/widen
         stop. Treat them differently.
         while timer:
             synchronize IB every 5 min
             tw_listen
         when trade comes to tw_listen:
             trade using localPos first, get posterior target position
             wait 2 sec
             then synchronize IB
             if synchronized Pos != posterior target Pos:
                 make trade correction
             otherwise:
                 pass
         when move stop comes to tw_listen:
             synchronize IB
             move stop
             synchronize IB, make sure stop placed correctly and position correct
             otherwise: make trade correction
"""

#Import the necessary methods from tweepy library
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream

#Variables that contains the user credentials to access Twitter API 
access_token = "2776510801-rbNCNtaWsLL4wUfadYMozdXZ5kfZntor0k7smpz"
access_token_secret = "l6T3CQZEHPUzqwe6OkKcQOJ2jRAi88BEGuF01hDZvPaao"
consumer_key = "lbXi5nIK19eQy608cKqQ0BlXt"
consumer_secret = "xk5UN9VxS2IKVNF3nFFeXftIvO3ZUvZHq3aN5GbrLgkmJE3YME"


#This is a basic listener that just prints received tweets to stdout.
class StdOutListener(StreamListener):

    def on_data(self, data):
        print data
        return True

    def on_error(self, status):
        print status


if __name__ == '__main__':

    #This handles Twitter authetification and the connection to Twitter Streaming API
    l = StdOutListener()
    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    stream = Stream(auth, l)

    #This line filter Twitter Streams to capture data by the keywords: 'python', 'javascript', 'ruby'
    stream.userstream('voila_voici')
    aa = stream.filter(track=['TRADE'])
