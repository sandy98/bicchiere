# -*- coding: utf-8 -*-

from fileinput import close
from uuid import uuid4
import json
import os
import hmac, hashlib

class Session(dict):
    """Session handling base class"""

    secret = None

    @classmethod
    def encrypt(cls, text = uuid4().hex):
        if not cls.secret:
            raise ValueError("Encryption can't be performed because secret word hasn't been set")
        hmac2 = hmac.new(key = text.encode(), digestmod = hashlib.sha256)
        hmac2.update(bytes(cls.secret, encoding = "utf-8"))
        return hmac2.hexdigest()

    def __init__(self, sid = None , **kw):
        if sid:
            self.sid = sid
            self.load()
        else:
            self.update(**kw)
            self.set_sid()

    def set_sid(self):
        self.sid = self.encrypt()
        self.save()

    def load(self) -> str:
        return self.sid

    def save(self) -> str:
        #d = dict()
        #d[self.sid] = self
        #j = json.dumps(d)
        #print(f"Saving {d}")
        return json.dumps(self)

    def get_store_dir(self) -> str:
        #store_dir = os.path.join(os.getcwd(), Bicchiere.config['session_directory'])
        store_dir = os.path.join(os.getcwd(), 'bicchiere_sessions')
        if os.path.exists(store_dir) is False:
            os.mkdir(store_dir)
        return store_dir

    def get_file(self):
        if not self.sid:
            return ""
        return os.path.join(self.get_store_dir(), self.sid)

    def pop(self, __name: str) -> str:
        value = self.get(__name)
        if value:
            self.__delitem__(__name)
            return value
        else:
            return ""

    def __getattr__(self, __name: str):
        if __name in self:
            return self[__name]
        else:
            raise AttributeError(f"getattr informs that {self.__class__.__name__} object has no attribute '{__name}'")

    #def __getattribute__(self, __name: str):
    #    return super().__getattribute__(__name)

    def __setitem__(self, __k: str, __v) -> str:
        super().__setitem__(__k, __v)
        if __k == "sid":
            return json.dumps(self)
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


class FileSession(Session):
    """File system based session handler class"""

    def load(self) -> str:
        file = self.get_file()
        if os.path.exists(file):
            fp = open(file, "rt", encoding="utf-8")
            old_self = json.load(fp)
            fp.close()
            for k in old_self:
                self[k] = old_self[k]
        return json.dumps(self)            

    def save(self) -> str:
        file = self.get_file()
        fp = open(file, "wt", encoding="utf-8")
        json.dump(self, fp)
        fp.close()
        return json.dumps(self)


def main():
    os.system("clear")

    FileSession.secret = "20181209"

    s = FileSession(team = "River Plate")
    s.answer = 42
    s.user = dict(name = "sandy", age = 68)
    print("\n", s, "\n")
    del s.answer
    print("\n", s, "\n")
    print("\n", s.pop("user"), "\n")
    print("\n", s, "\n")
    s.answer = 42
    s["user"] = dict(name = "Domingo Ernesto Savoretti", username = "sandy", age = 68)
    print("\n", s, "\n")

    s2 = FileSession('9a3163d6079203ca73584e8e6d68103d2e9065d430194f42321ac6481f13e589', foe = "Flamengo")

    print("\n", s2, "\n")


if __name__ == "__main__":
    main()
