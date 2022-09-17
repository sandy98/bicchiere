#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    import activate
except:
    pass

import asyncio
from bicchiere import Bicchiere, Session, application as app
Bicchiere.config.session_class = Session
from hypercorn.config import Config
from hypercorn.asyncio import  serve

config = Config()
config.bind = ["localhost:8086"]

@app.get("/sock2")
def sock2():
    script = """
    <!doctype=html>
    <head>
       <title>Sock 2</title>
    </head>
    <body>
      <h1>WebSocket Test</h1>
      <script>
          var myws = new WebSocket("ws://localhost:8086/dosock")
      </script>
    </body>
    """
    return script

@app.get("/dosock")
@app.websocket_handler
def dosock():
    app.websocket = app.environ.get("wsgi.websocket")
    print("Websocket created!!")

def main():
    #app.run()
    asyncio.run(serve(app, config))

if __name__ == '__main__':
    main()