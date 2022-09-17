#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    import activate
except:
    pass

from bicchiere import Bicchiere, Session

Bicchiere.config.session_class = Session

app = Bicchiere("WebSocket Test")

@app.get("/")
def home():
    return """
        <p>
           <h1>WebSocket Test</h1>
        </p>
        <script>
            var ws = new WebSocket("ws://localhost:8086/wstest")
        </script>
    """

@app.get("/wstest")
@app.websocket_handler
def wstest():
    app.wsock = app.environ.get("wsgi.websocket")
    #wsock.send("Hello!")
    return b' '

def main():
    app.run()

if __name__ == '__main__':
    main()