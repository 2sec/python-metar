# coding=utf-8

import csv
import os
from datetime import datetime 
from datetime import timedelta
from re import A
import requests
import time

import Log
import utils

import gc





def is_older_than(filename, minutes):
    if not os.path.isfile(filename):
        return True

    modify_date = datetime.fromtimestamp(os.path.getmtime(filename))
    
    return modify_date + timedelta(minutes=minutes) < datetime.now()



def download_aviationweather_csv(filename, debug_header_size = 5):
    base_url = 'https://www.aviationweather.gov/adds/dataserver_current/current/'

    input_filename = filename + '.cache.csv'   #no need to request the gz version, the service returns it zipped anyway and the requests lib unzips it transparently
    url = base_url + input_filename
    output_filename = filename + '.csv'

    output_list = []

    if is_older_than('download/' + input_filename, minutes=2.5): 
        Log.Write('downloading from %s' % url)
        response = requests.get(url)
        Log.Write('response status code = ' + str(response.status_code))
        if response.status_code != 200:
            raise Exception("Invalid status code")
        response = response.content.decode('utf-8')

        #default debug header:
        #No errors
        #No warnings
        #474 ms
        #data source=metars
        #4809 results

        n = -1
        for i in range(0,5):
            n = response.index('\n', n+1)
        debug_header = response[0:n]

        response = response[n+1:]

        Log.Write(debug_header)

        with open('download/' + input_filename, 'wb') as f:
            f.write(response.encode('utf-8'))

    # extract raw_text
    with open('download/' + input_filename, 'r', encoding='utf-8') as f, open('download/' + output_filename, 'w', newline='\n', encoding='utf-8') as f_out:
        rows = csv.reader(f)

        #skip header row
        next(rows)

        for row in rows:
            output_list.append(row[0])
            f_out.write('%s\n' % row[0])

    output_list.sort()
    return output_list



def download_ourairports_csv(filename):
    base_url = 'https://davidmegginson.github.io/ourairports-data/'

    input_filename = filename + '.csv'    
    url = base_url + input_filename

    output_list = []

    if is_older_than('download/' + input_filename, minutes=60): 
        Log.Write('downloading from %s' % url)
        response = requests.get(url)
        Log.Write('response status code = ' + str(response.status_code))
        if response.status_code != 200:
            raise Exception("Invalid status code")

        with open('download/' + input_filename, 'wb') as f:
            f.write(response.content)


    with open('download/' + input_filename, 'r', encoding='utf-8') as f:
        rows = csv.DictReader(f)

        output_list = list(rows)

    return output_list


airports = []
runways = []
airport_idents = []
airport_names = []


#download all datasets continously in the background
def download(sleep = True):
    global airports
    global runways
    global airport_idents
    global airport_names


    airports = download_ourairports_csv('airports')
    runways = download_ourairports_csv('runways')
    metars = download_aviationweather_csv('metars')
    tafs = download_aviationweather_csv('tafs')

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


    for airport in airports:
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
    

    airport_idents = idents
    airport_names = names
    
    gc.collect()


    time.sleep(60 * 5)



utils.StartThread(download, 'download', restartOnException=True)





if __name__ == '__main__':

    #config = CamConfig()
    #config.Run()

    while True: time.sleep(1000)



