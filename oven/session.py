# -*- coding: utf-8 -*-

from uuid import uuid4
import json
import os

class Session(dict):
    def __init__(self, sid = uuid4().hex, **kw):
        self.sid = sid
        self.update(**kw)
        self.save()

    def __getattr__(self, __name: str):
        if __name in self:
            return self[__name]
        else:
            raise AttributeError(f"getattr informs that {self.__class__.__name__} object has no attribute '{__name}'")

    def __getattribute__(self, __name: str):
        return super().__getattribute__(__name)

    def __setitem__(self, __k: str, __v) -> str:
        super().__setitem__(__k, __v)
        return self.save()

    def __delitem__(self, __k: str) -> str:
        super().__delitem__(__k)
        return self.save()

    def __setattr__(self, __name: str, __value) -> str:
        return self.__setitem__(__name, __value)

    def __delattr__(self, __name: str) -> str:
        if self.get(__name):
            return self.__delitem__(__name)
        else:
            return ""

    def pop(self, __name: str) -> str:
        value = self.get(__name)
        if value:
            self.__delitem__(__name)
            return value
        else:
            return ""

    def save(self) -> str:
        d = dict()
        d[self.sid] = self
        j = json.dumps(d)
        #print(f"Saving {d}")
        return j

    def load(self) -> str:
        return self.sid

    def get_store_dir(self) -> str:
        #return os.path.join(os.getcwd(), Bicchiere.config['session_directory'])
        return os.path.join(os.getcwd(), 'bicchiere_sessions')


    
