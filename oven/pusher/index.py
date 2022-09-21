#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pusher
from bicchiere import Bicchiere

pusher_client = pusher.Pusher(
  app_id='1480392',
  key='9fdc4bddc8888628d95a',
  secret='626e7d59fdfb57cf46f8',
  cluster='sa1',
  ssl=True
)

app = Bicchiere()

@app.get("/")
def home():
    pusher_client.trigger('my-channel', 'my-event', {'message': 'Ciao,  Mondo!'})
    app.redirect("/static/index.html")

if __name__ == '__main__':
    app.run()

