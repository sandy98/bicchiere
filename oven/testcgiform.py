#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from re import M
from bicchiere import Bicchiere as B

B.config.debug = True

app = B("CGI")

@app.route("/", ["GET", "POST"])
def home():
    future_action = "/cgi-bin/cgiform.py"
    future_action
    current_action = "/"
    current_action
    rm = app.environ.get("request_method".upper())
    tpl = f"""
    <h2>REQUEST METHOD: {rm}</h2>
    <form action="{future_action}", method="POST">
      <div style="width: 50%; max-width: 50%; min-width: 50%; display: flex; flex-direction: column; justify-items: space-between;">
      <p><label>Name  </label><input type="text" name="username" /></p>
      <p><label>Password  </label><input type="password" name="passwd" /></p>
      <p><input type="submit" value="Submit" name="submit" /></p>
    </form>
    """
    posted_data = """
        <h1>Posted data</h1>
        <h2>REQUEST METHOD: {{ reqmet }}</h2>
        {%for k, v in items %}
          <p>{{ k }} = {{ v }}</p>
        {%endfor %}
    """
    if rm.lower() == "get":
        return tpl
    else:
        items = [('Username', app.form['username'].value), 
        ('Password', app.form['passwd'].value)]
        if hasattr(app.form, "fp"):
            items.append(('fp', app.form.fp))
        return app.render_template(posted_data, items=items, reqmet = rm)

os.system("clear")
app.run()