#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def main():
    from bicchiere import Bicchiere
    major, minor, version = Bicchiere.__version__
    print(f"{major} {minor} {version}")
    return major, minor, version

if __name__ == '__main__':
    main()

    