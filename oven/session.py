# -*- coding: utf-8 -*-

from uuid import uuid4
import json
import os
import hmac, hashlib

class Session(dict):
    """Session handling class"""

    @staticmethod
    def encrypt(secret, text = uuid4().hex):
        hmac2 = hmac.new(key = text.encode(), digestmod = hashlib.sha256)
        hmac2.update(bytes(secret, encoding = "utf-8"))
        return hmac2.hexdigest()

    def __init__(self, secret = "20181209" , **kw):
        self.update(**kw)
        self.set_secret(secret)

    def set_secret(self, secret):
        self._secret = secret
        self.set_sid()

    def set_sid(self):
        self.sid = Session.encrypt(secret = self._secret)
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
        if __name.startswith('_') is False:
            return self.__setitem__(__name, __value)  
        else:
            super().__setattr__(__name, __value)
            return ""

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
        #d = dict()
        #d[self.sid] = self
        #j = json.dumps(d)
        #print(f"Saving {d}")
        return json.dumps(self)

    def load(self) -> str:
        return self.sid

    def get_store_dir(self) -> str:
        #store_dir = os.path.join(os.getcwd(), Bicchiere.config['session_directory'])
        store_dir = os.path.join(os.getcwd(), 'bicchiere_sessions')
        if os.path.exists(store_dir) is False:
            os.mkdir(store_dir)
        return store_dir

        

    
