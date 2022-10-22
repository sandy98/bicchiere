#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio, os, http, socket, threading
from typing import Callable, Any, List, Tuple
#from httptools import HttpRequestParser

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
        self.response_sent = False
        # self is now the protocol for the parser to interact with
        self.parser = HttpRequestParser(self)

    def run(self):
        while True:
            if self.response_sent:
                break
            data = self.client_socket.recv(1024)
            print(f"Received {data}")
            self.parser.feed_data(data)
        self.client_socket.close()
        print(f"Socket with {self.address} closed.")

    def send_response(self):
        body = b"""
            <!DOCTYPE html>
            <html lang="it">
            <head><title>Hello Page</title></head>
            <body style="font-family: Helvetica, Arial, sans-serif;">
                <h1 style="text-align: center; color: steelblue;">Hello World!</h1>
            </body>
            </html>
            """
        response = make_response(status_code=200, headers=[], body=body)
        self.client_socket.send(response)
        print("Response sent.")
        self.response_sent = True

    # parser callbacks
    def on_url(self, url: bytes):
        print(f"Received url: {url}")
        self.http_method = self.parser.http_method.decode("utf-8")
        self.url = url.decode("utf-8")
        self.headers = []

    def on_header(self, name: bytes, value: bytes):
        print(f"Received header: ({name}, {value})")
        self.headers.append((name, value))

    def on_body(self, body: bytes):
        print(f"Received body: {body}")

    def on_message_complete(self):
        print("Received request completely.")
        self.send_response()


def create_status_line(status_code: int = 200):
    code = str(status_code).encode()
    code_phrase = http.HTTPStatus(status_code).phrase.encode()
    return b"HTTP/1.1 " + code + b" " + code_phrase + b"\r\n"



def format_headers(headers: List[Tuple[bytes, bytes]]):
    return b"".join([(key + b": " + value + b"\r\n") for key, value in headers])


def make_response(status_code: int = 200, headers: List[Tuple[bytes, bytes]] = None, body: bytes = b""):
    if headers is None:
        headers = []
    if body:
        # if you add a body you must always send a header that informs
        # about the number of bytes to expect in the body
        headers.append((b"Content-Length", str(len(body)).encode("utf-8")))
    content = [create_status_line(status_code), format_headers(headers), b"\r\n" if body else b"", body, b"\r\n", b""]
    return b"".join(content)



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
