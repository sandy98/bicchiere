#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json

try:
    import activate
except:
    atp_path = './bin/activate_this.py'
    if os.path.exists(atp_path):
        print('Activating virtual environment.')
        exec(open(atp_path).read(), dict(__file__ = atp_path))
        print('Virtual environment activated.')
    else:
        print("No virtual environment.")


from datetime import datetime
try:
    from bicchiere import Bicchiere, SqliteSession, WebSocket, WebSocketError, TWServer, FixedHandler
except:
    print("You must run 'pip install bicchiere' prior to using this app")
    os.sys.exit(1)

try:
    from wsocket import WebSocket as WS
    print("Using wsoket.WebSocket for real time connection.")
except:
    WS = None
    print("You must run 'pip install wsocket' prior to using this feature")

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
        var ws = new WebSocket(location.href.replace("http", "ws") + "messages")
        ws.onopen = function() {
            if (is_logged) {
              ws.send("Logged in at " + new Date().toLocaleString());
            } else {
              console.log("New websocket open at " + ws.url);
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
            console.log(ev.data);
            data = JSON.parse(ev.data);
            console.log(data);
            console.log("Received at " + new Date().toLocaleString());
            var innerHTML = `<span style="color: ${data.usercolor};">${data.user}:&nbsp;&nbsp;&nbsp;</span><span>${data.msg}</span>`
            var newdiv = document.createElement('div');
            newdiv.innerHTML = innerHTML;
            msg_list.appendChild(newdiv);
            msg_list.scrollTop = msg_list.scrollHeight;
        }
        ws.onclose = function(ev) {
            console.log("Websocket closed at " + new Date().toLocaleString());
        }
        ws.onerror = function(ev) {
            console.warn("Websocket (" + ws.url + ") error: " + new Date().toLocaleString());
            console.info(ev);
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
        if isinstance(other, WebSocket):
            return self.socket == other
        elif isinstance(other, UserSocket):
            return self.socket == other.socket
        else:
            return False

app = Bicchiere()

app.config.session_class = SqliteSession
#app.config.websocket_class = WS if WS else WebSocket
app.config.websocket_class = WebSocket
app.config.debug = True

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
@app.websocket_handler
def ws_handler():
    if not app.session.user:
        return app.redirect("/")
    wsock = app.environ.get('wsgi.websocket')
    if not wsock:
        msg = "No websocket found in environment. :-("
        print(msg)
        return msg
    if not wsock in app.socks:
        wsock = UserSocket(get_username(app), wsock, usercolor = app.session.usercolor or "#008800")
        print(f"New socket added for user: {wsock.user}")
        app.socks.add(wsock)
        for msg in app.msgs:
            wsock.socket.send(msg)
    else:
        wsock.user = app.session.user
        wsock.usercolor = app.session.usercolor
    while True:
        try:
            msg = wsock.socket.receive()
            if msg and len(msg):
                app.debug(f"Received a message: {repr(msg)}")
                fmsg = json.dumps(dict(user = wsock.user, msg = msg, usercolor = wsock.usercolor))
                app.msgs.append(fmsg)
                for wsk in app.socks:
                    wsk.socket.send(fmsg)
            elif msg and not len(msg):
                app.debug("Received an empty message. :-((")
            app.debug("Now pinging the client to keep him alive...")
            wsock.socket.send_frame("Ping", wsock.socket.OPCODE_PING)
        except WebSocketError as err:
            app.debug(f"Error in socket: {repr(err)}")
            app.socks.remove(wsock)
            break
#        finally:
#            return "Websocket set, used and now is out."

def main():
    try:
        #print("Serving http and websockets at port 8088.")
        #server.serve_forever()
        os.system("clear")
        #app.debug(f"Using web socket class: {'wsocket.WebSocket' if WS else 'bicchiere.WebSocket'}")
        app.debug(f"Using web socket class: {'bicchiere.WebSocket'}")
        app.run(host = "127.0.0.1", application=app,
        server_name="twserver", handler_class = FixedHandler, server_class = TWServer)
    except KeyboardInterrupt:
        print("\nServer exiting...")
        os.sys.exit()        

if __name__ == '__main__':
    main()
else:
    application = app

