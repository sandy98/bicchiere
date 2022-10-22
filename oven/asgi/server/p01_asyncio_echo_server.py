#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio, os

async def echo_server(reader, writer):
    while True:
        data = await reader.read(4096) # Max number of bytes to read
        if not data:
            break
        writer.write(data)
        await writer.drain()
    writer.close()

async def main(host, port):
    os.system("clear")
    server = await asyncio.start_server(echo_server, host, port)
    print(f"Echo server running at {host}:{port}.")
    await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main('0.0.0.0', 5000))

