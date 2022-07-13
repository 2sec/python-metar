# coding=utf-8


from flask import Flask
import flask
import random

from datetime import datetime 
from datetime import timedelta

import dataset
import utils


app = Flask(__name__, static_folder='static', static_url_path='')

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
#this allows the zip function to the be callable in the templates
app.jinja_env.globals.update(zip=zip)

random_value = random.getrandbits(64)
static_version = '20220703-01'
static_path = '/cache/' + static_version + '/'

# cache versioning for static files
@app.route('/cache/<version>/<filename>')
def cache(version, filename):
        response = flask.send_from_directory('./static/', filename)
        response.headers['Cache-Control']  = 'max-age=31536000, immutable'
        for header in ['Expires', 'ETag', 'Last-Modified']:
            if header in response.headers:
                del response.headers[header]
        return response


def read_cookie():
    selected_airports = flask.request.cookies.get('airports')
    if not selected_airports: selected_airports = ''
    selected_airports = selected_airports.split(',')
    return selected_airports

def write_cookie(response, selected_airports):
    expires = datetime.utcnow() + timedelta(days = 365 * 10)
    response.set_cookie('airports', ','.join(selected_airports), expires=expires)


@app.route('/airports')
def airports(template = 'airports.html'):
    selected_airports = read_cookie()

    now = utils.ShortDateTime()

    airport_winds = []
    airports = []
    for airport in selected_airports:
        airport = dataset.cache.airports_ident.get(airport, None)
        if airport:
            airport_winds.append(dataset.cache.calc_wind(airport))
            airports.append(airport)

    response = flask.make_response(flask.render_template(template, now = now, airports = airports, airport_winds = airport_winds, random_value=random_value, static_version=static_version, static_path=static_path))
    write_cookie(response, selected_airports)
    return response

@app.route('/')
def home():
    return airports('index.html')
    


# add, remove or move an airport up in the list
@app.route('/add_airport/<airport>')
def add_airport(airport):
    selected_airports = read_cookie()
    if airport not in selected_airports: selected_airports.insert(0, airport)
    redirect = flask.redirect('/')
    write_cookie(redirect, selected_airports)
    return redirect

@app.route('/remove_airport/<airport>')
def remove_airport(airport):
    selected_airports = read_cookie()
    if airport in selected_airports: selected_airports.remove(airport)
    redirect = flask.redirect('/')
    write_cookie(redirect, selected_airports)
    return redirect

@app.route('/move_airport/<airport>')
def move_airport(airport):
    selected_airports = read_cookie()
    if airport in selected_airports: 
        index = selected_airports.index(airport)
        if index > 0:
            del selected_airports[index]
            selected_airports.insert(index - 1, airport)
        redirect = flask.redirect('/')
    write_cookie(redirect, selected_airports)
    return redirect


#return airports matching given word
@app.route('/suggest/<name>')
def suggest(name):
    print(name)
    matches = []
    airports = dataset.cache.find_airports(name)
    for airport in airports:
        matches.append({'ident': airport['ident'], 'name': airport['name']})
    return { "results": matches }


#download datasets if they have changed
#called by GAE every min
@app.route('/tasks/download')
def download():
    if not(flask.request.headers.get('X-Appengine-Cron', None) == 'true' or flask.request.remote_addr == '127.0.0.1'):
        return 'wot'
    dataset.cache.download()
    return 'duh'


@app.route('/_ah/warmup')
def warmup():
    return 'duh'

if __name__ == "__main__":
    app.run(debug=True)
    # note: debug=True restart the whole app but does not kill existing threads apparently!


