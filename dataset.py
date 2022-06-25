# coding=utf-8

import csv
import os
from datetime import datetime 
from datetime import timedelta
from datetime import timezone
import requests
import time

import Log
import utils
import io




debug = False


def file_exist(filename):
    metadata = utils.bucket_metadata(filename)
    return metadata is not None
    #return os.path.isfile(filename)

def is_older_than(filename, minutes):
    #if not file_exist(filename): return True
    #modify_date = datetime.fromtimestamp(os.path.getmtime(filename))
    metadata = utils.bucket_metadata(filename)
    if metadata is None: return True 
    modify_date = metadata.updated
    modify_date = modify_date.replace(tzinfo=None)

    return modify_date + timedelta(minutes=minutes) < datetime.utcnow()



def download_aviationweather_csv(filename, only_read_existing = False, debug_header_size = 5):
    base_url = 'https://www.aviationweather.gov/adds/dataserver_current/current/'

    input_filename = filename + '.cache.csv'   #no need to request the gz version, the service returns it zipped anyway and the requests lib unzips it transparently
    url = base_url + input_filename
    output_filename = filename + '.csv'

    output_list = []


    modify_date = utils.bucket_getlastmodified('download/' + output_filename)
    is_older = modify_date + timedelta(minutes=10) < datetime.utcnow()

    if only_read_existing and not modify_date:
        return []


    if only_read_existing:
        text = utils.bucket_download_string('download/' + output_filename)
        output_list = text.split('\n')
        if output_list[-1] == '': output_list.pop()


    if not only_read_existing and is_older_than('download/' + input_filename, minutes=2.5): 
        Log.Write('downloading from %s' % url)
        response = requests.get(url)
        Log.Write('response status code = ' + str(response.status_code))
        if response.status_code != 200:
            raise Exception("Invalid status code")

        content = response.content.decode('utf-8')
        #default debug header:
        #No errors
        #No warnings
        #474 ms
        #data source=metars
        #4809 results

        n = -1
        for i in range(0,5):
            n = content.index('\n', n+1)
        debug_header = content[0:n]

        content = content[n+1:]

        Log.Write(debug_header)

        utils.bucket_upload_string('download/' + input_filename, content)
    
        #extract raw_text
        rows = csv.reader(io.StringIO(content))

        #skip header row
        next(rows)

        for row in rows:
            output_list.append(row[0])

        output_list.sort()
        
        utils.bucket_upload_string('download/' + output_filename, '\n'.join(output_list))


    return output_list



def download_ourairports_csv(filename, only_read_existing = False):
    base_url = 'https://davidmegginson.github.io/ourairports-data/'

    input_filename = filename + '.csv'    
    url = base_url + input_filename

    output_list = []


    if only_read_existing and not file_exist('download/' + input_filename):
        return []

    if not only_read_existing and is_older_than('download/' + input_filename, minutes=60): 
        Log.Write('downloading from %s' % url)
        response = requests.get(url)
        Log.Write('response status code = ' + str(response.status_code))
        if response.status_code != 200:
            raise Exception("Invalid status code")

        utils.bucket_upload_string('download/' + input_filename, response.content.decode('utf-8'))


    content = utils.bucket_download_string('download/' + input_filename)
    rows = csv.DictReader(io.StringIO(content))
    output_list = list(rows)

    return output_list



class Cache(object):
    def __init__(self):
        self.airports = []
        self.runways = []
        self.metars = []
        self.tafs = []
        self.airport_idents = []
        self.airport_names = []
        self.date = 0 # todo: do not reload dataset if not changed

    def download(self, only_read_existing = False):
        self.airports = download_ourairports_csv('airports', only_read_existing = only_read_existing)
        #self.runways = download_ourairports_csv('runways', only_read_existing = only_read_existing)
        self.metars = download_aviationweather_csv('metars', only_read_existing = only_read_existing)
        self.tafs = download_aviationweather_csv('tafs', only_read_existing = only_read_existing)

    def update(self):

        self.download(True)

        tafs = self.tafs
        metars = self.metars

        #inconsistency in the source - sometimes a TAF starts with the word TAF, sometimes not
        for i, taf in enumerate(tafs):
            if taf.startswith('TAF '): tafs[i] = taf[4:]
        tafs.sort()

        idents = []
        names = []

        # advance in all sorted lists at the same time, and find matching metars, tafs and runways
        metars_iter = iter(metars)
        metar = next(metars_iter, None)


        tafs_iter = iter(tafs)
        taf = next(tafs_iter, None)


        for airport in self.airports:
            ident = airport['ident'].upper()
            idents.append(ident)
            names.append(airport['name'])

            # find matching metar, taf or runways, if any
            airport['metar'] = None
            airport['taf'] = None


            while metar and ident > metar[0:4]: metar = next(metars_iter, None)
            if metar and ident == metar[0:4]: airport['metar'] = metar

            while taf and ident > taf[0:4]: taf = next(tafs_iter, None)
            if taf and ident == taf[0:4]: airport['taf'] = taf
        

        self.airport_idents = idents
        self.airport_names = names


cache = Cache()

#update in memory datasets every 30 seconds in the background


#todo bug: if download and update run at the same time (in the same process or not)
def update(firstTime = False, sleep = True):
    if sleep:
        time.sleep(30)

    new_cache = Cache()
    new_cache.update()
    global cache
    cache = new_cache

    if firstTime:
        utils.StartThread(update, 'update', restartOnException=True)


#initialize dataset
update(True, False)

   

# called every 2.5 minutes by GAE: /tasks/download
def download():
    Cache().download()






if __name__ == '__main__':

    #config = CamConfig()
    #config.Run()

    while True:
        download()
        time.sleep(1000)





