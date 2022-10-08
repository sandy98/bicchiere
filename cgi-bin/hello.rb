#!/usr/bin/env ruby
# -*- coding: utf-8 -*-

$stdout.write "HTTP/1.1 200 OK \r\n"
$stdout.write "Content-Type: text/html; charset=utf-8\r\n\r\n"
$stdout.write "<h1 style=\"text-align: center; color: #aa0000;\"> Ciao, Mondo Ruby CGI :-) </h1>\r\n"
$stdout.flush
