#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import socket


async def handle_socket(client_socket):
    loop = asyncio.get_event_loop()
    while True:
        data = await loop.sock_recv(client_socket, 1024) # non blocking
        print(f"Received {data}")
        if data == b"":
            break
        client_socket.send(data) # blocking
    client_socket.close()


async def serve_forever(host, port):
    server_socket = socket.socket()
    server_socket.bind((socket.gethostbyname(host), int(port)))
    server_socket.listen(1)
    server_socket.setblocking(False)

    loop = asyncio.get_event_loop()
    while True:
            client_socket, address = await loop.sock_accept(server_socket) # non blocking
            print(f"Socket established with {address}.")
            loop.create_task(handle_socket(client_socket))

def main():
    import os, sys
    os.system("clear")
    argv = sys.argv[1:]
    if len(argv) < 2:
        print(f"Usage: {sys.argv[0]} host port\n")
        sys.exit()
    host, port = argv[:2]
    print(f"TCP Echo Server listening at {socket.gethostbyname(host)}:{port}")
    try:
        asyncio.run(serve_forever(host, port))
    except KeyboardInterrupt as ki:
        print("\nTCP Echo Server quitting due to KeyboardInterrupt\n")
        #server_socket.close()
        del ki
        sys.exit(0)
    except Exception as exc:
        print(f"\nTCP Echo Server quitting due to {repr(exc)}\n")
        #server_socket.close()
        del exc
        sys.exit(-1)

if __name__ == '__main__':
    main()