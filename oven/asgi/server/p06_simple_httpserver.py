#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio, os, http, socket, threading
from typing import Callable, Any, List, Tuple
from httptools import HttpRequestParser

class HttpRequestParserProtocol:
    def __init__(self, send_response: Callable):
        # we hand in and save a callback to be triggered once
        # we have received the entire request and can send a response
        self.send_response = send_response

    # parser callbacks
    # gets called once the start line is successfully parsed
    def on_url(self, url: Any):
        print(f"Received url: {url}")
        self.headers = []

    # gets called on every header that is read from the request
    def on_header(self, name: bytes, value: bytes):
        print(f"Received header: ({name}, {value})")
        self.headers.append((name, value))

    # gets called continously while reading chunks of the body
    def on_body(self, body: bytes):
        print(f"Received body: {body}")

    # gets called once the request was fully received and parsed
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

class HttpSession:
    def __init__(self, client_socket, address):
        self.client_socket = client_socket
        self.address = address
        self.response_sent = False
        protocol = HttpRequestParserProtocol(self.send_response)
        self.parser = HttpRequestParser(protocol)

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
        body = b"<html><head><title>Hello Page</title></head><body><h2>Hello World!!</h2></body></html>"
        response = make_response(status_code=200, headers=[(b"Content-Type", b"text/html; charset=utf-8")], body=body)
        self.client_socket.send(response)
        print("Response sent.")
        self.response_sent = True


def serve_forever(host: str, port: int):
    server_socket = socket.socket()
    server_socket.bind((host, port))
    server_socket.listen(1)

    while True:
        client_socket, address = server_socket.accept()
        print(f"Socket established with {address}.")
        session = HttpSession(client_socket, address)
        t = threading.Thread(target=session.run)
        t.start()


if __name__ == "__main__":
    os.system("clear")
    print(f"\nServing web content at 0.0.0.0:5000\n")
    serve_forever("0.0.0.0", 5000)
