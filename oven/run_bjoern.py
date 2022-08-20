#!/usr/bin/env python3
#-*- coding: UTF-8 #-*-

import os, logging, socket

activate_this = os.path.join(os.path.abspath('.'), 'bin', 'activate_this.py')

try:
    print("Activating virtualenv...")
    exec(open(activate_this).read(), dict(__file__=activate_this))
    print("Virtual environment activated.")
except Exception as e:
    print("Virtual environment activation failed. Error: {0}".format(str(e)))
    
import bjoern

#from simple_wsgi import application
os.sys.path.insert(0, os.path.abspath('.'))
os.sys.path.insert(0, os.path.abspath('..'))
from bicchiere import application

def main():
    print("Beginning Bjoern Web Server running WSGI App")
    SOCK = '/app.sock'
    if os.path.exists(SOCK):
        print("Tratando de borrar un socket unix preexistente...")
        try:
            os.unlink(SOCK)
        except Exception as e:
            print("No se pudo borrar el socket preexistente, por lo cual se cierra el sistema.")
            os.sys.exit(1)
    try:
        ###sock = socket.socket(socket.AF_UNIX)
        ###sock.bind(SOCK)
        ###sock.listen(1024)
        ###os.chmod(SOCK, 0o666)
        ###print(f"Socket creado para la app WSGI en {sock.getsockname()}")
        bjoern.run(application, host = '0.0.0.0', port = 8086)
        #bjoern.run(application, f"unix:{sock.getsockname()}")
        #bjoern.server_run(sock, application)
    except KeyboardInterrupt:
        print("Saliendo por interrupción del teclado. (CTRL-C)")
        pass
    except Exception as exc:
        print("Saliendo por otro error: {0}".format(str(exc)))
        pass

    finally:
        try: 
            pass
            ###print("Eliminando el socket unix {0}".format(sock.getsockname()))
            ###os.unlink(sock.getsockname())
        except Exception:
            pass
        finally:
            print("Server stopped...")


if __name__ == '__main__':
    main()


