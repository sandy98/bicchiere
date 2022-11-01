#!/usr/bin/env python3
# -*- coding; utf-8  -*-

"""
ASGI config for websocket_app project.
It exposes the ASGI callable as a module-level variable named ``application``.
"""

import os

#from django.core.asgi import get_asgi_application
from websocket_response import websocket_application
from http_response import http_application

async def application(scope, receive, send):
    if scope['type'] == 'http':
        print("Handling HTTP request with http app.")
        await http_application(scope, receive, send)
    elif scope['type'] == 'websocket':
        # We'll handle Websocket connections here
        print("Handling WEBSOCKET request with own websocket app.")
        await websocket_application(scope, receive, send)
    else:
        raise NotImplementedError(f"Unknown scope type {scope['type']}")


def main():
    from bicchiere import run
    os.system("clear")
    print("Echo ASGI Server listening at port 8087")
    server = os.sys.argv[1] if len(os.sys.argv) > 1 else "uvicorn"
    run(app=application, server_name=server, port=8087)

if __name__ == '__main__':
    main()

