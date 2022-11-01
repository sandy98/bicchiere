# -*- coding: utf-8 -*-

async def websocket_application(_, receive, send):
    while True:
        event = await receive()

        if event['type'] == 'websocket.connect':
            print("Accepting incoming websocket connection request.")
            await send({
                'type': 'websocket.accept'
            })
        elif event['type'] == 'websocket.disconnect':
            print("Handling disconnect...")
            break
            #await send({
            #    'type': 'websocket.close',
            #    'code': 1000
            #})
        elif event['type'] == 'websocket.receive':
            print(f"Websocket received this text: {event['text'] if event.get('text') else event['bytes']}")
            if event.get('text') == 'ping' or event.get('bytes') == b'ping':
                await send({
                    'type': 'websocket.send',
                    'text': 'PONG'
                })
            else:
                await send({
                    'type': 'websocket.send',
                    'text': event.get('text') or event.get('bytes').decode()
                })
        else:
            print(f"Received event type: {event.get('type')} (Don't know what to do with that...)")
            #await send({
            #    'type': 'websocket.accept'
            #})
