# -*- coding: utf-8 -*-

#import activate

from uuid import uuid4
import json
import os
import hmac
import hashlib
import sqlite3


# Session handling support classes

class SuperDict(dict):
    def __getattr__(self, attr):
        return super().get(attr)
 
    def __setattr__(self, attr, val):
        self.__setitem__(attr, val)

    def __delattr__(self, attr):
        if self.get(attr):
            self.__delitem__(attr)

    def __getitem__(self, key):
        return super().get(key)

    def __delitem__(self, key):
        if super().get(key):
            super().__delitem__(key)

    def __repr__(self) -> str:
        return json.dumps(self)

    def pop(self, __name: str):
        value = super().get(__name)
        if value:
            super().__delitem__(__name)
            return value
        else:
            return None


class Session(SuperDict):
    """Session handling base class"""

    secret = None

    @classmethod
    def encrypt(cls, text=uuid4().hex):
        if not cls.secret:
            #raise ValueError(
            #    "Encryption can't be performed because secret word hasn't been set")
            cls.secret = uuid4().hex
        hmac2 = hmac.new(key=text.encode(), digestmod=hashlib.sha256)
        hmac2.update(bytes(cls.secret, encoding="utf-8"))
        return hmac2.hexdigest()

    def __init__(self, sid=None, **kw):
        if sid:
            if len(sid) < 32:
                raise KeyError("Wrong SID format")
            self.sid = sid
            self.load()
        else:
            self.set_sid()
        if kw:
            super().update(**kw)
            self.save()

    def __del__(self):
        "Tries to save session prior to deletion"
        try:
            self.save()
        except:
            pass

    def set_sid(self):
        self.sid = self.encrypt()
        #self.save()

    def load(self) -> str:
        return str(self)

    def save(self) -> str:
        return str(self)

    def get_store_dir(self) -> str:
        store_dir = os.path.join(os.getcwd(), 'bicchiere_sessions')
        if os.path.exists(store_dir) is False:
            os.mkdir(store_dir)
        return store_dir

    def get_file(self):
        if not self.sid:
            return ""
        return os.path.join(self.get_store_dir(), self.sid)

    def __setitem__(self, __k: str, __v) -> str:
        super().__setitem__(__k, __v)
    #     if __k == "sid":
    #         return json.dumps(self)
        if __k == "sid":
            return __v
        else:
            return self.save()

    def __delitem__(self, __k: str) -> str:
        if __k == "sid":
            return
        super().__delitem__(__k)
        return self.save()



class FileSession(Session):
    """File system based session handler class"""

    def load(self) -> str:
        file = self.get_file()
        if os.path.exists(file):
            fp = open(file, "rt", encoding="utf-8")
            old_self = json.load(fp)
            #for k in self:
            #    if not k == "sid":
            #        del self[k] 
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


class SqliteSession(Session):
    "Stores sessions in SQLite database"

    def get_file(self):
        return os.path.join(self.get_store_dir(), "bicchiere_sessions.sqlite")

    def create_db(self):
        file = self.get_file()
        conn = sqlite3.connect(file)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS sessions(sid TEXT PRIMARY KEY, data TEXT);")
            conn.commit()
        except Exception as exc:
            print(
                f"Error creating table 'sessions' due to: {str(exc)}\nQuitting...")
            os.sys.exit(1)
        finally:
            cursor.close()
            conn.close()

    def sess_exists(self) -> bool:
        file = self.get_file()
        if os.path.exists(file) is False:
            return False
        conn = sqlite3.connect(file)
        cursor = conn.cursor()
        result = False
        try:
            cursor.execute(
                "select count(*) from sessions where sid = ?;", (self.sid, ))
            result = not not cursor.fetchone()[0]
        except Exception as exc:
            print(f"Exception '{exc.__class__.__name__}': {repr(exc)}")
        finally:
            cursor.close()
            conn.close()
        return result

    def load(self) -> str:
        file = self.get_file()
        if os.path.exists(file):
            if self.sess_exists():
                conn = sqlite3.connect(file)
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "select data from sessions where sid = ?;", (self.sid, ))
                    data = cursor.fetchone()[0]
                    #for k in self:
                    #    if not k == "sid":
                    #        del self[k] 
                    old_self = json.loads(data)
                    for k in old_self:
                        self[k] = old_self[k]
                except Exception as exc:
                    print(f"Exception '{exc.__class__.__name__}': {repr(exc)}")
                finally:
                    cursor.close()
                    conn.close()
        else:
            self.create_db()
            self.save()

        return json.dumps(self)

    def save(self) -> str:
        file = self.get_file()
        if os.path.exists(file) is False:
            self.create_db()
        conn = sqlite3.connect(file)
        cursor = conn.cursor()
        try:
            if self.sess_exists():
                cursor.execute(
                    "update sessions set data = ? where sid = ?;", (json.dumps(self), self.sid))
            else:
                cursor.execute(
                    "insert into sessions (sid, data) values (?, ?);", (self.sid, json.dumps(self)))
            conn.commit()
        except Exception as exc:
            print(f"Exception '{exc.__class__.__name__}': {repr(exc)}")
        finally:
            cursor.close()
            conn.close()
        return json.dumps(self)

# End of session handling support classes



def main():
    os.system("clear")

    FileSession.secret = "20181209"

    s = FileSession(team="River Plate")
    s.answer = 42
    s.user = dict(name="sandy", age=68)
    print("\n", s, "\n")
    del s.answer
    print("\n", s, "\n")
    print("\n", s.pop("user"), "\n")
    print("\n", s, "\n")
    s.answer = 42
    s["user"] = dict(name="Domingo Ernesto Savoretti",
                     username="sandy", age=68)
    print("\n", s, "\n")


    s2 = FileSession(s.sid, foe="Flamengo")

    del s

    s = None

    print("\n", s2, "\n")


if __name__ == "__main__":
    main()
