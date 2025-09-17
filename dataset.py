# coding=utf-8

import csv
import time
import math

import Log
import utils
import io
import gzip

from datetime import datetime

import pandas as pd
from lxml import etree



# this dict contains the last modification dates of all the files kept in memory
last_modified_dic = {}

# compare the date stored in /tmp/ (given as last_modified) vs the one in memory
# if different, the file must be reloaded
def read_if_changed(filename, new_last_modified):
    last_modified = last_modified_dic.get(filename, '')

    if last_modified and last_modified == new_last_modified:
        return None

    Log.Write('must reload %s: %s != %s' % (filename, last_modified, new_last_modified))
    content = utils.cloud_download_text(filename)
    last_modified_dic[filename] = new_last_modified

    return content


# read the given csv filename and return a list of dictionaries.
# if the file has not changed, return the existing list
# if an existing list is not given, read the file unconditionnally
def read_csv_if_newer(filename,  output_list, fields, quoting):
    new_last_modified = None
    if output_list: new_last_modified = utils.tmp_read(filename)

    modified = False

    content = read_if_changed(filename, new_last_modified)
    if content:
        rows = csv.DictReader(io.StringIO(content), quoting = quoting)

        output_list = []
        for row in rows:

            # sometime rows are malformed
            skip = False
            for key in fields: 
                if key not in row: skip = True

            if skip:
                continue

            row = { key: row[key] for key in fields}
            output_list.append(row)


        sort_key = fields[0]
        for item in output_list:
            item[sort_key] = item[sort_key].upper()

        output_list.sort(key=lambda item: item[sort_key] )

        modified = True

    return modified, output_list




# download the given file from the source and updates it on our cloud
def download_aviationweather_csv(filename):
    # new 10/2023 (gz)
    base_url = 'https://aviationweather.gov/data/cache/'

    # new 9/2025 the CSV format  for the TAF is no longer available
    # so the XML format is used instead, then converted back to CSV
    filename = filename.replace(".csv", ".xml")
    
    url = base_url + filename


    new_last_modified = utils.tmp_read(filename)

    modified, response, new_last_modified = utils.http_download_if_newer(url + '.gz', new_last_modified)
    if modified:
        content = gzip.decompress(response.content)
        content = content.decode('utf-8')

        # new 9/2025 see above
        df = pd.read_xml(content, xpath = "/response/data/*")
        content = df.to_csv(index=False)
        filename = filename.replace(".xml", ".csv")
        
        # no longer used since 9/2025
        if False:
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

        #upload the new file
        utils.cloud_upload_text(filename, content)

        #signal the file has changed
        utils.tmp_write(filename, new_last_modified)

    return modified


def download_ourairports_csv(filename):
    base_url = 'https://davidmegginson.github.io/ourairports-data/'

    url = base_url + filename

    new_last_modified = utils.tmp_read(filename)

    modified, response, new_last_modified = utils.http_download_if_newer(url, new_last_modified)
    if modified:
        content = response.content.decode('utf-8')
        #upload the new file
        utils.cloud_upload_text(filename, content)

        #signal the file has changed
        utils.tmp_write(filename, new_last_modified)

    return modified




def download_metar_stations(filename):
    # new 10/2023
    url = 'https://www.weathergraphics.com/identifiers/master-location-identifier-database-202307_standard.csv'
    

    # TODO: test if the url has changed
    # or use this source https://www.aviationweather.gov/docs/metar/stations.txt 

    new_last_modified = utils.tmp_read(filename)

    modified, response, new_last_modified = utils.http_download_if_newer(url, new_last_modified)
    if modified:
        content = response.content.decode('iso-8859-1')
        #default  header:
        #Master Location Identifier Database (MLID) - Standard Version																			
        #Edition 2022.07 | July 2022 | Series E | Effective dates: FAA: 2022-06-16 | ICAO: 2022-06-16 (AIRAC 2206) | WMO: 2022-07-01																			
        #©2010-2022 Weather Graphics / www.weathergraphics.com / servicedesk@weathergraphics.com / All rights reserved																			
        #This database is not approved for navigational use.  Rows marked with x" in the status column are obsolete and for historical reference only.  For complete information on this data, refer to the documentation at: www.weathergraphics.com/identifiers																			
        #

        n = -1
        for i in range(0,5):
            n = content.index('\n', n+1)
        debug_header = content[0:n]

        content = content[n+1:]

        #upload the new file
        utils.cloud_upload_text(filename, content)

        #signal the file has changed
        utils.tmp_write(filename, new_last_modified)

    return modified




