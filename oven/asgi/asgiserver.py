#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys
import asyncio
import socket
from dataclasses import dataclass, field
from typing import List, Tuple
import http


class SplitBuffer:
    def __init__(self):
        self.data = b""

    def feed_data(self, data: bytes):
        self.data += data

    def pop(self, separator: bytes):
        first, *rest = self.data.split(separator, maxsplit=1)
        # no split was possible
        if not rest:
            return None
        else:
            self.data = separator.join(rest)
            return first

    def flush(self):
        temp = self.data
        self.data = b""
        return temp


class HttpRequestParser:
    def __init__(self, protocol):
        self.protocol = protocol
        self.buffer = SplitBuffer()
        self.http_method = ""
        self.done_parsing_start = False
        self.done_parsing_headers = False
        self.expected_body_length = 0

    def feed_data(self, data: bytes):
        self.buffer.feed_data(data)
        self.parse()

    def parse(self):
        if not self.done_parsing_start:
            self.parse_startline()
        elif not self.done_parsing_headers:
            self.parse_headerline()
        elif self.expected_body_length:
            data = self.buffer.flush()
            self.expected_body_length -= len(data)
            self.protocol.on_body(data)
            self.parse()
        else:
            self.protocol.on_message_complete()

    def parse_startline(self):
        line = self.buffer.pop(separator=b"\r\n")
        if line is not None:
            http_method, url, http_version = line.strip().split()
            self.http_method = http_method
            self.done_parsing_start = True
            self.protocol.on_url(url)
            self.parse()

    def parse_headerline(self):
        line = self.buffer.pop(separator=b"\r\n")
        if line is not None:
            if line:
                name, value = line.strip().split(b": ", maxsplit=1)
                if name.lower() == b"content-length":
                    self.expected_body_length = int(value.decode("utf-8") if hasattr(value, "decode") else value)
                self.protocol.on_header(name, value)
            else:
                self.done_parsing_headers = True
                self.protocol.on_headers_complete()
            self.parse()


def create_status_line(status_code: int = 200):
    code = str(status_code).encode()
    code_phrase = http.HTTPStatus(status_code).phrase.encode()
    return b"HTTP/1.1 " + code + b" " + code_phrase + b"\r\n"


def format_headers(headers: List[Tuple[bytes, bytes]]):
    return b"".join([key + b": " + value + b"\r\n" for key, value in headers])


def make_response(status_code: int = 200, headers: List[Tuple[bytes, bytes]] = None,  body: bytes = b""):
    if headers is None:
        headers = []
    content = [create_status_line(status_code), format_headers(headers), b"\r\n" if body else b"", body]
    return b"".join(content)



@dataclass
class ASGIRequest:
    http_method: str = ""
    path: str = ""
    headers: List[Tuple[bytes, bytes]] = field(default_factory=lambda: [])
    body_buffer: bytes = b""
    trigger_more_body: asyncio.Event = asyncio.Event()
    last_body: bool = False

    def to_scope(self):
        path_parts = self.path.split("?")
        scope = {
            "type": "http",
            "asgi": {"version": "2.1", "spec_version": "2.1"},
            "http_version": "1.1",
            "method": self.http_method,
            "scheme": "http",
            "path": path_parts[0],
            "query_string": path_parts[1] if len(path_parts) > 1 else "",
            "headers": self.headers,
        }
        return scope

    def to_event(self):
        event = {
            "type": "http.request",
            "body": self.body_buffer,
            "more_body": not self.last_body,
        }
        self.body_buffer = b""
        return event


@dataclass
class ASGIResponse:
    status_code: int = 200
    headers: List[Tuple[bytes, bytes]] = field(default_factory=lambda: [])
    body: bytes = b""
    is_complete: bool = False

    def to_http(self):
        return make_response(self.status_code, self.headers, self.body)

    def feed_event(self, event):
        if event["type"] == "http.response.start":
            self.status_code = event["status"]
            self.headers = event["headers"]
        elif event["type"] == "http.response.body":
            self.body += event.get("body", b"")
            if not event.get("more_body", False):
                self.is_complete = True


