#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

sys.stdout.write('HTTP/1.1 200 OK \r\n')
sys.stdout.write('Content-Type: text/html; charset=utf-8\r\n\r\n')
sys.stdout.write('<h1 style="text-align: center; color: green;"> Ciao, Mondo Python CGI :-) </h1>\r\n')
sys.stdout.flush()
