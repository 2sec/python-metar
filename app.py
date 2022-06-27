from flask import Flask
from markupsafe import escape
import flask
import random

from datetime import datetime 
from datetime import timedelta

import dataset

app = Flask(__name__, static_folder='static', static_url_path='')



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
    response = flask.make_response(flask.render_template('index.html', airports=dataset.cache.airports, selected_airports=selected_airports, random_value=random_value))
    write_cookie(response, selected_airports)
    return response


@app.route('/add_airport/<airport>')
def add_airport(airport):
    selected_airports = read_cookie()
    if airport not in selected_airports: selected_airports.append(airport)
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


@app.route('/suggest/<name>')
def suggest(name):
    name = name.upper();
    name_len = len(name)
    matches = []
    for i, ident in enumerate(dataset.cache.airport_idents):
        if ident < name: continue
        if ident[0:name_len] == name: matches.append({'ident': ident, 'name': dataset.cache.airport_names[i]})
        else: break
    return {
        "results": matches,
    }


@app.route('/tasks/download')
def download():
    if flask.request.headers['X-Appengine-Cron'] != 'true':
        return 'wot'
    dataset.cache.download()
    return 'duh'


if __name__ == "__main__":
    app.run(debug=True)

