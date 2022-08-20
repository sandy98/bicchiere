# -*- coding: utf-8 -*-

class Chameleon(dict):
    def __init__(self, **kw):
        self.update(**kw)

    def __getattribute__(self, __name: str):
        if __name in self:
            return self[__name]
        elif __name == "save":
            return object.__getattribute__(self, "save")
        elif hasattr(dict, __name):
            return dict.__getattribute__(self, __name)
        else:
            raise AttributeError(f"{self.__class__.__name__} object has no attribute '{__name}'")

    def __setattr__(self, __name: str, __value) -> None:
        self[__name] = __value

    def __delattr__(self, __name: str) -> None:
        #return super().__delattr__(__name)
        if self.get(__name):
            del self[__name]

    def save(self):
        print(f"Saving {dict(self)}")

