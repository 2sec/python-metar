# coding=utf-8


import threading
import random
import os
import io
import atexit
import re
import requests


import Log
from google.cloud import storage
import boto3

#various helper functions are put here, and also StartThread() and SendMail(), see below

# random init for all modules
random_state = 1217
os.environ['PYTHONHASHSEED'] = '0'
random.seed(random_state)
#np.random.seed(random_state)



GAE_PROJECTID = os.getenv('GOOGLE_CLOUD_PROJECT', '')
GAE_BUCKET = GAE_PROJECTID + '.appspot.com'
GAE_ENV = os.getenv('GAE_ENV', '')

USE_GAE = GAE_PROJECTID != ''
BUCKET = GAE_BUCKET

USE_AWS = False

AWS_PROJECTID = os.getenv('AWS_PROJECT', '')
AWS_BUCKET = os.getenv('AWS_BUCKET', '')
AWS_ENV = os.getenv('AWS_ENV', '')

if AWS_PROJECTID != '':
    USE_AWS = True
    USE_GAE = False
    BUCKET = AWS_BUCKET


Log.Write('GOOGLE_CLOUD_PROJECT = ' + GAE_PROJECTID)
Log.Write('GAE_ENV = ' + GAE_ENV)
Log.Write('AWS_PROJECT = ' + AWS_PROJECTID)
Log.Write('AWS_BUCKET = ' + AWS_BUCKET)
Log.Write('AWS_ENV = ' + AWS_ENV)



is_production = GAE_ENV != '' or AWS_ENV != ''
local_download = not is_production



# upload to file in Google or AWS cloud
def cloud_upload_bytes(destination_filename, bytes, content_type = 'application/octet-stream'):
    if local_download:
        open('download/' + destination_filename, 'wb').write(bytes)
        return
    
    Log.Write('cloud upload to %s/%s' % (BUCKET, destination_filename))

    if USE_AWS:
        storage_client = boto3.client('s3')
        bytes = io.BytesIO(bytes)
        return storage_client.upload_fileobj(bytes, BUCKET, destination_filename)

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET)
    blob = bucket.blob(destination_filename)
    return blob.upload_from_string(bytes, content_type = content_type)

def cloud_upload_text(destination_filename, text):
    return cloud_upload_bytes(destination_filename, text.encode('utf-8'), 'text/plain')


# download from file in Google or AWS cloud
def cloud_download_bytes(source_filename):
    if local_download:
        return open('download/' + source_filename, 'rb').read()

    Log.Write('cloud download from %s/%s' % (BUCKET, source_filename))

    if USE_AWS:
        storage_client = boto3.client('s3')
        bytes = io.BytesIO()
        storage_client.download_fileobj (BUCKET, source_filename, bytes)
        return bytes.getvalue()

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET)
    blob = bucket.blob(source_filename)
    if not blob.exists(): return None
    bytes = blob.download_as_bytes()
    return bytes

def cloud_download_text(source_filename):
    file = cloud_download_bytes(source_filename);
    if not file: return None
    return file.decode('utf-8')



def http_get_last_modified(url):
    Log.Write('head %s' % url)
    response = requests.head(url)
    last_modified = response.headers['Last-Modified']
    Log.Write('Last-Modified %s %s' % (last_modified, url))
    return last_modified


def http_download_if_newer(url, last_modified, add_random_value = True):
    url += '?r=' + str(random.getrandbits(64))
    new_last_modified = http_get_last_modified(url)
    if new_last_modified == last_modified:
        return False, None, last_modified

    Log.Write('http get %s' % url)
    response = requests.get(url)
    Log.Write('response status code = ' + str(response.status_code))
    if response.status_code != 200:
        raise Exception("Invalid status code")

    return True, response, new_last_modified



# files in /tmp are stored in memory in GAE
def tmp_read(filename):
    filename = '/tmp/' + filename
    if not os.path.isfile(filename): return ''
    return open(filename, 'r').read()

def tmp_write(filename, str):
    filename = '/tmp/' + filename
    open(filename, 'w').write(str)



import socket
import time

import collections


from datetime import datetime 

import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart



