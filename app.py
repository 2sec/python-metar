# coding=utf-8


from flask import Flask
import flask
import random

from datetime import datetime 
from datetime import timedelta

import dataset


app = Flask(__name__, static_folder='static', static_url_path='')
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.jinja_env.globals.update(zip=zip)

random_value = random.getrandbits(64)

def read_cookie():
    selected_airports = flask.request.cookies.get('airports')
    if not selected_airports: selected_airports = ''
    selected_airports = selected_airports.split(',')
    return selected_airports

def write_cookie(response, selected_airports):
    expires = datetime.utcnow() + timedelta(days = 365 * 10)
    response.set_cookie('airports', ','.join(selected_airports), expires=expires)


@app.route('/')
def home():
    selected_airports = read_cookie()
    
    airport_winds = []
    airports = []
    for airport in selected_airports:
        airport = dataset.cache.airports_dic.get(airport, None)
        if airport:
            airport_winds.append(dataset.cache.calc_wind(airport))
            airports.append(airport)

    response = flask.make_response(flask.render_template('index.html', airports = airports, airport_winds = airport_winds, random_value=random_value))
    write_cookie(response, selected_airports)
    return response


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


#return airports matching given text
#currently only the ICAO code is searched
#TODO: also search any word in the airport names
@app.route('/suggest/<name>')
def suggest(name):
    name = name.upper();
    print(name)
    name_len = len(name)
    matches = []
    for ident in dataset.cache.airport_idents:
        if ident < name: continue
        if ident[0:name_len] == name: matches.append({'ident': ident, 'name': dataset.cache.airports_dic[ident]['name']})
        else: break
    return {
        "results": matches,
    }


#download datasets if they have changed
#called by GAE every min
@app.route('/tasks/download')
def download():
    if flask.request.headers.get('X-Appengine-Cron', None) != 'true':
        return 'wot'
    dataset.cache.download()
    return 'duh'


if __name__ == "__main__":
    app.run(debug=True)

