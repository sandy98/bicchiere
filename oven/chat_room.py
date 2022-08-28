#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json
from datetime import datetime
from bicchiere import Bicchiere, SqliteSession
try:
    from gevent.pywsgi import WSGIServer
    from geventwebsocket import WebSocketError, websocket
    from geventwebsocket.handler import WebSocketHandler
except:
    print("You must do 'pip install gevent-websocket' prior to using this app")
    os.sys.exit(1)

def get_username(app):
    return app.session.user if app.session.user else "Guest-{}".format(datetime.now().microsecond)

def isnone(obj):
    return True if obj is None else False

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
app.session_class = SqliteSession
app.socks = set()
app.msgs = []
app.register_template_filter("isnone", isnone)

@app.get("/")
def home():
    return app.render_template("chat_room.html", 
    session = app.session, is_logged = 1 if app.session.user else 0)

@app.post("/logout")
def logout():
    del app.session.user
    return app.redirect("/")

@app.post("/login")
def login():
    if app.form['user'].value:
        app.session.user = app.form['user'].value
        return app.redirect("/")
    else:
        return app.redirect("/logout")

@app.route('/messages')
def websocket_handler():
    if not app.session.user:
        return app.redirect("/")
    wsock = app.environ.get('wsgi.websocket')
    if not wsock:
        print("No websocket found :-(")
        return "Merda!"
    if not wsock in app.socks:
        wsock = UserSocket(get_username(app), wsock)
        print(f"New socket added for user: {wsock.user}")
        app.socks.add(wsock)
        for msg in app.msgs:
            wsock.socket.send(msg)
    while True:
        try:
            msg = wsock.socket.receive()
            if msg and len(msg):
                #fmsg = '<span style="color: green;">%s:&nbsp;&nbsp;&nbsp;</span><span>%s</span>' % (wsock.user, msg)
                fmsg = json.dumps(dict(user = wsock.user, msg = msg))
                app.msgs.append(fmsg)
                for wsk in app.socks:
                    wsk.socket.send(fmsg)
        except WebSocketError:
            app.socks.remove(wsock)
            break

def main():
    server = WSGIServer(('0.0.0.0', 8088), app, handler_class=WebSocketHandler)
    try:
        print("Serving http and websockets at port 8088.")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer exiting...")
        if hasattr(server, "socket"):
           server.socket.close()
        if hasattr(server, "stop"):
            print("Executing server stop.")
            server.stop()


if __name__ == '__main__':
    main()

