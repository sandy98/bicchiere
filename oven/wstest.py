#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
msg1 = msg2 = msg3 = ""

try:
    import activate
    msg1 = "Virtual environment activated"
except:
    msg1 = "Virtual environment could NOT be activated"

try:
    from bicchiere import Bicchiere, WebSocket
    msg2 = "Bicchiere imported"
except:
    os.system("clear")
    print("Bicchiere not found. Quitting")
    os.sys.exit()


html = """
    <input type="text" name="txt_chat" id="txt_chat" required />
    <br/>
    <div id="messages">
    </div>
    <script>
      var txtChat = document.getElementById("txt_chat");
      var messages = document.getElementById("messages");
      function print_message(msg) {
        if (!msg.length) return;
        p = document.createElement("p");
        p.innerHTML = msg;
        messages.appendChild(p);
        document.body.scrollTop = document.body.scrollHeight;
      }
      txtChat.addEventListener("keyup", function(ev) {
        if (ev.keyCode != 13 || !ev.target.value.length) return;
        if (ws.readyState == 1)
            ws.send(ev.target.value);
        else
            print_message("Websocket is closed.");
        ev.target.value = "";
      })
      var ws = new WebSocket("ws://localhost:8086/chat");
      ws.onopen = msg => print_message("WebSocket opened");
      ws.onmessage = msg => {
        console.log("Received a message from server.")
        console.info(msg);
        print_message(msg.data);
      }
      ws.onerror = msg => print_message("Closed");
      ws.onerror = msg => print_message("WebSocket Error");
    </script>
"""

app = Bicchiere("WSTest")
app.config.debug = True
app.config.websocket_class = WebSocket
msg3 = f"Websocket class: {app.config.websocket_class.__name__}"

@app.route("/")
@app.html_content()
def home():
    return html

@app.route("/chat")
@app.websocket_handler
def chat():
    wsock = app.environ.get('wsgi.websocket')
    if not wsock:
        app.debug("Something wrong, couldnt find socket")
    else:
        app.debug(f"Found a shiny web socket: {repr(wsock)}")
        wsock.send("Hello, bunch of sockets!")
    while True:
        try:
            msg = wsock.receive()
            app.debug(f"Received a message from remote socket: {repr(msg)}")
            if msg != None and len(msg):
                wsock.send(msg)
        except Exception as exc:
            break

@app.get("/showh")
#@app.plain_content()
def showh():
    return "<h1>This is a BIG Html banner</h1>"

@app.get("/showp")
#@app.html_content()
def showh():
    return "&lt;h1&gt;This pretends to be a BIG Html banner, but it is not :-(&lt;/h1&gt;"

def main():
    os.system("clear")
    print(f"{msg1}\n{msg2}\n{msg3}\n")
    try:
        app.run()
    except Exception as exc:
        print(f"Quitting app because of {repr(exc)}")
        os.sys.exit()
        
if __name__ == '__main__':
    main()
    


