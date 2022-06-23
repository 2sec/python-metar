import threading
import ConfigParser
import time

import Log

# Config class. Values are stored as text in an .ini file in the current directory
# the values can be changed while the program is running as the values are read in the background


class Config(object):
    def __init__(self):
        self.read_event = threading.Event()

    def read(self):
        self.config = ConfigParser.ConfigParser()
        self.config.read('config.ini')

        self.init()
        self.read_event.set()


    def init(self):
        pass


    def getvalue(self, name, default_value):
        try:
            value = self.config.get('config', name)

            if type(default_value)==bool:
                value = value == 'True'
            elif type(default_value)==tuple:
                value = value.split(',')
                value = [type(default_value[0])(item) for item in value]
                value = tuple(value)
            elif type(default_value)==list:
                value = value.split(',')
                value = [type(default_value[0])(item) for item in value]

        except:
            #Log.Log_Exception()
            value = default_value


        value = type(default_value)(value)

        setattr(self, name, value)

        #Log.Write('%s=%s' % (name, str(value)))

        return value


    def thread(self):
        while True:
            self.read()
            time.sleep(5)


    def Run(self):
        t = threading.Thread(target=self.thread, args=())
        t.daemon = True
        t.start()       

        self.read_event.wait()