WeekDay_Short = [ 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat' ]
Month_Short = [ 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul',  'Aug', 'Sep', 'Oct', 'Nov', 'Dec' ]

def HttpDateTime(dateTime = None):
    if dateTime is None: dateTime = datetime.utcnow()
    return '%s, %02u %s %04u %02u:%02u:%02u GMT' % (WeekDay_Short[dateTime.weekday()], dateTime.day, Month_Short[dateTime.month - 1], dateTime.year, dateTime.hour, dateTime.minute, dateTime.second)
 
def ShortDateTime(dateTime = None):
    if dateTime is None: dateTime = datetime.utcnow()
    return '%04u/%02u/%02u %02u:%02u:%02u' % (dateTime.year, dateTime.month, dateTime.day, dateTime.hour, dateTime.minute, dateTime.second) 

def GetHostName():
    return socket.gethostname()

'''
def getIPAddress():
    s = socket.socket()
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]    
    s.close()
    return ip

IPAddress = getIPAddress()
'''

#define MSG_MORE	0x8000	/* Sender will send more */
SOCKET_MSG_MORE = 0x8000

def socket_send(connection, buffer, more = False):

    tosend = len(buffer)

    while tosend > 0:
        sent = connection.send(buffer, SOCKET_MSG_MORE if more else 0)
        buffer = buffer[sent:]
        tosend -= sent



def socket_recv(connection, size = 1024):

    buffer = connection.recv(size)
    if len(buffer) == 0:
        raise(IOError('recv'))

    return buffer


def socket_create(reuse = False, nodelay = True):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if reuse:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if nodelay:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


# difference of two angles in degrees
def angle_diff(angle1, angle2):
    angle = angle1 - angle2
    return (angle + 180) % 360 - 180




class StopWatch(object):

    def __init__(self):
        self.now = datetime.utcnow()
        self.dict = {}
    
    def Elapsed(self, duration, id = 0):
        if id == 0: id = duration
        prev = self.dict.get(id, self.now)

        now = datetime.utcnow()
        diff = int((now - prev).total_seconds())

        if diff > 0 and diff % duration == 0:
            self.dict[id] = now
            return True

        return False
        



def Exit(code = -1):
     os._exit(code)


def StartThread(target, name = None, startDelay = 0, afterDelay = 0,  runImmediately = False, restart = True, restartOnException = False, exitOnException = True, *args):

    def thread(*args):
        while True:
            try:
                Log.Write('starting')
                target(*args)
                Log.Write('end')
                if not restart: return
                if afterDelay:
                    time.sleep(afterDelay)
            except:
                Log.Log_Exception()
                if not restartOnException: break
                Log.Write('pausing')
                time.sleep(5)

        # terminate all threads and exit process (a bit abruptly)
        if exitOnException:
            Exit()


    def startWithDelay():
        time.sleep(startDelay)
        thread(*args)


    if name is None: name = target.__name__

    if runImmediately:
        target(*args)

    fn = thread
    if startDelay: fn = startWithDelay

            
    t = threading.Thread(target=fn, name=name, args=args)
    t.daemon = True
    t.start()       
    return t
    




Mail = collections.namedtuple('Mail', 'config, to, subject, text, image')
mailEvent = threading.Event()
mail = None

#see the namedtuple above for the args
def SendMail(*args):
    global mail
    mail = Mail(*args)
    
    mailEvent.set()


# this is to make sure that the recipient is not flooded (note: mails are currently all sent to the same recipient, otherwise we would use a queue)
# todo: merge multiple emails sent to the same recipient within a given timespan?
def SendMailAsync():
    while True:
        mailEvent.wait()
        mailEvent.clear()

        m = mail

        config = m.config

        msg = MIMEMultipart()
        msg['From'] = m.config.smtp_username
        msg['To'] = m.to
        msg['Subject'] = m.subject

        text = MIMEText(m.text)
        msg.attach(text)

        Log.Write('SendMailAsync: %s' % msg.as_string())

        if m.image is not None:
            image = MIMEImage(m.image, 'jpeg')
            msg.attach(image)
            
        if config.sendmail:
            try:
                smtp = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port)
                smtp.login(config.smtp_username, config.smtp_password)
                smtp.sendmail(config.smtp_username, m.to, msg.as_string())
                smtp.quit()
            except:
                Log.Log_Exception()


        time.sleep(5)


StartThread(SendMailAsync, 'sendmail')





