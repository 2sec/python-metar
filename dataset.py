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


# this dict contains the last modification dates of all the files kept in memory
last_modified_dic = {}

# compare the date stored in /tmp/ (given as last_modified) vs the one in memory
# if different, the file must be reloaded
def read_if_changed(filename, new_last_modified):
    last_modified = last_modified_dic.get(filename, '')

    if last_modified and last_modified == new_last_modified:
        return None

    Log.Write('must reload %s' % filename)
    content = utils.cloud_download_text(filename)
    last_modified_dic[filename] = new_last_modified

    return content


# download the given file but only if it has changed
def download_aviationweather_csv(output_list, filename, only_read_existing = False):
    base_url = 'https://www.aviationweather.gov/adds/dataserver_current/current/'

    url = base_url + filename

    new_last_modified = utils.tmp_read(filename)

    modified = False

    if not only_read_existing:
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

            #upload the new file
            utils.cloud_upload_text(filename, content)

            #signal the file has changed
            utils.tmp_write(filename, new_last_modified)
            

    content = read_if_changed(filename, new_last_modified)
    if content:
        rows = csv.DictReader(io.StringIO(content), quoting=csv.QUOTE_NONE)
        output_list = list(rows)
        output_list.sort(key=lambda item: item['station_id'])
        modified = True


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
            #upload the new file
            utils.cloud_upload_text(filename, content)

            #signal the file has changed
            utils.tmp_write(filename, new_last_modified)


    content = read_if_changed(filename, new_last_modified)
    if content:
        rows = csv.DictReader(io.StringIO(content))
        output_list = list(rows)
        output_list.sort(key=lambda item: item['ident'])
        modified = True

    return modified, output_list



class Cache(object):
    def __init__(self, cache = None):
        self.airports = []
        self.runways = []
        self.metars = []
        self.tafs = []
        self.airports_dic = {}
        self.airport_idents = []

        if cache:
            self.airports = cache.airports
            self.runways = cache.runways
            self.metars = cache.metars
            self.tafs = cache.tafs
            self.airports_dic = cache.airports_dic
            self.airport_idents = cache.airport_idents


    # return true only if one of the files has changed
    def download(self, only_read_existing = False):
        any_modified = False

        modified, self.airports = download_ourairports_csv(self.airports, 'airports.csv', only_read_existing = only_read_existing)
        any_modified |= modified

        #modified, self.runways, modified = download_ourairports_csv(self.runways, 'runways.csv', only_read_existing = only_read_existing)
        #any_modified |= modified

        modified, self.metars = download_aviationweather_csv(self.metars, 'metars.cache.csv', only_read_existing = only_read_existing)
        any_modified |= modified
        if modified:
            metars = []
            for row in self.metars:
                row = { key: row[key] for key in ['raw_text', 'station_id', 'flight_category']}
                metars.append(row)
            self.metars = metars


        modified, self.tafs = download_aviationweather_csv(self.tafs, 'tafs.cache.csv', only_read_existing = only_read_existing)
        any_modified |= modified
        if modified:
            tafs = []
            for row in self.tafs:
                row = { key: row[key] for key in ['raw_text', 'station_id']}
                tafs.append(row)
            self.tafs = tafs

        return any_modified

    # update in memory structures if they have changed
    def update(self):
        #if nothing changed: do nothing
        if not self.download(True):
            return False

        Log.Write('updating')

        tafs = self.tafs
        metars = self.metars

        #TODO: AMD COR CNL

        #inconsistency in the source - sometimes a TAF starts with the word TAF, sometimes not
        for i, taf in enumerate(tafs):
            raw_text = taf['raw_text']
            if raw_text.startswith('TAF '): tafs[i]['raw_text'] = raw_text[4:]
        
        idents = []

        # advance in all sorted lists at the same time, and find matching metars, tafs and runways
        metars_iter = iter(metars)
        metar = next(metars_iter, None)

        tafs_iter = iter(tafs)
        taf = next(tafs_iter, None)

        airports_dic = {}

        for airport in self.airports:
            ident = airport['ident'].upper()
            idents.append(ident)
            airports_dic[ident] = airport

            # find matching metar, taf or runways, if any
            airport['metar'] = None
            airport['taf'] = None

            while metar and ident > metar['station_id']: metar = next(metars_iter, None)
            if metar and ident == metar['station_id']: airport['metar'] = metar

            while taf and ident > taf['station_id']: taf = next(tafs_iter, None)
            if taf and ident == taf['station_id']: airport['taf'] = taf
        

        self.airport_idents = idents
        self.airports_dic = airports_dic

        return True


cache = None

#update in memory datasets every 30s in the background
def update(firstTime=False):
    global cache

    new_cache = Cache(cache)
    if new_cache.update():
        cache = new_cache

    if not firstTime:
        time.sleep(30)

def delayed_start():
    time.sleep(30)
    utils.StartThread(update, 'update', restartOnException=True)


#initialize dataset
#make sure update() runs once immediately, then run it every 30s after that
update(True)
utils.StartThread(delayed_start, 'delayed_start', restart=False)




if __name__ == '__main__':

    #config = CamConfig()
    #config.Run()

    while True:
        Cache().download()
        time.sleep(60)





