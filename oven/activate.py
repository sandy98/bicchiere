import os

atp_path = './bin/activate_this.py'
if os.path.exists(atp_path):
    print('Activating virtual environment.')
    exec(open(atp_path).read(), dict(__file__ = atp_path))
    print('Virtual environment activated.')
else:
    print("No virtual environment.")
