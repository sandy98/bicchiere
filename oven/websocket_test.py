#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from datetime import datetime
from bicchiere import Bicchiere
from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketError, websocket
from geventwebsocket.handler import WebSocketHandler

html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>WebSocket Test</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">
    <!--[if lt IE 9]><script src="js/html5shiv-printshiv.js" media="all"></script><![endif]-->
 <style>
  body {
    font-family: Helvetica, Arial;
    margin-left: 3%;
  }
  .title {
    color: steelblue;
    text-align: center;
  }
  .messages {
    width: 95%;
    max-width: 95%;
    min-width: 95%;
    height: 15em;
    max-height: 15em;
    min-height: 15em;
    padding: 5px;
    border-radius: 4px;
    border: solid 1px;
    overflow: auto;
    margin-bottom: 12px;
  }
  .renglon {
    width: 95%;
    height: 2em;
    min-height: 2em;
  }
 </style>    
</head>
<body>
    <h1 class="title">Messages</h1>
    <div class="messages" id="msg_list"></div>
    <div class="renglon">
        <input style="width: 100%; height: 1.8em;" type="text" id="txt_msg"s/>
    </div>
    <script>
        var txt_msg  = document.getElementById('txt_msg');
        var msg_list  = document.getElementById('msg_list');
        var ws = new WebSocket("ws://savos.sytes.net:8088/messages")
        ws.onopen = function() {
            ws.send(new Date().toISOString());
        }
        txt_msg.addEventListener('keyup', function(ev) {
            if (ev.keyCode != 13) return false;
            if (ev.target.value.length) ws.send(ev.target.value);
            ev.target.value = "";
            return true;
        } )
        ws.onmessage = function(ev) {
            // alert(ev.data);
            var newdiv = document.createElement('div');
            newdiv.innerHTML = ev.data;
            msg_list.appendChild(newdiv);
            msg_list.scrollTop = msg_list.scrollHeight;
        }
    </script>
</body>
</html>
'''

def get_username():
    return "Guest-{}".format(datetime.now().microsecond)

class UserSocket:
    def __init__(self, user, socket):
        self.user = user
        self.socket = socket

    def __hash__(self):
        return hash(self.socket)

    def __eq__(self, other):
        if isinstance(other, websocket):
            return self.socket == other
        elif isinstance(other, UserSocket):
            return self.socket == other.socket
        else:
            return False

app = Bicchiere()
app.socks = set()

@app.get("/")
def home():
    return html

@app.route('/messages')
def websocket_handler():
    wsock = app.environ.get('wsgi.websocket')
    if not wsock:
        print("No websocket found :-(")
        return "Merda!"
    if not wsock in app.socks:
        wsock = UserSocket(get_username(), wsock)
        app.socks.add(wsock)
    while True:
        try:
            msg = wsock.socket.receive()
            for wsk in app.socks:
                wsk.socket.send('<span style="color: green;">%s:&nbsp;&nbsp;&nbsp;</span><span>%s</span>' % (wsock.user, msg))
        except WebSocketError:
            app.socks.remove(wsock)
            break
if __name__ == '__main__':
    os.system("clear")
    server = WSGIServer(('0.0.0.0', 8088), app, handler_class=WebSocketHandler)
    server.serve_forever()
