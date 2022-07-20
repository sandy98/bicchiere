#!/usr/bin/env python3
# -*- coding  utf-8 -*-

import os

activate_this = os.path.join(os.path.abspath('.'), 'bin', 'activate_this.py')

try:
    print("Activating virtualenv...")
    exec(open(activate_this).read(), dict(__file__=activate_this))
    print("Virtual environment activated.")
except Exception as e:
    print("Virtual environment activation failed. Error: {0}".format(str(e)))
    pass

os.sys.path.insert(0, os.path.abspath('..'))
os.sys.path.insert(0, os.path.abspath('.'))
#import gunicorn
#from bicchiere import application

def main():
    #os.system("clear")
    os.system("""gunicorn --bind '0.0.0.0:8086' --workers 4 bicchiere:application""")

if __name__ == "__main__":
     main()