class Cache(object):
    def __init__(self, cache = None):
        self.airports = []
        self.runways = []
        self.metars = []
        self.tafs = []
        self.airports_ident = {}
        self.airports_index = {}
        self.last_download = None

        if cache:
            self.airports = cache.airports
            self.runways = cache.runways
            self.metars = cache.metars
            self.tafs = cache.tafs
            self.airports_ident = cache.airports_ident
            self.airports_index = cache.airports_index
            self.last_download = cache.last_download

    # download all files from the source, if they have changed
    def download(self):

        Log.Write('testing')

        modified = False

        # no need to download those files more than once a day
        now = datetime.utcnow()
        if(self.last_download is None or (now - self.last_download).days >= 1):
            self.last_download = now

            modified |= download_metar_stations('stations.csv')
            modified |= download_ourairports_csv('airports.csv')

            #merge airports and stations
            if modified:
                Log.Write('merging')

                modified, airports = read_csv_if_newer('airports.csv', None, ['ident', 'name', 'elevation_ft'], csv.QUOTE_MINIMAL)
                modified, stations = read_csv_if_newer('stations.csv', None, ['icao', 'station_name', 'elev'], csv.QUOTE_MINIMAL)

                airports_set = { airport['ident'] for airport in airports }

                for station in stations:
                    ident = station['icao']
                    if ident == '': continue

                    if ident not in airports_set:
                        airports.append({'ident': station['icao'], 'name': station['station_name'], 'elevation_ft': station['elev']})

                airports.sort(key=lambda item: item['ident'] )


                content = io.StringIO()
                writer = csv.DictWriter(content, airports[0].keys(), quoting = csv.QUOTE_MINIMAL)
                writer.writeheader()
                writer.writerows(airports)
                content.seek(0)
                content = content.read()

                filename = 'airports_and_stations.csv'
                utils.cloud_upload_text(filename, content)
                #signal the file has changed
                utils.tmp_write(filename, str(now))


            modified |= download_ourairports_csv('runways.csv')


        modified |= download_aviationweather_csv('metars.cache.csv')
        modified |= download_aviationweather_csv('tafs.cache.csv')

        Log.Write('done')
        return modified


    def find_airports(self, text):
        indexes = []
        first_run  = True
        for word in utils.normalize_toupper(text):
            if len(word) < 3: continue
            new_indexes = set(self.airports_index.get(word, []))
            if first_run: 
                indexes = new_indexes
            else: 
                indexes &= new_indexes
            first_run = False

        indexes = [index for index in indexes]
        indexes.sort()
        airports = [self.airports[index] for index in indexes]
        return airports


    # update in memory structures only if they have changed
    def update(self):
        Log.Write('testing')

        any_modified = False

        #if nothing changed: do nothing
        modified, self.airports = read_csv_if_newer('airports_and_stations.csv', self.airports, ['ident', 'name', 'elevation_ft'], csv.QUOTE_MINIMAL)
        any_modified |= modified

        modified, self.runways = read_csv_if_newer('runways.csv', self.runways, ['airport_ident', 'length_ft', 'surface', 'le_ident', 'he_ident', 'closed', 'le_heading_degT'], csv.QUOTE_MINIMAL)
        any_modified |= modified


        if any_modified:

            Log.Write('rebuilding indexes')

            # rebuild indexes
            airports_index = {}
            airports_ident = {}

            runways = self.runways
            runways_iter = iter(runways)
            runway = next(runways_iter, None)


            for index, airport in enumerate(self.airports):
                ident = airport['ident']
                airports_ident[ident] = airport

                #clean name
                name = utils.normalize_toupper(airport['name'])
                #add ident
                name.append(ident)

                #add all those words to the search index
                words = set()
                for word in name:
                    for i in range(3, len(word) + 1):
                        words.add(word[0:i])

                for word in words:
                    indexes = airports_index.get(word, None)
                    if indexes:
                        indexes.append(index)
                    else:
                        airports_index[word] = [ index ]


                # find matching runways, if any
                airport_runways =  []

                while runway and ident > runway['airport_ident']: runway = next(runways_iter, None)
                while runway and ident == runway['airport_ident']:
                    if runway['closed'] == '0':
                        airport_runways.append(runway)
                    runway = next(runways_iter, None)

                airport['runways'] = airport_runways

            
            self.airports_index = airports_index
            self.airports_ident = airports_ident


        modified, self.metars = read_csv_if_newer('metars.cache.csv', self.metars, ['station_id', 'raw_text', 'flight_category', 'wind_dir_degrees', 'wind_speed_kt', 'wind_gust_kt'], csv.QUOTE_NONE)
        any_modified |= modified

        modified, self.tafs = read_csv_if_newer('tafs.cache.csv', self.tafs, ['station_id', 'raw_text'], csv.QUOTE_NONE)
        any_modified |= modified

        if not any_modified:
            return False


        Log.Write('updating')

        tafs = self.tafs
        metars = self.metars

        now = datetime.utcnow()

        for metar in metars:
            raw_text = metar['raw_text']
            # this happens
            if raw_text[0] == '\x0a': raw_text = raw_text[1:]
            if raw_text[0] == '"': raw_text = raw_text[1:]
            metar['diff'] = ''
            metar['raw_text'] = raw_text

            
            if not raw_text.startswith('METAR '): 
                Log.Write("INV %s" % raw_text)
                continue

            raw_text = raw_text[6:]

            try:
                day = int(raw_text[5:7])
                hour = int(raw_text[7:9])
                minute = int(raw_text[9:11])
                month = now.month
                year = now.year
                date = datetime(year, month, day, hour, minute)
                diff = (now - date).total_seconds() // 60
                # TODO: adjust diff for all cases (previous day, month, year..)
                metar['diff'] = diff
                metar['valid'] = str(diff < 35)
            except:
                Log.Log_Exception()
                Log.Write('Invalid METAR %s' % raw_text)



        #TODO: AMD COR CNL
        #inconsistency in the source - sometimes a TAF starts with the word TAF, sometimes not
        for i, taf in enumerate(tafs):
            raw_text = taf['raw_text']
            if raw_text.startswith('TAF '): tafs[i]['raw_text'] = raw_text[4:]
        

        # advance in all sorted lists at the same time, and find matching metars and tafs
        metars_iter = iter(metars)
        metar = next(metars_iter, None)

        tafs_iter = iter(tafs)
        taf = next(tafs_iter, None)

        for airport in self.airports:
            ident = airport['ident']

            # find matching metar and taf if any
            airport['metar'] = None
            airport['taf'] = None

            while metar and ident > metar['station_id']: metar = next(metars_iter, None)
            if metar and ident == metar['station_id']: airport['metar'] = metar

            while taf and ident > taf['station_id']: taf = next(tafs_iter, None)
            if taf and ident == taf['station_id']: airport['taf'] = taf


        Log.Write('done')

        return True


    def calc_wind(self, airport):
        wind = {}

        metar = airport['metar']

        if metar:
            wind_dir_degrees = metar['wind_dir_degrees']
            wind_speed_kt = metar['wind_speed_kt']
            wind_gust_kt = metar['wind_gust_kt']
            if wind_gust_kt == '': wind_gust_kt = '0'

            try:
                wind_dir_degrees = int(wind_dir_degrees)
                wind_speed_kt = int(wind_speed_kt)
                wind_gust_kt = int(wind_gust_kt)
            except:
                metar = None

        if metar:
            wind_origin = int((wind_dir_degrees%360) / 22.5 + 0.5)
            wind_origins = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N']
            wind['wind_origin'] = wind_origins[wind_origin]


        runway_winds = []

        for runway in airport['runways']:

            try:
                runway_heading = runway['le_heading_degT']
                runway_heading = float(runway_heading)
            except:
                runway_heading = None

            if runway_heading is None:
                try:
                    n = 0
                    runway_heading = runway['le_ident']
                    for i in runway_heading:
                        if not i.isnumeric(): break
                        n += 1
                    runway_heading = runway_heading[0:n]
                    runway_heading = int(runway_heading) * 10
                except:
                    runway_heading = None

            runway_wind = {}

            if metar and runway_heading != None:
                runway_wind['le_heading'] = runway_heading
                angle = utils.angle_diff(wind_dir_degrees, runway_heading)
                if angle < -90 or angle > 90: 
                    runway_heading = (runway_heading + 180) % 360
                    angle = utils.angle_diff(wind_dir_degrees, runway_heading)
                    runway_wind['le_class'] = 'runway_red'
                    runway_wind['he_class'] = 'runway_green'
                else:
                    runway_wind['le_class'] = 'runway_green'
                    runway_wind['he_class'] = 'runway_red'

                runway_wind['crosswind_angle'] = angle

                deg = math.radians(angle)
                sin = math.sin(deg)
                cos = math.cos(deg)
                cross_wind = int(sin * wind_speed_kt)
                head_wind = int(cos * wind_speed_kt)
                gust_cross_wind = int(sin * wind_gust_kt)
                gust_head_wind = int(cos * wind_gust_kt)

                if cross_wind < 0:
                    runway_wind['crosswind_type'] = '↑'
                    cross_wind = -cross_wind
                    gust_cross_wind = -gust_cross_wind
                else:
                    runway_wind['crosswind_type'] = '↓'

                runway_wind['wind'] = (cross_wind, head_wind, gust_cross_wind, gust_head_wind)

            runway_winds.append(runway_wind)
            
        wind['runway_winds'] = runway_winds

        return wind


cache = Cache()

def download():
    global cache
    cache.download()

#update in memory datasets every 30s in the background
def update():
    global cache
    new_cache = Cache(cache)
    if new_cache.update():
        cache = new_cache


#files must be present at startup
#note: download() should be run as a separate task with cron or something
#as actually coded, it would run on all frontend servers which is silly
utils.StartThread(download, runImmediately=True, delay=30, restartOnException=True)

#initialize dataset
#make sure update() runs once immediately and block until it does, then run it every 30s after that
utils.StartThread(update, runImmediately=True, delay=15, restartOnException=True)

