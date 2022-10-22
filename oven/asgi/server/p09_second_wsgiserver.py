#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, http, socket, threading
from typing import Callable, Any, List, Tuple
from dataclasses import dataclass, field
from io import BytesIO
from app import app

class SplitBuffer:
    def __init__(self, init_data = b""):
        self.data = init_data

    def feed_data(self, data: bytes):
        self.data += data

    def pop(self, separator: bytes):
        first, *rest = self.data.split(separator, maxsplit=1)
        # no split was possible
        if not rest:
            return None
        else:
            self.data = separator.join(rest)
            return first.strip()

    def flush(self):
        temp = self.data
        self.data = b""
        return temp


class HttpRequestParser:
    def __init__(self, protocol):
        self.protocol = protocol
        self.buffer = SplitBuffer()
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
            self.http_method, self.url, self.http_version = line.strip().split()
            self.done_parsing_start = True
            self.protocol.on_url(self.url)
            self.parse()

    def parse_headerline(self):
        line = self.buffer.pop(separator=b"\r\n")
        if line is not None:
            if line:
                name, value = line.strip().split(b": ", maxsplit=1)
                if name.lower() == b"content-length":
                    self.expected_body_length = int(value.decode("utf-8"))
                self.protocol.on_header(name, value)
            else:
                self.done_parsing_headers = True
            self.parse()


class WSGISession:
    def __init__(self, client_socket, address):
        self.client_socket = client_socket
        self.address = address
        self.parser = HttpRequestParser(self)
        self.request = WSGIRequest()
        self.response = WSGIResponse()

    def run(self):
        while True:
			# this flag is now stored on the new response object
            if self.response.is_sent:
                break
            data = self.client_socket.recv(1024)
            print(f"Received {data}")
            self.parser.feed_data(data)
        self.client_socket.close()
        print(f"Socket with {self.address} closed.")

    # parser callbacks
    def on_url(self, url: bytes):
        print(f"Received url: {url}")
        self.request.http_method = self.parser.http_method.decode("utf-8")
        self.request.path = url.decode("utf-8")

    def on_header(self, name: bytes, value: bytes):
        print(f"Received header: ({name}, {value})")
        self.request.headers.append(
            (name.decode("utf-8"), value.decode("utf-8"))
        )

    def on_body(self, body: bytes):
        print(f"Received body: {body}")
        self.request.body.write(body)
        self.request.body.seek(0)

    def on_message_complete(self):
        print("Received request completely.")
		# the functionality in this function replaces the previous
		# self.send_response functionality
        environ = self.request.to_environ()
		# the start_response callback is a method on the WSGIResponse object
		# here we call the app to dynamically create a response
        body_chunks = app(environ, self.response.start_response)
        print("App callable has returned.")
        self.response.body = b"".join(body_chunks)
        self.client_socket.send(self.response.to_http())


def create_status_line(status: str = "200 OK") -> str:
    return f"HTTP/1.1 {status}\r\n"


def format_headers(headers: List[Tuple[str, str]]) -> str:
    return "".join([f"{key}: {value}\r\n" for key, value in headers])


def make_response(status: str = "200 OK", headers: List[Tuple[str, str]] = None, body: bytes = b""):
    if headers is None:
        headers = []
    content = [
        create_status_line(status).encode("utf-8"),
        format_headers(headers).encode("utf-8"),
        b"\r\n" if body else b"",
        body,
    ]
    return b"".join(content)

# WSGI Specific

@dataclass
class WSGIRequest:
    http_method: str = ""
    path: str = ""
    headers: List[Tuple[str, str]] = field(default_factory=lambda: [])
    body: BytesIO = BytesIO()

	# build the environ dict from the accumulated request state
	# (i.e. translate HTTP to WSGI)
    def to_environ(self):
        path_parts = self.path.split("?")
        headers_dict = {k: v for k, v in self.headers}
        environ = {
            "REQUEST_METHOD": self.http_method,
            "PATH_INFO": path_parts[0],
            "QUERY_STRING": path_parts[1] if len(path_parts) > 1 else "",
            "SERVER_NAME": "127.0.0.1",
            "SERVER_PORT": "5000",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_TYPE": headers_dict.get("Content-Type", ""),
            "CONTENT_LENGTH": headers_dict.get("Content-Length", ""),
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": self.body,
            "wsgi.errors": BytesIO(),
            "wsgi.multithread": True,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            **{f"HTTP_{name}": value for name, value in self.headers},
        }
        return environ


@dataclass
class WSGIResponse:
    status: str = ""
    headers: List[Tuple[str, str]] = field(default_factory=lambda: [])
    body: BytesIO = BytesIO()
    is_sent: bool = False

	# we will register this function as the application start_response calback
    def start_response(self, status: str, headers: List[Tuple[str, str]], exc_info=None):
        print("Start response with", status, headers)
        self.status = status
        self.headers = headers

	# create a valid HTTP response from the accumulated response state
	# (i.e. translate WSGI to HTTP)
    def to_http(self):
        self.is_sent = True
        return make_response(self.status, self.headers, self.body)

# WSGI Specific


def serve_forever(host: str, port: int):
    server_socket = socket.socket()
    server_socket.bind((host, port))
    server_socket.listen(1)

    while True:
        client_socket, address = server_socket.accept()
        print(f"Socket established with {address}.")
        session = WSGISession(client_socket, address)
        t = threading.Thread(target=session.run)
        t.start()


if __name__ == "__main__":
    os.system("clear")
    print(f"\nServing web content at 0.0.0.0:5000\n")
    serve_forever("0.0.0.0", 5000)
