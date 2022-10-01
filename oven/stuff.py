#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

def main():
    os.system("clear")
    print()
    print(f"os.getcwd(): {os.getcwd()}")
    print(f"__name__: {__name__}")
    print(f"__file__: {__file__}")
    print(f"os.path.abspath(__file__): {os.path.abspath(__file__)}")
    print(f"os.path.split(__file__): {repr(os.path.split(__file__))}")
    print(f"os.path.split(os.path.abspath(__file__)): {repr(os.path.split(os.path.abspath(__file__)))}")
    print()

if __name__ == '__main__':
    main()


