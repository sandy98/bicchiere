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

def handle_socket(client_socket, address: Tuple[str, int]):
    # keep track of whether we have already sent a response
    response_sent = False

    # nested function for closure on local variables
    # that's the callback we'll trigger in the parser
    # once we should send the response
    def send_response():
        # a dummy response for now
        body = b"<html><body><h1>Hello World!!!</h1></body></html>"
        response = make_response(status_code=200, headers=[(b"Content-Type", b"text/html; charset=utf-8")], body=body)
        client_socket.send(response)
        print("Response sent.")
        nonlocal response_sent
        response_sent = True

    # instantiate the protocol and parser
    # hand in the send_response callback to get triggered by the parser
    protocol = HttpRequestParserProtocol(send_response)
    parser = HttpRequestParser(protocol)

    while True:
        # have we already replied? then close the socket
        if response_sent:
            break
        data = client_socket.recv(1024)
        print(f"Received {data}")
        # continuously feed incoming request data into the parser
        parser.feed_data(data)
    client_socket.close()
    print(f"Socket with {address} closed.")


def serve_forever(host: str, port: int):
    server_socket = socket.socket()
    server_socket.bind((host, port))
    server_socket.listen(1)

    while True:
        client_socket, address = server_socket.accept()
        print(f"Socket established with {address}.")
        t = threading.Thread(
            target=handle_socket, args=(client_socket, address)
        )
        t.start()


if __name__ == "__main__":
    os.system("clear")
    print(f"\nServing web content at 0.0.0.0:5000\n")
    serve_forever("0.0.0.0", 5000)
