#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, json

def activate_this():
    os.system("clear")
    atp_path = './bin/activate_this.py'
    if os.path.exists(atp_path):
        print('Activating virtual environment.')
        exec(open(atp_path).read(), dict(__file__ = atp_path))
        print('Virtual environment activated.')
    else:
        print("No virtual environment.")
    #time.sleep(2)

activate_this()

os.sys.path.insert(0, os.getcwd())

###while 'bicchiere.py' not in os.listdir():
###    os.chdir('..')
###    os.sys.path.insert(0, os.getcwd())

###print(f"Now working in directory {os.getcwd()}")
#os.chdir('test/')
print(f"This is file {os.path.abspath( __file__)}")

import bicchiere
from bicchiere import run
#from bicchiere import Bicchiere, BicchiereSession, application, run

###bapp = Bicchiere
###sapp = BicchiereSession(bapp)

"""
@bapp.get('/')
@bapp.content_decorator('application/json')
def bapp_home():
    if bapp.session:
        return json.dumps(bapp.session)
    else:
        return json.dumps({'sessid': 'No session'})

@bapp._any('/session/<key>/<value>')
def setkey(key, value):
    if not bapp.session:
       pass
    else:
       bapp.session[key] = value
    return bapp.redirect('/')


ttd = Bicchiere("Test Type Decorators")

@ttd.get('/')
def home():
    return '''
           <p><a href="/plain">Plain Text</a></p>
           <p><a href="/html">Html Text</a></p>
           <p><a href="/forced_plain">Forced Plain Text</a></p>
           <p><a href="/forced_html">Forced Html Text</a></p>
           '''

@ttd.get('/plain')
def plain():
    return "This is old plain text"

@ttd.get('/html')
def html():
    return "<h1>This is HTML text</h1>"

@ttd.get('/forced_plain')
@ttd.plain_content()
def forced_plain():
    return "<h1>This is forced plain text, even though it's in fact HTML</h1>"

@ttd.get('/forced_html')
@ttd.html_content()
def forced_html():
    return "This text is forced to be presented as HTML, while it could in fact be just plain old text."
"""

def main():
    run()

if __name__ == '__main__':
    main()

