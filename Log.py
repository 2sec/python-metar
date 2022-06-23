# coding=utf-8

import traceback
import datetime
from datetime import timedelta

import sys
import os

import threading

import platform


import sys


# module used to log information
# import Log, then call Log.Write(str)
# prints on stdout and also outputs to a log file 
# Call Log_Exception() to log exceptions with a stack trace

import __main__
name = 'main'
if hasattr(__main__, '__file__'):
    name = __main__.__file__
    _, name = os.path.split(name)


outputToLog = False


threading.current_thread().name = 'main'



fd = None
current_date = None

L = threading.Lock()

def Write(s, print_to_stdout = True):
    now = datetime.datetime.utcnow()
    date = '%04d-%02d-%02d' % (now.year, now.month, now.day)
    time = '%02d:%02d:%02d.%03d' % (now.hour, now.minute, now.second, now.microsecond / 1000)

    s = date + ' ' + time + ' ' + str(threading.current_thread().getName()) + ': ' + str(s)

    if print_to_stdout:
        print(s)

    global current_date
    global fd


    if outputToLog:
        try:
            L.acquire()

            if current_date != date:
                current_date = date
                if fd is not None: fd.close()
                linkName = name + '.log' 
                fullName = date + '.' + linkName
                fd = open(fullName, 'a+')
                if os.path.exists(linkName): os.remove(linkName)
                os.symlink(fullName, linkName)
                

            fd.write(s + '\n')
            fd.flush()

        finally:
            L.release()

def Log_Exception():
    Write(traceback.format_exc())

def excepthook(type, value, tb):
    l = traceback.format_exception(type, value, tb)
    s = ''
    for i in l: s += i
    Write(s)


sys.excepthook = excepthook


python_major_ver = sys.version_info.major
python_minor_ver = sys.version_info.minor
python_micro_ver = sys.version_info.micro

os_info = platform.platform()
#os_info = '%s/%s' % (platform.system(), platform.release())


Write('Using %s' % os_info)
Write('Using Python %d.%d.%d' % (python_major_ver, python_minor_ver, python_micro_ver))
Write('Working directory %s ' % (os.getcwd()))


Write('MAIN = ' + name)



