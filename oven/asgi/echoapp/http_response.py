# -*- coding: utf-8 -*-

async def http_application(scope, _, send):
    response_start = dict(type="http.response.start", status = 200, headers = [(b'Content-Type', b'text/html; charset=utf-8')])
    await send(response_start)
    html = b"""
    <!DOCTYPE html>
    <html lang="it">
      <head>
      </head>
      <body style="font-family: Helvetica, Arial, sans-serif; padding: 10px;">
        <div id="main">
          <div style="text-align: center;">
            <input type="text" style="width: 80%; height: 1.5em;" name="testo" id="testo" />
          </div>
          <hr style="width: 100%; margin-top: 1.5em; margin-bottom: 1.5em;">
          <div style="font-family: monospace; background: inherit; color: steelblue;">
            <div id="messages" style="width: 80%; margin-left: 10%; height: 40em; max-height: 40em; overflow: auto; scroll-behavior: auto; border: solid 1px;">
            </div>
          </div>
        </div>
        <script>
            var myws = new WebSocket(location.href.replace("http", "ws"));
            var testo = document.getElementById("testo");
            var messages = document.getElementById("messages");
            testo.addEventListener("keyup", evt => {
                //console.log("keyup code: " + evt.keyCode);
                if (evt.keyCode != 13)
                   return false;
                data = evt.target.value;
                //console.log(evt.target.value);
                if (data.length && myws.readyState == 1) {
                    evt.target.value = "";
                    myws.send(data);
                    return true;
                }
                return false;
            })
            myws.onopen = evt => console.log("Websocket opened");
            myws.onerror = evt => console.error(evt);
            myws.onmessage = evt => {
                console.log("Received: " + evt.data);
                if (evt.data && evt.data.length) {
                    var par = document.createElement("p");
                    par.innerText = evt.data;
                    par.style.height = "0.5em";
                    par.style.maxHeight = "0.5em";
                    par.style.padding = "8px";
                    messages.appendChild(par);
                    messages.scrollTop = messages.scrollHeight;
                }
            }
        </script>
      </body>
    </html>
    """
    response_body = dict(type="http.response.body", body=html, more_body=False)
    return await send(response_body)
