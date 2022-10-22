# -*- coding: utf-8 -*-

#from bicchiere import application as app
from bicchiere import Bicchiere as B

body = b"""
    <!DOCTYPE html>
    <html lang="it">
        <head>
        <title>Hello Page</title>
        </head>
        <body style="font-family: Helvetica, Arial, sans-serif;">
        <h1 style="text-align: center; color: steelblue;">
            Hello, WSGI!!
        </h1>
        </body>
    </html>
"""

def appita(environ, start_response):
    start_response("200 OK", [('Content-Type', 'text/html; charset=utf-8')])
    return [body]

appB = B("Test WSGI Server")

@appB.get("/")
def home():
    return body


from bottle import Bottle
app = Bottle(__name__)

@app.get("/")
def home():
    return body

