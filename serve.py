from twlib import *

def send_client_SMS(code):
    alert_server = smtplib.SMTP('smtp.gmail.com',587)
    alert_server.starttls()
    alert_server.login('voilasept@gmail.com', 'Al#4Vic!hAnMa')
    clients = ['3142813654@tmomail.net']
    for ii in clients:
        alert_server.sendmail('voilasept@gmail.com', ii, code)
    alert_server.quit()

