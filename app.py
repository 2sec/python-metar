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
static_version = '20220731-04'
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



# the selected airports list is stored in the cookies but cookies do not work within the javascript service worker (because of fetch() which removes the headers)
# and iOS furthermore does not transmit existing cookies to the PWA app when installing it (contrary to Android or Windows)
# hence they are also propagated through the URLs to cover all cases
def read_cookie():
    selected_airports = flask.request.args.get('airports', '')
    if not selected_airports: selected_airports = flask.request.cookies.get('airports', '')
    selected_airports = selected_airports.split(',')
    return selected_airports

def write_cookie(response, selected_airports):
    expires = datetime.utcnow() + timedelta(days = 365 * 10)
    response.set_cookie('airports', selected_airports, expires=expires)


# no longer used as redirects are not supported in service workers
def redirect(selected_airports):
    selected_airports = ','.join(selected_airports)
    redirect = flask.redirect('/')
    write_cookie(redirect, selected_airports)    
    return redirect



@app.route('/airports')
def airports(template = 'airports.html', remove_airport = None, add_airport = None, move_airport = None):
    selected_airports = read_cookie()

    if remove_airport and remove_airport in selected_airports: selected_airports.remove(remove_airport)
    if add_airport and add_airport not in selected_airports: selected_airports.insert(0, add_airport)
    if move_airport:
        index = selected_airports.index(move_airport)
        if index > 0:
            del selected_airports[index]
            selected_airports.insert(index - 1, move_airport)


    now = utils.ShortDateTime()

    airport_winds = []
    airports = []
    for airport in selected_airports:
        airport = dataset.cache.airports_ident.get(airport, None)
        if airport:
            airport_winds.append(dataset.cache.calc_wind(airport))
            airports.append(airport)

    selected_airports = ','.join(selected_airports)
        
    response = flask.make_response(flask.render_template(template, selected_airports=selected_airports, now = now, airports = airports, airport_winds = airport_winds, random_value=random_value, static_version=static_version, static_path=static_path))
    write_cookie(response, selected_airports)
    return response


@app.route('/')
def home():
    args = flask.request.args;
    remove_airport = args.get('remove', None)
    add_airport = args.get('add', None)
    move_airport = args.get('move', None)

    return airports('index.html', remove_airport, add_airport, move_airport)


#return airports matching given word
@app.route('/suggest/<name>')
def suggest(name):
    print(name)
    matches = []
    airports = dataset.cache.find_airports(name)
    for airport in airports:
        matches.append({'ident': airport['ident'], 'name': airport['name']})
    return { "results": matches }


if __name__ == "__main__":
    app.run(debug=True)
    # note: debug=True restart the whole app but does not kill existing threads apparently!


