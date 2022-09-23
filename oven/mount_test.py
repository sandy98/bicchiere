#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import activate
from bicchiere import Bicchiere
from bottle import Bottle

ipyregex = r" \[\d+\]:\s*|\s+\.+:\s+)"

acasa = Bicchiere("Casa")
acocina = Bicchiere("Cocina")
acomedor = Bicchiere("Comedor")
abottiglia = Bottle("Bottiglia")

acasa.config.debug = True

#acasa.mount("/casa", acasa)  # app can't be mounted on itself
acasa.mount("/cocina", acocina)
acasa.mount("/comedor", acomedor)
acasa.mount("/bottiglia", abottiglia)

@acasa.get("/")
def casa():
    return "Esta es la casa."


@acocina.get("/")
def cocina():
    return "Esta es la cocina."

@acocina.get("/show")
def cocinashow():
    return "<h1>Vi mostro la cucina</h1>"


def cocina():
    return "<h1>Vi mostro la cucina</h1>"

@acomedor.get("/")
def comedor():
    return "Este es el comedor."

@abottiglia.get("/")
def bottiglia():
    return "C'e una bottiglia cui."

@abottiglia.get("/show")
def bottigliashow():
    return """
        <h1 style="text-align: center; color: red;">
           C'e una bottiglia di Campari!!
        </h1>
    """



def main():
    acasa.run()


if __name__ == '__main__':
    main()
