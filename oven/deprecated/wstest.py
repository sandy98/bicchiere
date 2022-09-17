# -*- coding: utf-8 -*-

import activate
import os
import base64

from bicchiere import Bicchiere as B

app = B("Test")
app.config.debug = False

home = """
    <!doctype html>
    <html lang=it>
      <head>
         <title>WS Test</title>
         <script>
           var myws = new WebSocket("ws://127.0.0.1:8086/wshome") 
         </script>
         <style>
             .renglon {
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
                margin; 10px;
                margin-bottom: 0.5em;
                padding-left: 1em;
                padding-right; 1em;
                padding-bottom: 10px;
                border-bottom: solid 1px red;
             }
         </style>
      </head>
      <body style="font-family: Helvetica, Arial, sans-serif;">
        {%for k in env %}
           {% if k|ishttp %}
                <div class="renglon"> 
                    <span style="color: steelblue; font-weight: bold;">{{ k }}</span>
                    <span style="color: red;"></span>
                    <span>{{ env[k] }}</span>
                </div>
           {% endif %}
        {% endfor %}
      </body>
    </html>
"""

def ishttp(text):
    return text.lower().startswith("http")

app.register_template_filter("ishttp", ishttp)

@app.get("/")
def homeland():
    return app.render_template(home, env = app.environ)

@app.get("/wshome")
def sockhome():
    for k in app.environ:
        if "CONNECTION" in k:
            print(f"@ {k}: {app.environ[k]}")
        elif "UPGRADE" in k:
            print(f"@ {k}: {app.environ[k]}")
    if app.environ.get("HTTP_SEC_WEBSOCKET_VERSION"):
        print(f"@ HTTP_SEC_WEBSOCKET_VERSION: {app.environ.get('HTTP_SEC_WEBSOCKET_VERSION')}")
    if app.environ.get("HTTP_SEC_WEBSOCKET_KEY"):
        print(f"@ HTTP_SEC_WEBSOCKET_KEY: {app.environ.get('HTTP_SEC_WEBSOCKET_KEY')}")
        print(f"@ HTTP_SEC_WEBSOCKET_KEY length: {len(app.environ.get('HTTP_SEC_WEBSOCKET_KEY'))}")
        key_len = len(base64.b64decode(app.environ.get('HTTP_SEC_WEBSOCKET_KEY')))
        print(f"@ HTTP_SEC_WEBSOCKET_KEY (decoded) length: {key_len}")

    #return app.render_template(home, env = app.environ)
    return "WEBSOCKET"

def main():
    os.system("clear")
    app.debug("Serving web at port 8086.")
    try:
        app.run(host = "0.0.0.0")
    except KeyboardInterrupt:
        app.debug("Ciao")
        os.sys.exit(0)

if __name__ == '__main__':
    main()