class ASGISession:
    def __init__(self, client_socket, address, app):
        self.loop = asyncio.get_event_loop()
        self.client_socket = client_socket
        self.address = address
        self.app = app
        self.trigger_run_asgi = asyncio.Event()
        self.parser = HttpRequestParser(self)
        self.request = ASGIRequest()
        self.response = ASGIResponse()

    async def run(self):
        self.loop.create_task(self.run_asgi())
        while True:
            if self.response.is_complete:
                break
            data = await self.loop.sock_recv(self.client_socket, 1024)
            print(f"Received {data}")
            self.parser.feed_data(data)
        self.client_socket.close()
        print(f"Socket with {self.address} closed.")

    # ASGI Server protocol methods
    async def run_asgi(self):
        await self.trigger_run_asgi.wait()
        return await self.app(self.request.to_scope(), self.receive, self.send)

    async def receive(self):
        while True:
            await self.request.trigger_more_body.wait()
            return self.request.to_event()

    async def send(self, event):
        self.response.feed_event(event)
        if self.response.is_complete:
            resp_http = self.response.to_http()
            await self.loop.sock_sendall(self.client_socket, resp_http)
            print("Response sent.")
            try:
                self.client_socket.close()
            except:
                pass

    # HTTP parser callbacks
    def on_url(self, url):
        print(f"Received url: {url}")
        self.request.http_method = self.parser.http_method.decode("utf-8") if hasattr(self.parser.http_method, "decode") else self.parser.http_method
        self.request.path = url.decode("utf-8") if hasattr(url, "decode") else url

    def on_header(self, name: bytes, value: bytes):
        print(f"Received header: ({name}, {value})")
        self.request.headers.append((name, value))

    def on_headers_complete(self):
        print("Received all headers.")
        self.trigger_run_asgi.set()

    def on_body(self, body: bytes):
        print(f"Received body: {body}")
        self.request.body_buffer += body
        self.request.trigger_more_body.set()

    def on_message_complete(self):
        print("Received request completely.")
        self.request.last_body = True
        self.request.trigger_more_body.set()


class ASGIServer:
    def __init__(self, host: str, port: int, app):
        self.host = host
        self.port = port
        self.app = app

    async def serve_forever(self):
        server_socket = socket.socket()
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)
        server_socket.setblocking(False)

        loop = asyncio.get_event_loop()
        try:
            while True:
                client_socket, address = await loop.sock_accept(server_socket)
                print(f"Socket established with {address}.")
                session = ASGISession(client_socket, address, self.app)
                loop.create_task(session.run())
        except KeyboardInterrupt:
            print("Server stopped due to keyboard interrupt.")
            server_socket.close()
            sys.exit(0)
        except Exception as exc:
            print(f"Server stopped due to exception: {repr(exc)}")    
            server_socket.close()
            sys.exit(255)

test_visitors = 0

async def test_asgi_app(scope, receive, send):
    if scope.get("type") not in ("http", "https"):
        print(f"Unknown scope type: {scope.get('type')}")
        return

    global test_visitors
    test_visitors += 1
    start_response = dict(type="http.response.start", status=200, headers=[(b'Content-Type', b'text/html; charset=utf-8')])
    html = """
    <!DOCTYPE html>
    <html lang="it">
        <head>
            <title>ASGI Test Page</title>
            <style>
              .sign {
                background: #effeef; 
                font-size: 14pt; 
                margin-left: 2em; 
                padding: 10px; 
                border: solid 1px; 
                border-radius: 4px; 
                width: 20%;
                margin-top: 10px;
                text-align: center;
              }
            </style>
        </head>
        <body style="font-family: Helvetica, Arial, sans-serif;">
          <h1 style="padding: 0.5em; text-align: center; color: steelblue;">Hello, ASGI!</h1>
          <div class="sign">
            <span>You're visitor number</span>
            &nbsp;
            <span style="color: red;">{test_visitors}</span>
          </div>
          <div class="sign" style="border: none; background: transparent;">
            <button onclick="location.href=location.href">Reload</button>
          </div>
        </body>
    </html>
    """.replace("{test_visitors}", str(test_visitors))
    body = dict(type="http.response.body", more_body=False, body=html.encode() + b"")
    await send(start_response)
    await send(body)
    return b""

async def main():
    import os
    server = ASGIServer("0.0.0.0", 5000, test_asgi_app)
    os.system("clear")
    print("\nASGI server serving web content at 0.0.0.0:5000\n")
    await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except:
        print("\nServer quitting...\n")
        sys.exit()
