# -*- coding: utf-8 -*-

from uuid import uuid4
import json

class Session(dict):
    def __init__(self, sid = uuid4().hex, **kw):
        self.sid = sid
        self.update(**kw)

    def __getattr__(self, __name: str):
        if __name in self:
            return self[__name]
        else:
            raise AttributeError(f"getattr informs that {self.__class__.__name__} object has no attribute '{__name}'")

    def __getattribute__(self, __name: str):
        return super().__getattribute__(__name)

    def __setitem__(self, __k: str, __v) -> None:
        super().__setitem__(__k, __v)
        self.save()

    def __setattr__(self, __name: str, __value) -> None:
        self.__setitem__(__name, __value)

    def __delattr__(self, __name: str) -> None:
        #return super().__delattr__(__name)
        if self.get(__name):
            del self[__name]
            self.save()

    def save(self) -> str:
        d = dict()
        d[self.sid] = self
        j = json.dumps(d)
        print(f"Saving {d}")
        return j
