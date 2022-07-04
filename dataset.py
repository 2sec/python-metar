# coding=utf-8

import csv
import time
import math

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

    Log.Write('must reload %s: %s != %s' % (filename, last_modified, new_last_modified))
    content = utils.cloud_download_text(filename)
    last_modified_dic[filename] = new_last_modified

    return content


# read the given csv filename and return a list of dictionaries.
# if the file has not changed, return the existing list
def read_csv_if_newer(filename,  output_list, fields, quoting):

    new_last_modified = utils.tmp_read(filename)

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

        output_list.sort(key=lambda item: item[fields[0]] )

        modified = True

    return modified, output_list




# download the given file from the source and updates it on our cloud
def download_aviationweather_csv(filename):
    base_url = 'https://www.aviationweather.gov/adds/dataserver_current/current/'

    url = base_url + filename

    new_last_modified = utils.tmp_read(filename)

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

    # download all files from the source, if they have changed
    def download(self):

        download_ourairports_csv('airports.csv')
        download_ourairports_csv('runways.csv')
        download_aviationweather_csv('metars.cache.csv')
        download_aviationweather_csv('tafs.cache.csv')


    # update in memory structures only if they have changed
    def update(self):
        Log.Write('testing')

        any_modified = False

        #if nothing changed: do nothing
        modified, self.airports = read_csv_if_newer('airports.csv', self.airports, ['ident', 'name', 'elevation_ft'], csv.QUOTE_MINIMAL)
        any_modified |= modified

        modified, self.runways = read_csv_if_newer('runways.csv', self.runways, ['airport_ident', 'length_ft', 'surface', 'le_ident', 'he_ident', 'closed', 'le_heading_degT'], csv.QUOTE_MINIMAL)
        any_modified |= modified

        modified, self.metars = read_csv_if_newer('metars.cache.csv', self.metars, ['station_id', 'raw_text', 'flight_category', 'wind_dir_degrees', 'wind_speed_kt', 'wind_gust_kt'], csv.QUOTE_NONE)
        any_modified |= modified

        modified, self.tafs = read_csv_if_newer('tafs.cache.csv', self.tafs, ['station_id', 'raw_text'], csv.QUOTE_NONE)
        any_modified |= modified

        if not any_modified:
            return False


        Log.Write('updating')

        tafs = self.tafs
        metars = self.metars
        runways = self.runways

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

        runways_iter = iter(runways)
        runway = next(runways_iter, None)


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

            airport_runways =  []

            while runway and ident > runway['airport_ident']: runway = next(runways_iter)
            while runway and ident == runway['airport_ident']:
                if runway['closed'] == '0':
                    airport_runways.append(runway)
                runway = next(runways_iter)

            airport['runways'] = airport_runways
        

        self.airport_idents = idents
        self.airports_dic = airports_dic

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
            wind_origin = int(wind_dir_degrees / 22.5 + 0.5)
            if wind_origin > 15: wind_origin = 15
            wind_origins = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
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

if True or utils.is_production:
    #check if files need to be downloaded at startup
    cache.download()

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



