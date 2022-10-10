#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, cgi, cgitb
from tempfile import TemporaryFile
from io import BytesIO
cgitb.enable()
#from urllib.parse import parse_qsl

#entry = "@@@"
#entry = sys.stdin.read()
#sys.stdin.seek(0)

#tf = TemporaryFile()
#tf.write(entry.encode())
#tf.seek(0)
#form = cgi.FieldStorage(fp=tf, environ=os.environ)
#form = cgi.FieldStorage(fp = BytesIO(entry.encode()))
#form  = dict(parse_qsl(entry))
form = cgi.FieldStorage()

def separator():
    #sys.stdout.write(f"<p>{'-' * 80}</p>\n")
    sys.stdout.write('<hr style="color: red;">\n')

sys.stdout.write("HTTP/1.1 200 OK\r\n")
sys.stdout.write("Content-Type: text/html; charset=utf-8\r\n\r\n")

#separator()
#sys.stdout.write(f"<p>Stdin received: /{entry}/</p>\n")
separator()
for k, v in os.environ.items():
    if k.upper() == "USER":
        sys.stdout.write(f'<p style="padding: 0.5em;">{k} = {v}</p>\n') 
        separator()
sys.stdout.write(f'<p style="padding: 0.5em;">{repr(form)}</p>\n')
separator()
sys.stdout.write(f'<p style="padding: 0.5em;"><strong>Username:</strong> {form.getvalue("username")}</p>\n')
sys.stdout.write(f'<p style="padding: 0.5em;"><strong>Password:</strong> {form.getvalue("passwd")}</p>\n')
separator()

sys.stdout.flush()
