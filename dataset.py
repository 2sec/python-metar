# coding=utf-8

import csv
import os
from datetime import datetime 
from datetime import timedelta
from datetime import timezone
import time

import Log
import utils
import io


last_modified_dic = {}


def read_if_changed(filename, new_last_modified):
    last_modified = last_modified_dic.get(filename, '')

    if last_modified == new_last_modified:
        return None

    Log.Write('reload %s' % filename)
    content = utils.cloud_download_text(filename)
    last_modified_dic[filename] = new_last_modified

    return content



def download_aviationweather_csv(output_list, filename, only_read_existing = False):
    base_url = 'https://www.aviationweather.gov/adds/dataserver_current/current/'

    url = base_url + filename

    new_last_modified = utils.tmp_read(filename)

    modified = False

    if only_read_existing:
        content = read_if_changed(filename, new_last_modified)

        if content:
            output_list = content.split('\n')
            if output_list[-1] == '': output_list.pop()
            modified = True
            
        return modified, output_list

    
    modified, response, new_last_modified = utils.http_download_if_newer(url, new_last_modified)
    if modified:
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

        #extract raw_text
        rows = csv.reader(io.StringIO(content))

        #skip header row
        next(rows)

        output_list = []

        for row in rows:
            output_list.append(row[0])

        output_list.sort()
        
        utils.cloud_upload_text(filename, '\n'.join(output_list))
        utils.tmp_write(filename, new_last_modified)

    return modified, output_list




def download_ourairports_csv(output_list, filename, only_read_existing = False):
    base_url = 'https://davidmegginson.github.io/ourairports-data/'

    url = base_url + filename

    new_last_modified = utils.tmp_read(filename)

    modified = False

    if not only_read_existing:
        modified, response, new_last_modified = utils.http_download_if_newer(url, new_last_modified)
        if modified:
            content = response.content.decode('utf-8')
            utils.cloud_upload_text(filename, content)
            utils.tmp_write(filename, new_last_modified)


    content = read_if_changed(filename, new_last_modified)
    if content:
        rows = csv.DictReader(io.StringIO(content))
        output_list = list(rows)
        modified = True

    return modified, output_list



class Cache(object):
    def __init__(self, cache):
        self.airports = []
        self.runways = []
        self.metars = []
        self.tafs = []
        self.airport_idents = []
        self.airport_names = []

        if cache:
            self.airports = cache.airports
            self.runways = cache.runways
            self.metars = cache.metars
            self.tafs = cache.tafs
            self.airport_idents = cache.airport_idents
            self.airport_names = cache.airport_names


    def download(self, only_read_existing = False):
        any_modified = False

        modified, self.airports = download_ourairports_csv(self.airports, 'airports.csv', only_read_existing = only_read_existing)
        any_modified |= modified

        #modified, self.runways, modified = download_ourairports_csv(self.runways, 'runways.csv', only_read_existing = only_read_existing)
        #any_modified |= modified

        modified, self.metars = download_aviationweather_csv(self.metars, 'metars.cache.csv', only_read_existing = only_read_existing)
        any_modified |= modified

        modified, self.tafs = download_aviationweather_csv(self.tafs, 'tafs.cache.csv', only_read_existing = only_read_existing)
        any_modified |= modified

        return any_modified

    def update(self):

        if not self.download(True):
            return False

        Log.Write('updating')

        tafs = self.tafs
        metars = self.metars

        #TODO AMD COR CNL
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

        return True


cache = None

def delayed_start():
    time.sleep(30)
    utils.StartThread(update, 'update', restartOnException=True)

#update in memory datasets every 30s in the background
def update(firstTime=False):
    global cache

    new_cache = Cache(cache)
    if new_cache.update():
        cache = new_cache

    if not firstTime:
        time.sleep(30)



#initialize dataset
#make sure update() runs once immediately, then run it every 30s after that
update(True)
utils.StartThread(delayed_start, 'delayed_start', restart=False, restartOnException=True)




if __name__ == '__main__':

    #config = CamConfig()
    #config.Run()

    while True:
        cache.download()
        time.sleep(60)





