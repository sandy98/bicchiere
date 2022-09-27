#!/usr/bin/env python
# -*- coding: utf-8 -*-

from uuid import uuid4


class EventArg:
    "Simple class for passing packed event arguments to handlers"

    __slots__ = ["target", "type", "data"]

    def __init__(self, target = None, type = "change", data = None):
        self.target = target
        self.type = type
        self.data = data

class Event:
    """
    Class to manage event handlers and emit events on behalf of their source (target)
    Not meant to be used as a mixin, but to be included in a 'has a' relationship.
    """
    def __init__(self, event_target, event_type: str):
        self.event_target = event_target
        self.event_type = event_type
        self.event_handlers = []
        self.cancel_handlers = []

    def subscribe(self, handler):
        if not callable(handler):
            raise ArgumentError("Event handler must be a callable object")
        fid = uuid4().hex
        handler.fid = fid
        def off():
            for index, handler in enumerate(self.event_handlers):
                if handler.fid == fid:
                    return self.event_handlers.pop(index)
            return None

        off.fid = fid
        self.event_handlers.append(handler)
        self.cancel_handlers.append(off)
        return off

    def unsubscribe(self, fid: str = ""):
        if not fid:
            self.event_handlers = []
            self.cancel_handlers = []
            return None
        for index, cancel_handler in enumerate(self.cancel_handlers):
            if cancel_handler.fid == fid:
                event_handler = cancel_handler()
                self.cancel_handlers.pop(index)
                return event_handler
        return None

    def __iadd__(self, handler):
        self.subscribe(handler)
        return self

    def __isub__(self, fid):
        self.unsubscribe(fid)
        return self

    def emit(self, data = None):
        arg = EventArg(target = self.event_target, type = self.event_type, data = data)
        for handler in self.event_handlers:
            handler(arg)


