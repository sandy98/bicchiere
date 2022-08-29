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

html = """

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
    margin-right: 3%;
  }
  hr {
    color: transparent;
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
  .statusline {
    width: 95%;
    max-width: 95%;
    min-width: 95%;
    margin-top: 0.5em; 
    margin-bottom: 0.5em; 
    padding: 6px; 
    border:solid 1px; 
    border-radius: 3px; 
    display: flex; flex-direction: row; 
    align-items: center; 
    justify-content: flex-end;
  }
 </style>    
</head>
<body>
    <h1 class="title">Bicchiere Chat Room</h1>
    <hr>
    <div class="statusline">
      {%if session.user %}
        <span style="color: {{ session.usercolor }}; margin-right: 0.5em;">{{ session.user }}</span>
        <form action="/logout" method="POST">
          <button type="submit">Logout</button>
        </form>
      {# endif #}
      {% else %}
      {# if session.user|isnone #}
      <form action="/login" method="POST">
        <label for="txtuser">User:</label>
        <input type="text" id="txtuser" name="user" required />
        <input type="color" value="#008800" name="usercolor" />
        <button type="submit">Login</button>
      </form>
      {% endif %}
   </div>
   <hr>
   <div class="messages" id="msg_list"></div>
    <div class="renglon">
        <label for="txt_msg">Message:</label>
        <input style="width: 80%; height: 1.8em;" type="text" id="txt_msg"/>
    </div>
    
    <script>
        var is_logged = {{ is_logged }};
        var txt_msg  = document.getElementById('txt_msg');
        var msg_list  = document.getElementById('msg_list');
        var ws = new WebSocket(location.protocol == "https:" ? "wss" : "ws" + "://" + location.hostname + ":8088/messages")
        ws.onopen = function() {
            if (is_logged) {
              ws.send("Logged in at " + new Date().toLocaleString());
            }
        }
        txt_msg.addEventListener('keyup', function(ev) {
            if (ev.keyCode != 13) return false;
            if (is_logged) {
              if (ev.target.value.length) ws.send(ev.target.value);
              ev.target.value = "";
              return true;
            } else {
              alert("Must be logged in to send messages.");
              return false;
            }
        } )
        ws.onmessage = function(ev) {
            // alert(ev.data);
            data = JSON.parse(ev.data);
            var innerHTML = `<span style="color: ${data.usercolor};">${data.user}:&nbsp;&nbsp;&nbsp;</span><span>${data.msg}</span>`
            var newdiv = document.createElement('div');
            newdiv.innerHTML = innerHTML;
            msg_list.appendChild(newdiv);
            msg_list.scrollTop = msg_list.scrollHeight;
        }
    </script>
</body>
</html>

"""

def get_username(app):
    return app.session.user if app.session.user else "Guest-{}".format(datetime.now().microsecond)

def isnone(obj):
    return True if obj is None else False

class UserSocket:
    def __init__(self, user, socket, usercolor = "#008800"):
        self.user = user
        self.socket = socket
        self.usercolor = usercolor

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
    return app.render_template(html, session = app.session, is_logged = 1 if app.session.user else 0)

@app.post("/logout")
def logout():
    del app.session.user
    return app.redirect("/")

@app.post("/login")
def login():
    if app.form['user'].value:
        app.session.user = app.form['user'].value
        app.session.usercolor = app.form['usercolor'].value
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
        wsock = UserSocket(get_username(app), wsock, usercolor = app.session.usercolor or "#008800")
        print(f"New socket added for user: {wsock.user}")
        app.socks.add(wsock)
        for msg in app.msgs:
            wsock.socket.send(msg)
    while True:
        try:
            msg = wsock.socket.receive()
            if msg and len(msg):
                fmsg = json.dumps(dict(user = wsock.user, msg = msg, usercolor = wsock.usercolor))
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

