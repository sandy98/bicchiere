#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio, os

class EchoProtocol(asyncio.Protocol):

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self.transport.write(data)


async def main(host, port):
    os.system("clear")
    print(f"\nEchoProtocol server running at {host}:{port}.\n")
    loop = asyncio.get_running_loop()
    server = await loop.create_server(EchoProtocol, host, port)
    await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main('0.0.0.0', 5000))

