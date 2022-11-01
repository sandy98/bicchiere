#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.client import HTTPException
import os, sys
import webbrowser
from xml.dom import NotSupportedErr
if sys.version_info < (3, 6):
    raise NotSupportedErr("This software only runs within Python version 3.6 or higher.")

# Following 3 for ASGIServer
from dataclasses import dataclass, field
from typing import List, Tuple, Any, Callable, Dict, Optional, overload
import http

# These for sync2async
import asyncio.coroutines
import contextvars
import functools
import warnings
import weakref
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import Executor
import queue
import string

# Till here

import logging
import inspect
import struct
import mimetypes
import random
import re
import json
import cgi
import threading
import base64
import sqlite3
import hmac
import hashlib
import asyncio
import urllib.request
import wsgiref.util
import zlib

from tempfile import TemporaryFile, SpooledTemporaryFile
#from email import charset
from argparse import ArgumentTypeError
from io import StringIO, BytesIO
from subprocess import Popen, PIPE, STDOUT, run as runsub
from datetime import datetime  # , timedelta
from time import time as timestamp, sleep
import time as o_time
from functools import reduce, wraps, partial
from http.cookies import SimpleCookie  # , Morsel
from socketserver import ThreadingMixIn
import socket
from socket import error as socket_error  # , socket as Socket
from wsgiref.headers import Headers
from wsgiref.simple_server import make_server, ServerHandler, WSGIRequestHandler, WSGIServer
from wsgiref.simple_server import demo_app as simple_demo_app
from uuid import uuid4
from urllib.parse import parse_qsl
from mimetypes import guess_type
import wsgiref.util
#from xmlrpc.client import Boolean

# Prepares logging

logger = logging.getLogger("Bicchiere")
logging.basicConfig()

# End of logging part

# Part I - The sync world

# Websocket auxiliary classes and stuff

_is_hop_by_hop = wsgiref.util.is_hop_by_hop
wsgiref.util.is_hop_by_hop = lambda x: False


class EventArg:
    "Simple class for passing packed event arguments to handlers"

    __slots__ = ["target", "type", "data"]

    def __init__(self, target=None, type="change", data=None):
        self.target = target
        self.type = type
        self.data = data


class Event:
    """
    Class to manage event handlers and emit events on behalf of their source (target)
    Not meant to be used as a mixin, but to be included in a 'has a' relationship.
    Mainly, to implement 'onxxx' handlers.
    """

    def __init__(self, event_target, event_type: str):
        self.event_target = event_target
        self.event_type = event_type
        self.event_handlers = []
        self.cancel_handlers = []

    def subscribe(self, handler):
        if not callable(handler):
            raise ArgumentTypeError("Event handler must be a callable object")
        fid = uuid4().hex
        handler.fid = fid

        def off():
            for index, handler in enumerate(self.event_handlers):
                if handler.fid == fid:
                    return self.event_handlers.pop(index)
            return None

        off.fid = fid
        self.event_handlers.append(handler)
        self.cancel_handlers.append(off)
        return off

    def unsubscribe(self, fid: str = ""):
        if not fid:
            self.event_handlers = []
            self.cancel_handlers = []
            return None
        for index, cancel_handler in enumerate(self.cancel_handlers):
            if cancel_handler.fid == fid:
                event_handler = cancel_handler()
                self.cancel_handlers.pop(index)
                return event_handler
        return None

    def __iadd__(self, handler):
        self.subscribe(handler)
        return self

    def __isub__(self, fid):
        self.unsubscribe(fid)
        return self

    def emit(self, data=None):
        arg = EventArg(target=self.event_target,
                       type=self.event_type, data=data)
        for handler in self.event_handlers:
            handler(arg)


class BicchiereServerHandler(ServerHandler):
    http_version = "1.1"

    def _convert_string_type(self, value, title):
        if isinstance(value, str):
            return value
        raise AssertionError(
            "{0} must be of type str (got {1})".format(title, repr(value)))

    def start_response(self, status, headers, exc_info=None):
        if exc_info:
            try:
                if self.headers_sent:
                    raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])
            finally:
                exc_info = None
        elif self.headers is not None:
            raise AssertionError("Headers already set!")
        self.status = status
        self.headers = self.headers_class(headers)
        status = self._convert_string_type(status, "Status")
        assert len(status) >= 4, "Status must be at least 4 characters"
        assert status[:3].isdigit(), "Status message must begin w/3-digit code"
        assert status[3] == " ", "Status message must have a space after code"
        if __debug__:
            for name, val in headers:
                name = self._convert_string_type(name, "Header name")
                val = self._convert_string_type(val, "Header value")
        self.send_headers()
        return self.write


class BicchiereHandler(WSGIRequestHandler):
    def address_string(self):
        return self.client_address[0]

    def log_request(self, *args, **kw):
        try:
            if not getattr(self, "quit", False):
                return WSGIRequestHandler.log_request(self, *args, **kw)
        except:
            pass

    def get_app(self):
        return self.server.get_app()

    def handle(self):
        self.raw_requestline = self.rfile.readline(65537)
        if len(self.raw_requestline) > 65536:
            self.requestline = ""
            self.request_version = ""
            self.command = ""
            self.send_error(414)
            return
        if not self.parse_request():
            return
        handler = BicchiereServerHandler(
            self.rfile, self.wfile, self.get_stderr(), self.get_environ())
        handler.request_handler = self
        handler.run(self.get_app())


class SuperDict(dict):
    "Dictionary that makes no difference between items and attributes"

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
        return json.dumps(self, default=lambda x: repr(x))

    def pop(self, __name: str):
        value = super().get(__name)
        if value:
            super().__delitem__(__name)
            return value
        else:
            return None


class Stream:
    """Handler that encapsulates an input file descriptor together with an output file descriptor"""

    def __init__(self, inputstream, outputstream):
        self.input = inputstream
        self.output = outputstream
        self.buffer = []
        self.flush = self.output.flush if hasattr(
            self.output, "flush") else lambda: None

    def read(self, size=-1):
        try:
            value = self.input.read(size)
        except Exception as exc:
            value = self.error(exc)
        finally:
            return value

    def write(self, buffer):
        try:
            value = self.output.write(buffer)
            self.flush()
        except Exception as exc:
            value = self.error(exc)
        finally:
            return value

    def close(self):
        try:
            self.input.close()
            self.output.close()
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        r = repr(exc)
        print(r)
        return r

    def __del__(self):
        try:
            self.close()
        except:
            pass


class WebSocketError(socket_error):
    """
    Base class for all websocket errors.
    """
    pass


class ProtocolError(WebSocketError):
    pass


class FrameTooLargeException(ProtocolError):
    """
    Raised if a frame is received that is too large.
    """


class WebSocket:
    """
    Base class for supporting websocket operations.
    """

    OPCODE_CONTINUATION = 0x00
    OPCODE_TEXT = 0x01
    OPCODE_BINARY = 0x02
    OPCODE_CLOSE = 0x08
    OPCODE_PING = 0x09
    OPCODE_PONG = 0x0A
    FIN_MASK = 0x80
    OPCODE_MASK = 0x0F
    MASK_MASK = 0x80
    LENGTH_MASK = 0x7F
    RSV0_MASK = 0x40
    RSV1_MASK = 0x20
    RSV2_MASK = 0x10
    HEADER_FLAG_MASK = RSV0_MASK | RSV1_MASK | RSV2_MASK

    # default messages
    MSG_SOCKET_DEAD = "Socket is dead"
    MSG_ALREADY_CLOSED = "Connection is already closed"
    MSG_CLOSED = "Connection closed"

    origin = None
    protocol = None
    version = None
    path = None
    logger = logging.getLogger("WebSocket")

    def __init__(self, environ, read, write, handler, do_compress):
        self.environ = environ
        self.closed = False
        self.write = write
        self.read = read
        self.handler = handler
        self.do_compress = do_compress
        self.origin = self.environ.get("HTTP_SEC_WEBSOCKET_ORIGIN") or self.environ.get("HTTP_ORIGIN")
        self.protocols = list(map(str.strip, self.environ.get("HTTP_SEC_WEBSOCKET_PROTOCOL", "").split(",")))
        self.version = int(self.environ.get("HTTP_SEC_WEBSOCKET_VERSION", "13").strip())
        self.path = self.environ.get("PATH_INFO", "/")
        if do_compress:
            self.compressor = zlib.compressobj(7, zlib.DEFLATED, -zlib.MAX_WBITS)
            self.decompressor = zlib.decompressobj(-zlib.MAX_WBITS)

        self.default_handler = self.logger.info

        self.onopen = Event(self, "open")
        self.onopen += partial(self.default_handler, "WebSocket Opened")
        self.onerror = Event(self, "error")
        self.onmessage = Event(self, "message")
        self.onclose = Event(self, "close")
        self.onping = Event(self, "ping")
        self.onpong = Event(self, "pong")

    def heartbeat(self):
        #dt = datetime.now()
        #sdate = dt.strftime("%Y-%m-%d %H:%M:%S").encode("utf-8")
        #self.send_frame(sdate, self.OPCODE_PING)
        self.send_frame(str(Bicchiere.millis()), self.OPCODE_PING)

    def __del__(self):
        try:
            self.close()
        except:
            # close() may fail if __init__ didn't complete
            pass

    def _decode_bytes(self, bytestring):
        if not bytestring:
            return ""
        try:
            return bytestring.decode("utf-8")
        except UnicodeDecodeError as e:
            self.logger.debug('UnicodeDecodeError')
            self.close(1007, str(e))
            raise

    def _encode_bytes(self, text):
        if not isinstance(text, str):
            text = str(text or "")
        return text.encode("utf-8")

    def _is_valid_close_code(self, code):
        # valid hybi close code?
        if (code < 1000 or 1004 <= code <= 1006 or 1012 <= code <= 1016
                or code ==
                # not sure about this one but the autobahn fuzzer requires it.
                1100
                or 2000 <= code <= 2999):
            return False
        return True

    def handle_close(self, payload):
        if not payload:
            self.close(1000, "")
            return
        if len(payload) < 2:
            raise ProtocolError("Invalid close frame: %s" % payload)
        code = struct.unpack("!H", payload[:2])[0]
        payload = payload[2:]
        if payload:
            payload.decode("utf-8")
        if not self._is_valid_close_code(code):
            raise ProtocolError("Invalid close code %s" % code)
        self.close(code, payload)
        self.onclose.emit(payload)

    def handle_ping(self, payload):
        self.send_frame(payload, self.OPCODE_PONG)
        self.onping.emit(payload)

    def handle_pong(self, payload):
        self.onpong.emit(payload)

    def mask_payload(self, mask, length, payload):
        payload = bytearray(payload)
        mask = bytearray(mask)
        for i in range(length):
            payload[i] ^= mask[i % 4]

        return payload

    def read_message(self):
        opcode = None
        message = bytearray()

        while True:
            data = self.read(2)

            if len(data) != 2:
                first_byte, second_byte = 0, 0

            else:
                first_byte, second_byte = struct.unpack("!BB", data)

            fin = first_byte & self.FIN_MASK
            f_opcode = first_byte & self.OPCODE_MASK
            flags = first_byte & self.HEADER_FLAG_MASK
            length = second_byte & self.LENGTH_MASK
            has_mask = second_byte & self.MASK_MASK == self.MASK_MASK

            if f_opcode > 0x07:
                if not fin:
                    raise ProtocolError(
                        "Received fragmented control frame: {0!r}".format(data))
                # Control frames MUST have a payload length of 125 bytes or less
                if length > 125:
                    raise FrameTooLargeException(
                        "Control frame cannot be larger than 125 bytes: {0!r}".format(data))

            if length == 126:
                # 16 bit length
                data = self.read(2)
                if len(data) != 2:
                    raise WebSocketError(
                        "Unexpected EOF while decoding header")
                length = struct.unpack("!H", data)[0]

            elif length == 127:
                # 64 bit length
                data = self.read(8)
                if len(data) != 8:
                    raise WebSocketError(
                        "Unexpected EOF while decoding header")
                length = struct.unpack("!Q", data)[0]

            if has_mask:
                mask = self.read(4)
                if len(mask) != 4:
                    raise WebSocketError(
                        "Unexpected EOF while decoding header")

            if self.do_compress and (flags & self.RSV0_MASK):
                flags &= ~self.RSV0_MASK
                compressed = True

            else:
                compressed = False

            if flags:
                raise ProtocolError(str(flags))

            if not length:
                payload = b""

            else:
                try:
                    payload = self.read(length)

                except socket.error:
                    payload = b""

                except Exception:
                    raise WebSocketError("Could not read payload")

                if len(payload) != length:
                    raise WebSocketError(
                        "Unexpected EOF reading frame payload")

                if has_mask:
                    payload = self.mask_payload(mask, length, payload)

                if compressed:
                    payload = b"".join((
                        self.decompressor.decompress(bytes(payload)),
                        self.decompressor.decompress(b"\0\0\xff\xff"),
                        self.decompressor.flush(),
                    ))

            if f_opcode in (self.OPCODE_TEXT, self.OPCODE_BINARY):
                # a new frame
                if opcode:
                    raise ProtocolError("The opcode in non-fin frame is "
                                        "expected to be zero, got "
                                        "{0!r}".format(f_opcode))

                opcode = f_opcode

            elif f_opcode == self.OPCODE_CONTINUATION:
                if not opcode:
                    raise ProtocolError("Unexpected frame with opcode=0")

            elif f_opcode == self.OPCODE_PING:
                self.handle_ping(payload)
                continue

            elif f_opcode == self.OPCODE_PONG:
                self.handle_pong(payload)
                continue

            elif f_opcode == self.OPCODE_CLOSE:
                print('opcode close')
                self.handle_close(payload)
                return

            else:
                raise ProtocolError("Unexpected opcode={0!r}".format(f_opcode))

            if opcode == self.OPCODE_TEXT:
                payload.decode("utf-8")

            message += payload

            if fin:
                break

        self.onmessage.emit(message)

        if opcode == self.OPCODE_TEXT:
            return self._decode_bytes(message)

        else:
            return message

    def receive(self):
        """
        Read and return a message from the stream. If `None` is returned, then
        the socket is considered closed/errored.
        """
        if self.closed:
            self.logger.debug('Receive closed')
            err_already_closed = WebSocketError(self.MSG_ALREADY_CLOSED)
            self.onerror.emit(err_already_closed)
            raise err_already_closed
            # return None
        try:
            return self.read_message()
        except UnicodeError as e:
            self.logger.debug('UnicodeDecodeError')
            self.close(1007, str(e).encode("utf-8"))
            self.onclose.emit(str(e).encode("utf-8"))
        except ProtocolError as e:
            self.logger.debug(f'Protocol err: {repr(e)}')
            self.close(1002, str(e).encode())
            self.onclose.emit(self.MSG_CLOSED)
        except socket.timeout as e:
            self.logger.debug('Socket timeout')
            self.close(message=str(e))
            self.onclose.emit(str(e))
        except socket.error as e:
            self.logger.debug(f'Spcket error: {repr(e)}')
            self.close(message=str(e))
            self.onclose.emit(self.MSG_CLOSED)

        return None

    def encode_header(self, fin, opcode, mask, length, flags):
        first_byte = opcode
        second_byte = 0
        extra = b""
        result = bytearray()

        if fin:
            first_byte |= self.FIN_MASK

        if flags & self.RSV0_MASK:
            first_byte |= self.RSV0_MASK

        if flags & self.RSV1_MASK:
            first_byte |= self.RSV1_MASK

        if flags & self.RSV2_MASK:
            first_byte |= self.RSV2_MASK

        if length < 126:
            second_byte += length

        elif length <= 0xFFFF:
            second_byte += 126
            extra = struct.pack("!H", length)

        elif length <= 0xFFFFFFFFFFFFFFFF:
            second_byte += 127
            extra = struct.pack("!Q", length)

        else:
            raise FrameTooLargeException

        if mask:
            second_byte |= self.MASK_MASK

        result.append(first_byte)
        result.append(second_byte)
        result.extend(extra)

        if mask:
            result.extend(mask)

        return result

    def send_frame(self, message, opcode, do_compress=False):
        if self.closed:
            self.logger.debug('Receive closed')
            self.onclose.emit(self.MSG_ALREADY_CLOSED)
            raise WebSocketError(self.MSG_ALREADY_CLOSED)

        if not message:
            return

        if opcode in (self.OPCODE_TEXT, self.OPCODE_PING):
            message = self._encode_bytes(message)

        elif opcode == self.OPCODE_BINARY:
            message = bytes(message)

        if do_compress and self.do_compress:
            message = self.compressor.compress(message)
            message += self.compressor.flush(zlib.Z_SYNC_FLUSH)

            if message.endswith(b"\x00\x00\xff\xff"):
                message = message[:-4]

            flags = self.RSV0_MASK

        else:
            flags = 0

        header = self.encode_header(True, opcode, b"", len(message), flags)

        try:
            self.write(bytes(header + message))

        except socket_error as e:
            raise WebSocketError(self.MSG_SOCKET_DEAD + " : " + str(e))

    def send(self, message, binary=None, do_compress=True):
        """
        Send a frame over the websocket with message as its payload
        """

        if binary is None:
            binary = not isinstance(message, str)

        opcode = self.OPCODE_BINARY if binary else self.OPCODE_TEXT

        try:
            self.send_frame(message, opcode, do_compress)

        except WebSocketError:
            self.logger.debug(
                f"Socket already closed: {repr(self.MSG_ALREADY_CLOSED)}")
            self.onclose.emit(self.MSG_SOCKET_DEAD)
            raise WebSocketError(self.MSG_SOCKET_DEAD)

    def close(self, code=1000, message=b""):
        """
        Close the websocket and connection, sending the specified code and
        message.  The underlying socket object is _not_ closed, that is the
        responsibility of the initiator.
        """
        print("close called")
        if self.closed:
            self.logger.debug('Receive closed')
            self.onclose.emit(self.MSG_ALREADY_CLOSED)

        try:
            message = self._encode_bytes(message)
            self.send_frame(struct.pack("!H%ds" % len(message), code, message),
                            opcode=self.OPCODE_CLOSE)

        except WebSocketError:
            self.logger.debug(
                "Failed to write closing frame -> closing socket")

        finally:
            self.logger.debug("Closed WebSocket")
            self.closed = True
            self.write = None
            self.read = None
            self.environ = None

# End of websocket auxiliary classes


# Threading server

class BicchiereServer(ThreadingMixIn, WSGIServer):
    """This class is identical to WSGIServer but uses threads to handle
    requests by using the ThreadingMixIn. This is useful to handle web
    browsers pre-opening sockets, on which Server would wait indefinitely.
    Credits for the idea to Kavindu Santhusa (@ksenginew)
    See https://github.com/ksenginew/WSocket
    """

    multithread = True
    daemon_threads = True


# Threading server

# Routing classes

class Route:
    "Utility class for routing requests"

    def __init__(self, pattern, func, param_types, methods=['GET']):
        self.pattern = pattern
        self.func = func
        self.param_types = param_types
        self.methods = methods
        self.args = {}

    def __call__(self):
        return (self.pattern, self.func, self.param_types, self.args, self.methods)

    def match(self, path):
        if not path:
            return None
        m = self.pattern.match(path)
        if m:
            kwargs = m.groupdict()
            self.args = {}
            for argname in kwargs:
                self.args[argname] = self.param_types[argname](kwargs[argname])
            return self
            # return m.groupdict(), self.func, self.methods, self.param_types
        return None

    def __str__(self):
        return f"""
               Pattern: {str(self.pattern)}
               Handler: {self.func.__name__}
               Parameter Types:  {self.param_types}
               Methods: {self.methods}
               Arguments: {self.args}
               """

# End of routing classes

# Templates related code


class CodeBuilder:
    """Build source code conveniently."""

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent

    def add_line(self, line):
        """Add a line of source to the code.
        Indentation and newline will be added for you, don't provide them.
        """
        self.code.extend([" " * self.indent_level, line, "\n"])

    INDENT_STEP = 4      # PEP8 says so!

    def indent(self):
        """Increase the current indent for following lines."""
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        """Decrease the current indent for following lines."""
        self.indent_level -= self.INDENT_STEP

    def add_section(self):
        """Add a section, a sub-CodeBuilder."""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        """Execute the code, and return a dict of globals it defines."""
        # A check that the caller really finished all the blocks they started.
        assert self.indent_level == 0
        # Get the Python source as a single string.
        python_source = str(self)
        # Execute the source, defining globals, and return them.
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace


class TemplateSyntaxError(BaseException):
    pass


class TemplateLight:

    test_tpl = """
        <h2> Hello, I am {{ user  }}. </h2>
        <p>These are my favourite teams, in no particular order.<p>
        <p>
          <ul>
            {% for team in teams %}
              <li> {{ team }} </li>
            {% endfor %}
          </ul>
        </p>
        """

    def __init__(self, text, **contexts):
        """Construct a TemplateLight with the given `text`.
        `contexts` are key-value pairs to use for future renderings.
        These are good for filters and global values.
        """
        self._template_text = text
        self.context = {}
        # for context in contexts:
        # self.context.update(context)
        self.context.update(contexts)
        self.all_vars = set()
        self.loop_vars = set()

        code = CodeBuilder()
        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered = []

        def flush_output():
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []
        text = text.replace(",", " , ")
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)

        for token in tokens:
            if token.startswith('{#'):
                # Comment: ignore it and move on.
                continue
            elif token.startswith('{{'):
                # An expression to evaluate.
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str({0})".format(expr))
            elif token.startswith('{%'):
                # Action tag: split into words and parse further.
                flush_output()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    # An if statement: evaluate the expression to determine if.
                    # if len(words) != 2:
                    #    self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if {0}:".format(
                        self._expr_code(' '.join(words[1:]))))
                    code.indent()
                elif words[0] == 'elif':
                    # An elif statement: evaluate the expression to determine else.
                    #print("Uso de 'else' en el template detectado.")
                    # if len(words) != 2:
                    #    self._syntax_error("Don't understand elif", token)
                    if not ops_stack:
                        self._syntax_error(
                            "'elif' without previous 'if'", token)
                    start_what = ops_stack.pop()
                    if (start_what != "if"):
                        self._syntax_error(
                            "'elif' without previous 'if'", token)
                    ops_stack.append('if')
                    code.dedent()
                    code.add_line("elif {0}:".format(
                        self._expr_code(' '.join(words[1:]))))
                    code.indent()
                elif words[0] == 'else':
                    # An else statement: evaluate the expression to determine else.
                    #print("Uso de 'else' en el template detectado.")
                    if len(words) != 1:
                        self._syntax_error("Don't understand else", token)
                    if not ops_stack:
                        self._syntax_error(
                            "'Else' without previous 'if'", token)
                    start_what = ops_stack.pop()
                    if (start_what != "if"):
                        self._syntax_error(
                            "'Else' without previous 'if'", token)
                    ops_stack.append('else')
                    code.dedent()
                    code.add_line("else:")
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    if words[-2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    loopvars = list(filter(lambda x: x != ',', words[1:-2]))
                    for loopvar in loopvars:
                        self._variable(loopvar, self.loop_vars)
                    deco_loopvars = list(map(lambda v: f"c_{v}", loopvars))
                    line_to_add = "for {0} in {1}:".format(
                        " , ".join(deco_loopvars), self._expr_code(words[-1]))
                    code.add_line(line_to_add)
                    code.indent()
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if (start_what != end_what) and (start_what != "else" or end_what != "if"):
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # Literal content.  If it isn't empty, output it.
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

        code.add_line("return ''.join(result)")
        code.dedent()

        self._code = code
        self._render_function = code.get_globals()['render_function']

    @staticmethod
    def _is_string(name):
        pattrn = r"""^(\"|\')(.*?)\1$"""
        return re.match(pattrn, name)

    @staticmethod
    def _is_reserved(name):
        if name == "true":
            name = "True"
        if name == "false":
            name = "False"
#        if name == "null" or name == "nil":
#            name = "None"
        return name in ["|", "if", "else", "and", "or", "not", "in", "is", "True", "False", "None"]

    @staticmethod
    def _is_variable(name):
        if TemplateLight._is_reserved(name) or TemplateLight._is_string(name):
            return False
        pattrn = r"(?P<varname>[_a-zA-Z][_a-zA-Z0-9]*)(?P<subscript>\[(?P<subvar>.+)\])?$"
        return re.match(pattrn, name)

    def _variable(self, name, vars_set):
        """Track that `name` is used as a variable.
        Adds the name to `vars_set`, a set of variable names.
        Raises an syntax error if `name` is not a valid name.
        """
        m = self._is_variable(name)
        if not m:
            self._syntax_error("Not a valid name", name)
        d = m.groupdict()
        vars_set.add(d.get("varname"))
        #subvar = d.get("subvar")
        # if subvar and self._is_variable(subvar):
        #    vars_set.add(self._expr_code(subvar))

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        nonisobar = r"[^\s]\|[^\s]"
        if re.findall(nonisobar, expr):
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        elif "." in expr:
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" % (code, args)
        else:
            subexprs = expr.split()
            code = ""
            for subexpr in subexprs:
                m = self._is_variable(subexpr)
                if m:
                    self._variable(subexpr, self.all_vars)
                    d = m.groupdict()
                    varname = f"c_{d.get('varname')}"
                    subscript = d.get('subscript', '')
                    if subscript:
                        subvar = d.get('subvar')
                        if subvar and self._is_variable(subvar):
                            subscript = subscript.replace(
                                subvar, f"c_{subvar}")
                    code += "{0}{1} ".format(varname,
                                             subscript if subscript else "")
                else:
                    code += f"{subexpr} "
        return code

    def _syntax_error(self, msg, thing):
        """Raise a syntax error using `msg`, and showing `thing`."""
        raise TemplateSyntaxError("%s: %r" % (msg, thing))

    def _do_dots(self, value, *dots):
        """Evaluate dotted expressions at runtime."""
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                if isinstance(value, list) or isinstance(value, tuple):
                    dot = int(dot)
                value = value[dot]
            if callable(value):
                value = value()
        return value

    def render(self, **context):
        """Render this template by applying it to `context`.
        `context` is a dictionary of values to use in this rendering.
        """
        # Make the complete context we'll use.
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)


header_prefix_html = """
<!DOCTYPE html>
  <html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" href="/static/img/bicchiere-rosso-2.png" type="image/x-icon" />
"""

header_suffix_html = """
    <title> {{ page_title }} </title>
  </head>
"""

body_prefix_html = """
<body>
  <div class="navbar">
    {{ menu_content }}
  </div>
  <div class="container" id="main-container">
"""

body_suffix_html = """
    <script type="text/javascript">
        // script to handle clicks on notifications
        document.addEventListener('DOMContentLoaded', function() {
	    // console.log("DOMContentLoaded");

	    (document.querySelectorAll('.notification .delete') || []).forEach(function($delete) {
    	        var $notification = $delete.parentNode;
		$delete.addEventListener('click', function() {
      		   $notification.parentNode.removeChild($notification);
    		});
  	    });

          // Get all "navbar-burger" elements
          var $navbarBurgers = Array.prototype.slice.call(document.querySelectorAll('.navbar-burger'), 0);
          //console.log("Processing click handlers for " + $navbarBurgers.length + " burgers.");
          // Check if there are any navbar burgers
          if ($navbarBurgers.length > 0) {
            // Add a click event on each of them
            $navbarBurgers.forEach( function(el) {
              el.addEventListener('click', function() {
                // Get the target from the "data-target" attribute
                //console.log("el: " + el.innerHTML);
		//console.log("el.dataset: " + el.dataset);
                var target = el.dataset.target;
                //console.log("target: " + target);
                var $target = document.getElementById(target);
                //console.log("$target: " + $target);
		// Toggle the "is-active has-text-link" class on both the "navbar-burger" and the "navbar-menu"
                el.classList.toggle('is-active');
                el.classList.toggle('has-text-link');
                $target.classList.toggle('is-active');
                $target.classList.toggle('has-text-link');
                //console.log("el.classList: " + el.classList);
                //console.log("$target.classList: " + $target.classList);
                //console.log('Click sobre el burger!');
              });
            });
          }
       });
    </script>

      </div>
    </body>
  </html>
"""

fontawesome_style = """
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
"""

bulma_style = """
 <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.1/css/bulma.min.css">
"""

body_style = """
  <style>
  body {
    font-family: Arial, Helvetica, sans-serif;
  }
  </style>
"""

menu_style = """
  <style>
  .navbar {
    overflow: hidden;
    background-color: #676767;
  }

  .navbar a {
    float: left;
    font-size: 16px;
    color: white;
    text-align: center;
    padding: 14px 16px;
    text-decoration: none;
  }

  .dropdown {
    float: left;
    overflow: hidden;
  }

  .dropdown .dropbtn {
    font-size: 16px;
    border: none;
    outline: none;
    color: white;
    padding: 14px 16px;
    background-color: inherit;
    font-family: inherit;
    margin: 0;
  }

  .navbar a:hover, .dropdown:hover .dropbtn {
    background-color: steelblue;
  }

  .dropdown-content {
    display: none;
    position: absolute;
    background-color: #f9f9f9;
    min-width: 160px;
    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
    z-index: 1;
  }

  .dropdown-content a {
    float: none;
    color: black;
    padding: 12px 16px;
    text-decoration: none;
    display: block;
    text-align: left;
  }

  .dropdown-content a:hover {
    background-color: #ddd;
  }

  .dropdown:hover .dropdown-content {
    display: block;
  }
  </style>
"""

# Page template includes 3 placeholders: 'page_title', 'menu_content' and 'main_contents'
page_template = chr(10).join([
    header_prefix_html,
    body_style,
    fontawesome_style,
    menu_style,
    header_suffix_html,
    body_prefix_html,
    "{{ main_contents }}",
    body_suffix_html
])

page_template_with_bulma = chr(10).join([
    header_prefix_html,
    body_style,
    fontawesome_style,
    bulma_style,
    menu_style,
    header_suffix_html,
    body_prefix_html,
    "{{ main_contents }}",
    body_suffix_html
])


class MenuItem:

    def __init__(self, label, link):
        self.label = label
        self.link = link

    def __repr__(self):
        return '<a href="{0}">{1}</a>'.format(self.link, self.label)


class DropdownMenu:

    def __init__(self, label="Dropdown"):
        self.label = label
        self.__items = list()

    def addItem(self, item: MenuItem):
        if not isinstance(item, MenuItem):
            return False
        else:
            self.__items.append(item)
            return True

    def __repr__(self):
        parts = []
        prefix = f"""
        <div class="dropdown">
            <button class="dropbtn">{self.label}
            <i class="fa fa-caret-down"></i>
            </button>
            <div class="dropdown-content">
        """
        parts.append(prefix)
        for i in self.__items:
            parts.append(str(i))
        suffix = """
            </div>
        </div>
        """
        parts.append(suffix)
        return "".join(parts)


class MenuBuilder:

    def __init__(self):
        self.__items = []

    def addItem(self, item: MenuItem):
        if not isinstance(item, (MenuItem, DropdownMenu)):
            return False
        else:
            self.__items.append(item)
            return True

    def __repr__(self):
        parts = []
        for i in self.__items:
            parts.append(str(i))
        return "".join(parts)


# End of templates related code

# Session handling support classes

class Session(SuperDict):
    """Session handling base class"""

    secret = None

    @classmethod
    def encrypt(cls, text=uuid4().hex):
        if not cls.secret:
            # raise ValueError(
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
        self.save()

    def load(self) -> str:
        return str(self)

    def save(self) -> str:
        return str(self)

    def get_store_dir(self) -> str:
        store_dir = os.path.join(
            os.getcwd(), Bicchiere.config['sessions_directory'])
        if os.path.exists(store_dir) is False:
            os.mkdir(store_dir)
        return store_dir

    def get_file(self):
        if not self.sid:
            return ""
        return os.path.join(self.get_store_dir(), self.sid)

    def __setitem__(self, __k: str, __v) -> str:
        super().__setitem__(__k, __v)
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
            # for k in self:
            #    if not k == "sid":
            #        del self[k]
            fp.close()
            for k in old_self:
                self[k] = old_self[k]
        return json.dumps(self)

    def save(self) -> str:
        file = self.get_file()
        fp = open(file, "wt", encoding="utf-8")
        json.dump(self, fp, default=lambda x: repr(x))
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
            Bicchiere.debug(
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
            Bicchiere.debug(
                f"Exception '{exc.__class__.__name__}': {repr(exc)}")
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
                    # for k in self:
                    #    if not k == "sid":
                    #        del self[k]
                    old_self = json.loads(data)
                    for k in old_self:
                        self[k] = old_self[k]
                except Exception as exc:
                    Bicchiere.debug(
                        f"Exception '{exc.__class__.__name__}': {repr(exc)}")
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
                    "update sessions set data = ? where sid = ?;", (json.dumps(self, default=lambda x: repr(x)), self.sid))
            else:
                cursor.execute(
                    "insert into sessions (sid, data) values (?, ?);", (self.sid, json.dumps(self, default=lambda x: repr(x))))
            conn.commit()
        except Exception as exc:
            Bicchiere.debug(
                f"Exception '{exc.__class__.__name__}': {repr(exc)}")
        finally:
            cursor.close()
            conn.close()
        return json.dumps(self)

# End of session handling support classes


# Miscelaneous configuration options

default_config = SuperDict({
    'debug': False,
    'session_class': FileSession,
    'sessions_directory': 'bicchiere_sessions',
    'static_directory': 'static',
    'templates_directory': 'templates',
    'allow_directory_listing': False,
    'pre_load_default_filters': True,
    'websocket_class': WebSocket,
    'allow_cgi': True,
    'cgi_directory': 'cgi-bin'
})

# End of miscelaneous configuration options


# Middleware

class BicchiereMiddleware:
    "Base class for everything Bicchiere"

    __version__ = (1, 9, 0)
    __author__ = "Domingo E. Savoretti"
    config = default_config
    template_filters = {}
    known_wsgi_servers = ['bicchiereserver', 'gunicorn', 'whypercorn',
                          'bjoern', 'wsgiref', 'waitress', 'uwsgi', 'gevent']
    known_asgi_servers = ['uvicorn', 'hypercorn', 'daphne', 'asgiserver']
    bevande = ["Campari", "Negroni", "Vermut",
               "Bitter", "Birra"]  # Ma dai! Cos'e questo?

    @property
    def version(self):
        major, minor, release = self.__version__
        return f"{major}.{minor}.{release}"

    def set_cookie(self, key, value, **attrs):
        self.headers.add_header('Set-Cookie', f'{key}={value}', **attrs)

    def get_cookie(self, key):
        return self.cookies.get(key, None)

    def redirect(self, path, status_code=302, status_msg="Found"):
        self.headers.add_header('Location', path)
        status_line = f"{status_code} {status_msg}"
        self.logger.info(f"Redirecting (status code {status_code}) to {path}")
        self.start_response(status_line, self.headers.items())
        self._start_response = self.no_response
        return [status_line.encode("utf-8")]

    
    @staticmethod
    def scope2env(scope, body):
        """
        Builds a scope and request body into a WSGI environ object.
        """
        if not scope:
            return None

        environ = {
            "REQUEST_METHOD": scope.get("method", "GET"),
            "SCRIPT_NAME": BicchiereMiddleware.tobytes(scope.get("root_path", "")).decode("latin1"),
            "PATH_INFO": BicchiereMiddleware.tobytes(scope.get("path", b"/")).decode("latin1"),
            "QUERY_STRING": BicchiereMiddleware.tobytes(scope.get("query_string", b"")).decode("ascii"),
            "SERVER_PROTOCOL": "HTTP/%s" % scope.get("http_version", "1.1"),
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": scope.get("scheme", "http"),
            "wsgi.input": BytesIO(body),
            "wsgi.errors": BytesIO(),
            "wsgi.multithread": True,
            "wsgi.multiprocess": True,
            "wsgi.run_once": False,
        }
        # Get server name and port - required in WSGI, not in ASGI
        if "server" in scope:
            environ["SERVER_NAME"] = scope["server"][0]
            environ["SERVER_PORT"] = str(scope["server"][1])
        else:
            environ["SERVER_NAME"] = "localhost"
            environ["SERVER_PORT"] = "80"

        if "client" in scope:
            environ["REMOTE_ADDR"] = scope["client"][0]

        # Go through headers and make them into environ entries
        for name, value in scope.get("headers", []):
            name = name.decode("latin1")
            if name == "content-length":
                corrected_name = "CONTENT_LENGTH"
            elif name == "content-type":
                corrected_name = "CONTENT_TYPE"
            else:
                corrected_name = "HTTP_%s" % name.upper().replace("-", "_")
            # HTTPbis say only ASCII chars are allowed in headers, but we latin1 just in case
            value = value.decode("latin1")
            if corrected_name in environ:
                value = environ.get(corrected_name) + "," + value
            environ[corrected_name] = value
        return environ

    # SCGI stuff

    @staticmethod
    def to_netstring(text):
        pad2 = lambda t: t if len(t) > 1 else f"0{t}"
        return f"<{' '.join(list(map(lambda c: pad2(hex(ord(c)).replace('0x', '')), list(text))))}>"

    @staticmethod
    def from_netstring(text):
        return f"\"{''.join(list(map(lambda c: chr(int(c, 16)), text.replace('<', '').replace('>', '').split())))}\""

    # End of SCGI stuff


    # Template related stuff

    @staticmethod
    def get_template_dir():
        templates_root = BicchiereMiddleware.config.get(
            'templates_directory', 'templates')
        return os.path.join(os.getcwd(), templates_root)

    @staticmethod
    def get_template_fullpath(template_file):
        return os.path.join(BicchiereMiddleware.get_template_dir(), template_file)

    @staticmethod
    def preprocess_template(tpl_str=TemplateLight.test_tpl):
        ftpl = StringIO(tpl_str)
        lines = ftpl.readlines()
        ftpl.close()
        for index, line in enumerate(lines):
            stripline = line.strip()
            m = re.match(
                r"\{\#\s+include\s+(?P<inc_file>[a-zA-Z0-9.\"\']+)\s+\#\}", stripline)
            if m:
                inc_file = m.group_dict().get("inc_file")
                if not inc_file:
                    raise TemplateSyntaxError(
                        "include directiva must refer to a file")
                fullpath = BicchiereMiddleware.get_template_fullpath(
                    inc_file.replace("\"", "").replace("'", ""))
                if os.path.exists(fullpath) and os.path.isfile(fullpath):
                    fp = open(fullpath)
                    new_tpl_str = fp.read()
                    fp.close()
                    replace_line = BicchiereMiddleware.preprocess_template(
                        new_tpl_str)
                    lines[index] = replace_line
                else:
                    raise TemplateSyntaxError(
                        "Included file {0} in line {1} does not exist.".format(inc_file, index))
        return "".join(lines)

    @staticmethod
    def compile_template(tpl_str=TemplateLight.test_tpl):
        if not tpl_str:
            return None
        words = tpl_str.split()
        if len(words) == 1:
            fullpath = BicchiereMiddleware.get_template_fullpath(tpl_str)
            if os.path.exists(fullpath) and os.path.isfile(fullpath):
                fp = open(fullpath)
                tpl_str = fp.read()
                fp.close()
        return TemplateLight(BicchiereMiddleware.preprocess_template(tpl_str),
                             **BicchiereMiddleware.template_filters)

    @staticmethod
    def render_template(tpl_str=TemplateLight.test_tpl, **kw):
        if tpl_str.__class__.__name__ == "TemplateLight":
            return tpl_str.render(**kw)
        elif tpl_str.__class__.__name__ == "str":
            compiled = BicchiereMiddleware.compile_template(tpl_str)
            if compiled:
                return compiled.render(**kw)
            else:
                return None
        else:
            return None

    # End of template related stuff

    def debug(self, *args, **kw):
        if hasattr(self, "config") and hasattr(self.config, "get"):
            if self.config.get("debug"):
                self.logger.setLevel(10)
                self.logger.debug(*args, **kw)

    @staticmethod
    def func_args(callablee):
        if not callable(callablee):
            raise ValueError(
                "A callable must be provided in order to get the signature.")
        firma = inspect.signature(callablee)
        return list(map(lambda t: t[0], firma.parameters.items()))

    @staticmethod
    def is_asgi(callablee):
        args = BicchiereMiddleware.func_args(callablee)
        if len(args) < 3:
            return False
        return args[0].lower() in ["context", "scope"] and args[1].lower() == "receive" and args[2].lower() == "send"

    @staticmethod
    def is_wsgi(callablee):
        args = BicchiereMiddleware.func_args(callablee)
        if len(args) < 2:
            return False
        return args[0].lower() == "environ" and args[1].lower() == "start_response"

    @staticmethod
    def seconds():
        return round(timestamp())

    @staticmethod
    def millis():
        return round(timestamp() * 1000.0)

    @staticmethod
    def no_response(*args, **kwargs):
        pass

    @staticmethod
    def is_html(fragment):
        rtest1 = r'<(\w+)\s*.*>.*?</\1>'
        rtest2 = r'doctype\s*=?\s*html'
        to_be_tested = str(fragment).lower()
        return re.search(rtest1, to_be_tested) or re.search(rtest2, to_be_tested) or False

    @staticmethod
    def qs2dict(qs):
        if type(qs) is bytes:
            qs = qs.decode('utf-8')
        try:
            return dict(parse_qsl(qs))
        except Exception as exc:
            return {}

    @staticmethod
    def tobytes(s):
        retval = None
        if not hasattr(s, '__iter__'):
            #Bicchiere.debug("Not an iterable, returning an empty bytes string")
            return b''
        if type(s) == int:
            return chr(s).encode()
        if type(s).__name__ == 'generator':
            #Bicchiere.debug("Got a generator, transforming it into a list")
            s = [x for x in s]  # pack the generator in a list and then go on
        if hasattr(s, "__len__") and len(s) == 0:
            #Bicchiere.debug(f"Length s for provided {s.__class__.__name__}, returning an empty bytes string")
            return b''
        elif hasattr(s, "__len__") and type(s[0]) == int:
            #Bicchiere.debug("Got a byte string, returning it unchanged")
            return s  # It's a sequence of ints, i.e. bytes
        elif hasattr(s, "__len__") and type(s[0]) == bytes:
            #Bicchiere.debug("Got a sequence of byte strings, joining it in one prev. to returning it.")
            return b''.join(s)  # It's a sequence of byte strings
        elif hasattr(s, "__len__") and type(s[0]) == str:
            return b''.join([x.encode('utf-8') for x in s])
        else:
            return b''

    @staticmethod
    def encode_image(image_data, image_type='image/jpeg'):
        img_template = "data:{0};base64,{1}"
        img_string = base64.b64encode(image_data).decode("utf-8")
        return img_template.format(image_type, img_string)

    @staticmethod
    def get_status_code(code):
        "Get section and msg for provided code, or the whole list if no code is provided"
        codes = {'100': {'section': 'Section 10.1.1', 'status_msg': 'Continue'},
                 '101': {'section': 'Section 10.1.2', 'status_msg': 'Switching Protocols'},
                 '200': {'section': 'Section 10.2.1', 'status_msg': 'OK'},
                 '201': {'section': 'Section 10.2.2', 'status_msg': 'Created'},
                 '202': {'section': 'Section 10.2.3', 'status_msg': 'Accepted'},
                 '203': {'section': 'Section 10.2.4',
                         'status_msg': 'Non-Authoritative Information'},
                 '204': {'section': 'Section 10.2.5', 'status_msg': 'No Content'},
                 '205': {'section': 'Section 10.2.6', 'status_msg': 'Reset Content'},
                 '206': {'section': 'Section 10.2.7', 'status_msg': 'Partial Content'},
                 '300': {'section': 'Section 10.3.1', 'status_msg': 'Multiple Choices'},
                 '301': {'section': 'Section 10.3.2', 'status_msg': 'Moved Permanently'},
                 '302': {'section': 'Section 10.3.3', 'status_msg': 'Found'},
                 '303': {'section': 'Section 10.3.4', 'status_msg': 'See Other'},
                 '304': {'section': 'Section 10.3.5', 'status_msg': 'Not Modified'},
                 '305': {'section': 'Section 10.3.6', 'status_msg': 'Use Proxy'},
                 '307': {'section': 'Section 10.3.8', 'status_msg': 'Temporary Redirect'},
                 '400': {'section': 'Section 10.4.1', 'status_msg': 'Bad Request'},
                 '401': {'section': 'Section 10.4.2', 'status_msg': 'Unauthorized'},
                 '402': {'section': 'Section 10.4.3', 'status_msg': 'Payment Required'},
                 '403': {'section': 'Section 10.4.4', 'status_msg': 'Forbidden'},
                 '404': {'section': 'Section 10.4.5', 'status_msg': 'Not Found'},
                 '405': {'section': 'Section 10.4.6', 'status_msg': 'Method Not Allowed'},
                 '406': {'section': 'Section 10.4.7', 'status_msg': 'Not Acceptable'},
                 '407': {'section': 'Section 10.4.8',
                         'status_msg': 'Proxy Authentication Required'},
                 '408': {'section': 'Section 10.4.9', 'status_msg': 'Request Time-out'},
                 '409': {'section': 'Section 10.4.10', 'status_msg': 'Conflict'},
                 '410': {'section': 'Section 10.4.11', 'status_msg': 'Gone'},
                 '411': {'section': 'Section 10.4.12', 'status_msg': 'Length Required'},
                 '412': {'section': 'Section 10.4.13', 'status_msg': 'Precondition Failed'},
                 '413': {'section': 'Section 10.4.14',
                         'status_msg': 'Request Entity Too Large'},
                 '414': {'section': 'Section 10.4.15', 'status_msg': 'Request-URI Too Large'},
                 '415': {'section': 'Section 10.4.16', 'status_msg': 'Unsupported Media Type'},
                 '416': {'section': 'Section 10.4.17',
                         'status_msg': 'Requested range not satisfiable'},
                 '417': {'section': 'Section 10.4.18', 'status_msg': 'Expectation Failed'},
                 '418': {'section': 'Section 10.4.18', 'status_msg': "I'm a teapot"},
                 '419': {'section': 'Section 10.4.19', 'status_msg': "Sono un bicchiere"},
                 '500': {'section': 'Section 10.5.1', 'status_msg': 'Internal Server Error'},
                 '501': {'section': 'Section 10.5.2', 'status_msg': 'Not Implemented'},
                 '502': {'section': 'Section 10.5.3', 'status_msg': 'Bad Gateway'},
                 '503': {'section': 'Section 10.5.4', 'status_msg': 'Service Unavailable'},
                 '504': {'section': 'Section 10.5.5', 'status_msg': 'Gateway Time-out'},
                 '505': {'section': 'Section 10.5.6',
                         'status_msg': 'HTTP Version not supported'}}
        return codes.get(str(code)) if code else None

    @staticmethod
    def get_status_line(code):
        line = Bicchiere.get_status_code(str(code)) if code else None
        return f"{code} {line['status_msg']}" if line else ""

    @staticmethod
    def is_iterable(obj):
        return hasattr(obj, '__iter__')

    @staticmethod
    def is_callable(obj):
        return hasattr(obj, '__call__') or Bicchiere.is_iterable(obj)

    @staticmethod
    def build_route_pattern(route):
        accepted_types = ['str', 'int', 'float']
        params = []
        params_types = []
        param_regex = r'(<((\w+):)?(\w+)>)'
        replace_regex = r'(?P<{}>.+)'

        def regex_parser(m):
            if not m:
                return ''
            params.append(m.group(4))
            if not m.group(2):
                params_types.append(type("42"))
            else:
                if not m.group(3) in accepted_types:
                    raise ValueError(f"Unknown parameter type: {m.group(3)}")
                else:
                    if m.group(3) == 'int':
                        ptype = type(42)
                    elif m.group(3) == 'float':
                        ptype = type(42.)
                    else:
                        ptype = type("42")
                params_types.append(ptype)
            return replace_regex.format(m.group(4))

        route_regex = re.sub(param_regex, regex_parser, route)
        return re.compile("^{}$".format(route_regex)), dict(zip(params, params_types))

    def _config_environ(self):
        for h in self.environ:
            if h.lower().endswith('cookie'):
                self.debug(f"\nLoading stored cookies: {h}: {self.environ.get(h)}")
                self.cookies = SimpleCookie(
                    self.environ.get(h).strip().replace(' ', ''))
                for h in self.cookies:
                    self.debug(
                        f"Cookie {self.cookies.get(h).key} = {self.cookies.get(h).value}")
        self.environ['bicchiere_cookies'] = str(self.cookies).strip()

    def _test_environ(self):
        if self.environ is None:
            return False
        else:
            return True

    def _init_session(self):
        sid = self.cookies.get('sid', None)
        if not sid:
            sid = self.cookies.get('_sid', None)
        if sid:
            sid = sid.value
        else:
            #sid = uuid4().hex
            sid = Session.encrypt()

        self.session = self.get_session(sid)
        #print(self.session.sid if self.session else "No session :-(")
        #print(self.environ.get("USER_AGENT") if self.environ else "No environ :-(")
        if self.session and self.environ:
            self.session['USER_AGENT'.lower()] = self.environ.get('HTTP_USER_AGENT', "Unknown user agent")
            self.session['REMOTE_ADDR'.lower()] = self.environ.get("HTTP_X_FORWARDED_FOR", 
                self.environ.get('REMOTE_ADDR'))
            self.environ['bicchiere_session'] = self.session

        cookie_opts = {}
        cookie_opts['Max-Age'] = "3600"
        cookie_opts['HttpOnly'] = ""
        self.set_cookie('sid', sid, **cookie_opts)

    def _init_args(self):
        if not self.environ:
            self.args = {}
        else:
            self.args = self.qs2dict(self.environ.get('QUERY_STRING', ''))

    def _init_form(self):
        self.input = self.environ.get('wsgi.input')

        if hasattr(self.input, "closed"):
            self.logger.info(f"wsgi.input status: {self.input.closed}")
        else:
            self.logger.info(f"{self.input.__class__.__name__} has not a 'closed' attribute")
        self.form = cgi.FieldStorage(fp=self.input, environ=self.environ, keep_blank_values=1)

    def _try_mounted(self):
        old_env = None
        self.full_path = self.environ.get('PATH_INFO')
        status_msg = None
        response = None

        for r, app in self.mounted_apps.items():
            if self.full_path.startswith(r):
                self.debug(f"found path prefix {r} in mounted app.")
                new_env = self.environ
                old_env = new_env.copy()
                mounted_path = self.full_path.replace(r, '')
                if not mounted_path.startswith("/"):
                    mounted_path = f"/{mounted_path}"
                new_env['PATH_INFO'] = mounted_path
                if asyncio.iscoroutinefunction(app):
                    #response = asyncio.run(app(new_env, self.no_response if app is not self else start_response))
                    response = asyncio.run(app(new_env, self._start_response))
                    self._start_response = self.no_response
                else:
                    #response = app(new_env, self.no_response if app is not self else start_response)
                    response = app(new_env, self._start_response)
                    self._start_response = self.no_response
                return "200 OK", response
        if old_env:
            self.environ = old_env
        self.environ['PATH_INFO'] = f"{self.path_prefix}{self.environ.get('PATH_INFO')}"
        return status_msg, response


    def _try_routes(self):
        route = None
        response = None
        status_msg = None

        try:
            self.full_path = self.environ.get('PATH_INFO')
            route = self.get_route_match(self.full_path)
            if route:
                if self.environ.get('REQUEST_METHOD', 'GET') in route.methods:
                    status_msg = BicchiereMiddleware.get_status_line(200)
                    if asyncio.iscoroutinefunction(route.func):
                        response = asyncio.run(route.func(**route.args))
                    else:
                        response = route.func(**route.args)
                    return status_msg, response
                else:
                    status_msg, response = self._abort(405, self.environ.get('REQUEST_METHOD'),
                                       f'not allowed for URL: {self.environ.get("PATH_INFO", "")}')
                    return status_msg, response
            else:
                #status_msg, response = self._abort(404, self.environ.get('path_info'.upper()), " not found.")
                #return status_msg, response
                return None, None
        except Exception as exc:
            status_msg, response = self._abort(500, self.environ.get('PATH_INFO'),
                               f'raised an error: {str(exc)}')
            return status_msg, response

    def _try_default(self):
        if len(self.routes) == 0 and len(self.mounted_apps) == 0:
            if self.environ.get('path_info'.upper()) != '/':
                status_msg, response = self._abort(404, self.environ.get('path_info'.upper()), " not found.")
            else:
                status_msg = Bicchiere.get_status_line(200)
                response = self.default_handler()
            return status_msg, response
        return None, None

    @staticmethod
    def _make_cgi_env(env):
        # Allowed CGI environmental variables
        cgi_vars = """
        SERVER_SOFTWARE
        SERVER_NAME
        GATEWAY_INTERFACE
        SERVER_PROTOCOL
        SERVER_PORT
        REQUEST_METHOD
        PATH_INFO
        PATH_TRANSLATED
        SCRIPT_NAME
        QUERY_STRING
        REMOTE_HOST
        REMOTE_ADDR
        AUTH_TYPE
        REMOTE_USER
        REMOTE_IDENT
        CONTENT_TYPE
        CONTENT_LENGTH
        """.split('\n')
        
        cgi_vars = list(filter(lambda x: len(x), map(lambda x: x.strip(), cgi_vars)))
        d = {}
        for k in cgi_vars:
            d[k] = ''

        os.system("clear")
        for k, v in env.items():
            if k in cgi_vars or k.startswith("HTTP_"):
                d[k] = v
        logger.info(f"CGI ENV: {repr(d)}")
        return d

    @staticmethod
    def _run_cgi(resource, env=os.environ):
        def is_status_line(line): return len(line.split()) == 3 and \
            line.split()[1].isdigit() and 90 < int(line.split()[1]) < 1000

        def is_header_line(line): 
            return len(line.split(b":")) == 2 and not b"<" in line

        input_stream = env.get("wsgi.input")
        status_line = b""
        response = b""
        headers = Headers()
        parg = resource.split()

        tf = TemporaryFile()
        tf.write(env.get("QUERY_STRING", '').encode())

        content_length = env.get('CONTENT_LENGTH', '')
        if not content_length:
            if hasattr(input_stream, "len"):
                content_length = len(input_stream)
            else:
                content_length = 0
        content_length = int(content_length) #if len(content_length) else 0
        logger.debug(f"Content of length {content_length} has been written to the request body.")
        if content_length > 0 and tf.tell() > 0:
            tf.write(b"&")
        if not hasattr(input_stream, 'read'):
            input_stream = BytesIO(input_stream) # Wrap it into a file like thing
        #iter_stream = wsgiref.util.FileWrapper(input_stream, blksize=content_length)
        counter = 0
        if content_length > counter:
            #for chunk in iter_stream:
                chunk = input_stream.read(content_length)
                counter += content_length
                tf.write(chunk)
                if counter == content_length:
                    tf.write(b"")
                    #break
        tf.seek(0)
        process = runsub(parg, stdin=tf, stdout=PIPE, stderr=STDOUT, 
            env=BicchiereMiddleware._make_cgi_env(env))
        output = process.stdout
        fp = BytesIO(output.replace(b"\r\n\r\n", b"\r\n \r\n"))
        lines = iter(map(lambda l: l.strip(), fp.readlines()))
        for line in lines:
            if line.startswith(b"stderr"):
                line = next(lines)
                logger.info(f"CGI stderr: {line}")
                break
            if not len(line):
                if not len(status_line):
                    logger.debug("Manually adding status line")
                    status_line = "200 OK"
            elif is_status_line(line) and not len(status_line):
                status_line = b" ".join(line.lstrip().split()[1:])
                logger.info(f"CGI status line: {status_line}")
            elif is_header_line(line):
                k, v = line.split(b":")
                headers.add_header(k.decode().strip(), v.decode().strip())
                logger.info(f"CGI header line: {k} = {v}")
            else:
                response += line if line else b"" + b"\n"
                logger.info(f"CGI content line: {line.lstrip()}")

        if not headers.get("Content-Type"):
            logger.debug("Manually adding 'Content-Type' header")
            if BicchiereMiddleware.is_html(response):
                headers.add_header(
                    'Content-Type', 'text/html', charset="utf-8")
            else:
                headers.add_header(
                    'Content-Type', 'text/plain', charset="utf-8")

        if not len(status_line):
            logger.debug("Manually adding status line")
            status_line = b"200 OK"

        logger.info(
            f"Returning with values:\nstatus_line: {repr(status_line)}\nresponse: {repr(response)}\nheaders: {repr(headers)}\n")
        return (Bicchiere.tobytes(status_line).decode() if status_line else "500 No status line",
                response.decode() if response else "",
                headers)

    def _try_cgi(self):
        curr_path = self.environ.get('PATH_INFO')
        if self.cgi_path in curr_path:
            if not self.config.allow_cgi:
                status_msg, response = self._abort(403, curr_path, "CGI Execution not allowed.")
                return status_msg, response
            resource = f"{os.getcwd()}{self.environ.get('path_info'.upper())}"
            self.debug("Searching for resource '{}'".format(resource))
            if os.path.exists(resource):
                if os.path.isfile(resource):
                    if os.access(resource, os.X_OK):
                        resource = resource
                    elif resource.endswith("py"):
                        resource = f"python {resource}"
                    elif resource.endswith("rb"):
                        resource = f"ruby {resource}"
                    else:
                        resource = None
                    if resource:
                        env = self.environ.copy()
                        status_line, response, headers = self._run_cgi(resource, env)
                        if status_line and response and headers:
                            for k, v in headers.items():
                                self.headers.add_header(k, v)
                        return status_line, response
                    else:
                        status_msg, response = self._abort(500, curr_path, " cannot be executed.")
                        return status_msg, response
                else:
                    status_msg, response = self._abort(400, curr_path, " is not a file, so it can't be executed.")
                    return status_msg, response
            else:
                status_msg, response = self._abort(404, curr_path, " resource not found in this server.")
                return status_msg, response
        else:
            return None, None

    def _try_static(self):
        if self.environ.get('path_info'.upper()).startswith(self.static_path):
            resource = f"{os.getcwd()}{self.environ.get('path_info'.upper())}"
            self.debug("Searching for resource '{}'".format(resource))
            if os.path.exists(resource):
                if os.path.isfile(resource):
                    mime_type, _ = guess_type(
                        resource) or ('text/plain', 'utf-8')
                    fp = open(resource, 'rb')
                    response = [b'']
                    r = fp.read(1024)
                    while r:
                        response.append(r)
                        r = fp.read(1024)
                    fp.close()
                    del self.headers['Content-Type']
                    self.headers.add_header(
                        'Content-Type', mime_type, charset='utf-8')
                    status_msg = Bicchiere.get_status_line(200)
                elif os.path.isdir(resource):
                    del self.headers['Content-Type']
                    self.headers.add_header(
                        'Content-Type', 'text/html', charset='utf-8')
                    if Bicchiere.config.get('allow_directory_listing', False) or Bicchiere.config.get('debug', False):
                        status_msg = Bicchiere.get_status_line(200)
                        response = [
                            b'<p style="margin-top: 15px;"><strong>Directory listing for&nbsp;</strong>']
                        response.append(
                            f'<strong style="color: steelblue;">{self.environ.get("path_info".upper())}</strong><p><hr/>'.encode())
                        left, right = os.path.split(
                            self.environ.get('path_info'.upper()))
                        if left != "/":
                            response.append(
                                f'<p title="Parent directory"><a href="{left}">..</a></p>'.encode())
                        l = os.listdir(resource)
                        l.sort()
                        for f in l:
                            fullpath = os.path.join(resource, f)
                            if os.path.isfile(fullpath) or os.path.isdir(fullpath):
                                href = os.path.join(
                                    self.environ.get('path_info'.upper()), f)
                                response.append(
                                    f'<p><a href="{href}">{f}</a></p>'.encode())
                    else:
                        status_msg, response = self._abort(403, self.environ.get('path_info'.upper()),
                                                           'Directory listing forbidden')
                else:
                    status_msg, response = self._abort(400, self.get_status_code(400).get('status_msg'),
                                                       'Bad request, file type cannot be handled.')
            else:
                status_msg, response = self._abort(404, self.environ.get('path_info'.upper()),
                                                   " not found.")
            return status_msg, response
        else:
            return None, None

    def _send_response(self, status_msg, response):

        if not self.headers_sent and 'content-type' not in self.headers:
            if response and self.is_html(response):
                self.headers.add_header(
                    'Content-Type', 'text/html', charset='utf-8')
            else:
                self.headers.add_header(
                    'Content-Type', 'text/plain', charset='utf-8')

        if response and self.config.debug:
            r = self.tobytes(response)
            if hasattr(response, "split"):
                dbg_msg_l = response.split('\n')
            else:
                dbg_msg_l = response
            dbg_msg = ''
            for msg in dbg_msg_l:
                if len(msg) > len(dbg_msg):
                    dbg_msg = msg
            self.debug(f"\nRESPONSE: '{dbg_msg[ : 79]}{'...' if len(dbg_msg) > 79 else ''}'")

        self.start_response(status_msg, self.headers.items())
        retval = b""
        # for i in range(len(response)):
        #     retval += self.tobytes(response[i])
        retval += self.tobytes(response)
        return [retval]

    def init_local_data(self):
        "Makes Bicchiere thread safe by assigning vars to thread local data"
        #self.debug("Initializing local data")
        self._local_data = threading.local()

        self._local_data.__dict__.setdefault('environ', None)
        self._local_data.__dict__.setdefault(
            '_start_response', self.no_response)
        self._local_data.__dict__.setdefault('headers', Headers())
        self._local_data.__dict__.setdefault('session', None)
        self._local_data.__dict__.setdefault('cookies', SimpleCookie())
        self._local_data.__dict__.setdefault('args', None)
        self._local_data.__dict__.setdefault('form', None)
        self._local_data.__dict__.setdefault('headers_sent', False)

        self.clear_headers()
        self.headers_sent = False
        if self.session:
            del self.session
        self.session = None
        self.cookies = SimpleCookie()

# Decorators

# Web socket handler decorator

    def websocket_handler(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.environ:
                return "500 malformed environment"
            known_versions = ('13', '8', '7')
            guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            connection = self.environ.get("HTTP_CONNECTION")
            if not connection or not "Upgrade" in connection:
                self.debug(
                    f'Error with HTTP_CONNECTION header: {repr(self.environ.get("HTTP_CONNECTION"))}')
                status_msg, response = self._abort(400, self.environ.get("PATH_INFO"),
                                                   "Not a websocket request")
                self.start_response(
                    status_msg, [('Content-Type', 'text/html; charset=utf-8')])
                return response
            upgrade = self.environ.get("HTTP_UPGRADE")
            if not upgrade or upgrade != "websocket":
                self.debug(
                    f'Error with HTTP_UPGRADE header: {repr(self.environ.get("HTTP_UPGRADE"))}')
                status_msg, response = self._abort(400, self.environ.get("PATH_INFO"),
                                                   "Not a websocket request")
                self.start_response(
                    status_msg, [('Content-Type', 'text/html; charset=utf-8')])
                return response
            wsversion = self.environ.get("HTTP_SEC_WEBSOCKET_VERSION")
            if not wsversion or wsversion not in known_versions:
                self.debug(
                    f'Error with HTTP_SEC_WEBSOCKET_VERSION header: {repr(self.environ.get("HTTP_SEC_WEBSOCKET_VERSION"))}')
                raise WebSocketError(
                    f"Websocket version {wsversion if wsversion else 'unknown'} not allowed.")
            wskey = self.environ.get("HTTP_SEC_WEBSOCKET_KEY")
            if not wskey:
                self.debug(
                    f'Error with HTTP_SEC_WEBSOCKET_KEY header: {repr(self.environ.get("HTTP_SEC_WEBSOCKET_KEY"))}')
                raise WebSocketError("Non existent websocket key.")
            key_len = len(base64.b64decode(wskey))
            if key_len != 16:
                self.debug(
                    f'Error with websocket key length (should be 16) but is {key_len}')
                raise WebSocketError(f"Incorrect websocket key.")
            requested_protocols = self.environ.get(
                'HTTP_SEC_WEBSOCKET_PROTOCOL', '')
            protocol = None if not requested_protocols else re.split(
                r"/s*,/s*", requested_protocols)[0]
            extensions = list(map(lambda ext: ext.split(";")[0].strip(),
                                  self.environ.get("HTTP_SEC_WEBSOCKET_EXTENSIONS", "").split(",")))

            do_compress = "permessage-deflate" in extensions

            accept = base64.b64encode(hashlib.sha1(
                (wskey + guid).encode("latin-1")).digest()).decode("latin-1")
            headers = [("Upgrade", "websocket"),
                       ("Connection", "Upgrade"),
                       ("Sec-WebSocket-Accept", accept)]
            if protocol:
                headers.append(("Sec-WebSocket-Protocol", protocol))

            if do_compress:
                headers.append(
                    ("Sec-WebSocket-Extensions", "permessage-deflate"))

            final_headers = [(k, v) for k, v in headers if not wsgiref.util.is_hop_by_hop(k)]
            self.debug(f"Response headers for websocket:\n{final_headers}")

            self.writer = self.start_response("101 Switching protocols", final_headers)
            self.writer(b"")
            self.headers_sent = True
            self._start_response = lambda *args, **kw: None
            # Create the websocket object and update environ
            self.reader = self.environ.get("wsgi.input").read
            websocket_class = self.config.get("websocket_class")
            self.websocket = websocket_class(self.environ.copy(), self.reader, self.writer, self, do_compress)
            self.environ["wsgi.websocket"] = self.websocket
            self.environ["wsgi.version"] = wsversion
            # End of websocket creation part
            retval = ""
            if asyncio.iscoroutinefunction(func):
                retval = asyncio.run(func(*args, **kwargs))
            else:
                retval = func(*args, **kwargs)
            return retval

        return wrapper

# End of Web socket handler decorator


# Content decorators


    def content_type(self, c_type="text/html", charset="utf-8", **attrs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                del self.headers['Content-Type']
                self.headers.add_header(
                    'Content-Type', c_type, charset=charset, **attrs)
                # self.set_new_start_response()
                #self.start_response("200 OK", self.headers.items())
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def custom_header(self, header_name="Content-Disposition", header_value="attachment", charset="utf-8", **attrs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                self.debug(
                    f"Adding header {header_name} with value {header_value} and attrs: {attrs}")
                self.headers.add_header(header_name, header_value, **attrs)
                if header_name == "Content-Disposition" and header_value == "attachment" and "filename" in attrs:
                    filename = attrs["filename"]
                    try:
                        filetype = mimetypes.guess_type(filename)[0]
                    except:
                        filetype = "text/plain"
                    del self.headers['Content-Type']
                    self.debug(f"Trying to set content type to {filetype}")
                    self.headers.add_header(
                        'Content-Type', filetype, charset=charset)
                # self.set_new_start_response()
                #self.start_response("200 OK", self.headers.items())
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def html_content(self, **attrs):
        return self.content_type("text/html", "utf-8", **attrs)

    def plain_content(self, **attrs):
        return self.content_type("text/plain", "utf-8", **attrs)

    def json_content(self, **attrs):
        return self.content_type("application/json", "utf-8", **attrs)

    def csv_content(self, **attrs):
        return self.content_type("text/csv", "utf-8", **attrs)

# End of Content decorators

# Routing decorators

    def route(self, route_str, methods=['GET']):
        def decorator(func):
            pattern, types = self.build_route_pattern(route_str)
            self.routes.append(Route(pattern, func, types, methods))
            return func
        return decorator

    def get(self, route_str):
        return self.route(route_str, methods=['GET'])

    def post(self, route_str):
        return self.route(route_str, methods=['POST'])

    def put(self, route_str):
        return self.route(route_str, methods=['PUT'])

    def delete(self, route_str):
        return self.route(route_str, methods=['DELETE'])

    def head(self, route_str):
        return self.route(route_str, methods=['HEAD'])

    def _any(self, route_str):
        return self.route(route_str, methods=['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])

# End of decorators

# Thread specific properties, things which are in fact kept in a threading.local instance
# Necessary to handle multiprocessor/multithreading WSGI servers

    @property
    def environ(self):
        try:
            return self._local_data.environ
        except:
            return None

    @environ.setter
    def environ(self, new_env):
        self._local_data.environ = new_env

    @environ.deleter
    def environ(self):
        del self._local_data.environ

    @property
    def _start_response(self):
        try:
            return self._local_data._start_response
        except:
            return lambda *args, **kwargs: None

    @_start_response.setter
    def _start_response(self, new_sr):
        self._local_data._start_response = new_sr

    @_start_response.deleter
    def _start_response(self):
        del self._local_data._start_response

    @property
    def headers(self):
        try:
            return self._local_data.headers
        except:
            return Headers()

    @headers.setter
    def headers(self, new_h):
        self._local_data.headers = new_h

    @headers.deleter
    def headers(self):
        del self._local_data.headers

    @property
    def session(self):
        try:
            return self._local_data.session
        except:
            return None

    @session.setter
    def session(self, new_sess):
        self._local_data.session = new_sess

    @session.deleter
    def session(self):
        del self._local_data.session

    @property
    def cookies(self):
        try:
            return self._local_data.cookies
        except:
            return SimpleCookie()

    @cookies.setter
    def cookies(self, new_c):
        self._local_data.cookies = new_c

    @cookies.deleter
    def cookies(self):
        del self._local_data.cookies

    @property
    def args(self):
        try:
            return self._local_data.args
        except:
            return None

    @args.setter
    def args(self, new_args):
        self._local_data.args = new_args

    @args.deleter
    def args(self):
        del self._local_data.args

    @property
    def form(self):
        try:
            return self._local_data.form
        except:
            return None

    @form.setter
    def form(self, new_form):
        self._local_data.form = new_form

    @form.deleter
    def form(self):
        del self._local_data.form

    @property
    def headers_sent(self):
        try:
            return self._local_data.headers_sent
        except:
            return True

    @headers_sent.setter
    def headers_sent(self, new_hs):
        self._local_data.headers_sent = new_hs

    @headers_sent.deleter
    def headers_sent(self):
        del self._local_data.headers_sent

    def _show_local_data(self):
        return self._local_data.__dict__

    def get_session(self, sid):
        if self.session:
            self.session.load()
        else:
            self.session = self.session_class(sid)
        return self.session

    def clear_headers(self):
        self.headers = Headers()
        self.headers_sent = False

####

    def _abort(self, code=404, primary_message="Not found", secondary_message='', procceed=False):
        del self.headers['Content-Type']
        self.headers.add_header('Content-Type', 'text/html', charset="utf-8")
        status_msg = BicchiereMiddleware.get_status_line(code)
        prefix = 'METHOD ' if code == 400 else 'URL ' if code < 500 else 'ERROR '
        response = f'''
        <strong>{code}</strong>&nbsp;&nbsp;&nbsp;{prefix}&nbsp;
                        <span style="color: {'green' if code < 400 else 'red'};">{primary_message}</span>
                        {secondary_message}
        '''
        if procceed:
            self.start_response(status_msg, self.headers.items())
            self._start_response = self.no_response
            return response
        return status_msg, response

    logger = logger

    def __init__(self, application=None, name=None):
        self.routes = []
        self.application = application
        self.name = name or self.__class__.__name__
        #self.logger = logger
        self.path_prefix = ""
        self.mounted_apps = dict()
        self.static_root = Bicchiere.config.get('static_directory', 'static')
        self.static_path = f'/{self.static_root}'
        self.cgi_root = Bicchiere.config.get('cgi_directory', 'cgi-bin')
        self.cgi_path = f'/{self.cgi_root}'
        self.init_local_data()

    def __call__(self, environ, start_response):
        self.environ = environ
        self._start_response = start_response

        self.environ["wsgi_middleware"] = str(self)

        if self.application:
            return self.application(self.environ.copy(), self.start_response)
        else:
            start_response(
                "200 OK", [('Content-Type', 'text/html; charset=utf-8')])
            return [b"", str(self).encode("utf-8")]

    def mount(self, mount_point: str, app) -> None:
        if app is self:
            raise ValueError("An app can't be mounted on itself.")
        app.path_prefix = mount_point
        self.mounted_apps[mount_point] = app

    def umount(self, mount_point: str):
        for path, mounted_app in self.mounted_apps.items():
            if path == mount_point:
                mounted_app.path_prefix = ''
                return self.mounted_apps.pop(path)
        return None

    def __str__(self):
        return f"{self.__class__.__name__} v. {Bicchiere.get_version()}"

    @property
    def last_handler(self):
        lh = self.application if hasattr(
            self, "application") and Bicchiere.is_callable(self.application) else self

        while hasattr(lh, "application") and Bicchiere.is_callable(lh.application):
            lh = lh.application

        return lh or self

    def run(self, *args, **kwargs):
        if self.application:
            return self.application.run(*args, **kwargs)
        else:
            self.debug(
                f"{self.name} was meant as middleware, therefore it will not run stand alone")

    def start_response(self, status="200 OK", headers=[]):
        if self.headers_sent:
            return self.write or None

        if isinstance(headers, (dict, Headers)):
            headers = list(headers.items())
        self.write = self._start_response(status, headers)
        self.headers_sent = True
        return self.write

# End of middleware

# Main Bicchiere App class


class Bicchiere(BicchiereMiddleware):
    """
    Main WSGI application class
    """

    def __init__(self, name=None, application=None, **kwargs):
        "Prepares Bicchiere instance to run"

        super().__init__(application)

        # Register some common template filter functions
        if Bicchiere.config['pre_load_default_filters']:
            Bicchiere.register_template_filter("title", str.title)
            Bicchiere.register_template_filter("capitalize", str.capitalize)
            Bicchiere.register_template_filter("upper", str.upper)
            Bicchiere.register_template_filter("lower", str.lower)

        # First, things that don't vary through calls
        self.name = name if name else f"{self.__class__.__name__} - {random.choice(Bicchiere.bevande)}"
        self.session_class = Bicchiere.config['session_class']
        if not self.session_class.secret:
            self.session_class.secret = uuid4().hex
        #self.routes = []

        # Call specific variables
        self.init_local_data()

        self.environ = None
        self._start_response = lambda *args, **kwargs: None

        # And whatever follows....
        for k in kwargs:
            self.__dict__[k] = kwargs[k]

    def __call__(self, environ, start_response):
        # Most important to make this thing thread safe in presence of multithreaded/multiprocessing servers
        self.init_local_data()

        self.environ = environ
        self._start_response = start_response

        if not self._test_environ():
            return [b'']
        self._config_environ()

        self._init_session()

        self._init_args()

        response = None
        status_msg = None

        status_msg, response = self._try_static()
        if status_msg and response:
            self.logger.info(
                f"Proceeding from _try_static with status: {status_msg}")
            return self._send_response(status_msg, response)

        status_msg, response = self._try_cgi()
        if status_msg and response:
            self.logger.info(
                f"Proceeding from _try_cgi with status: {status_msg}")
            return self._send_response(status_msg, response)

        status_msg, response = self._try_default()
        if status_msg and response:
            self.logger.info(
                f"Proceeding from _try_default with status: {status_msg}")
            return self._send_response(status_msg, response)

        self._init_form()
        status_msg, response = self._try_routes()
        #if status_msg and response and re.match(r"^[25]", status_msg):
        if status_msg and response:
            self.logger.info(f"Proceeding from _try_routes with status: {status_msg}")
            return self._send_response(status_msg, response)

        status_msg, response = self._try_mounted()
        if status_msg and response:
            self.logger.info(
                f"Proceeding from _try_mounted with status: {status_msg}")
            return self._send_response(status_msg, response)

        status_msg, response = self._abort(404, self.environ.get('PATH_INFO'), " not found AT ALL.")
        return self._send_response(status_msg, response)

    def get_route_match(self, path):
        "Used by the app to match received path_info vs. saved route patterns"
        # path = path.replace(self.path_prefix, "") # Added to support mounted apps
        for route in self.routes:
            r = route.match(path)
            if r:
                return r
        return None

    def __str__(self):
        return f"{self.name} version {self.version}"

    @staticmethod
    def get_normalize_css() -> str:
        return """
        html {
                line-height: 1.15; /* 1 */
                -webkit-text-size-adjust: 100%; /* 2 */
        }
        body {
                margin: 0;
        }
        h1 {
                font-size: 2em;
                margin: 0.67em 0;
        }
        hr {
                box-sizing: content-box; /* 1 */
                height: 0; /* 1 */
                overflow: visible; /* 2 */
        }
        pre {
                font-family: monospace, monospace; /* 1 */
                font-size: 1em; /* 2 */
        }
        a {
                background-color: transparent;
        }
        abbr[title] {
                border-bottom: none; /* 1 */
                text-decoration: underline; /* 2 */
                text-decoration: underline dotted; /* 2 */
        }
        b, strong {
                font-weight: bolder;
        }
        code,
        kbd,
        samp {
                font-family: monospace, monospace; /* 1 */
                font-size: 1em; /* 2 */
        }
        small {
                font-size: 80%;
        }
        sub,
        sup {
                font-size: 75%;
                line-height: 0;
                position: relative;
                vertical-align: baseline;
        }
        sub {
                bottom: -0.25em;
        }
        sup {
                top: -0.5em;
        }
        img {
                 border-style: none;
        }
        button,
        input,
        optgroup,
        select,
        textarea {
                font-family: inherit; /* 1 */
                font-size: 100%; /* 1 */
                line-height: 1.15; /* 1 */
                margin: 0; /* 2 */
        }
        button,
        input { /* 1 */
                overflow: visible;
        }
        button,
        select { /* 1 */
                text-transform: none;
        }
        button,
        [type="button"],
        [type="reset"],
        [type="submit"] {
                -webkit-appearance: button;
        }
        button::-moz-focus-inner,
        [type="button"]::-moz-focus-inner,
        [type="reset"]::-moz-focus-inner,
        [type="submit"]::-moz-focus-inner {
                border-style: none;
                padding: 0;
        }
        button:-moz-focusring,
        [type="button"]:-moz-focusring,
        [type="reset"]:-moz-focusring,
        [type="submit"]:-moz-focusring {
                outline: 1px dotted ButtonText;
        }
        fieldset {
                padding: 0.35em 0.75em 0.625em;
        }
        legend {
                box-sizing: border-box; /* 1 */
                color: inherit; /* 2 */
                display: table; /* 1 */
                max-width: 100%; /* 1 */
                padding: 0; /* 3 */
                white-space: normal; /* 1 */
        }
        progress {
                vertical-align: baseline;
        }
        textarea {
                overflow: auto;
        }
        [type="checkbox"],
        [type="radio"] {
                box-sizing: border-box; /* 1 */
                padding: 0; /* 2 */
        }
        [type="number"]::-webkit-inner-spin-button,
        [type="number"]::-webkit-outer-spin-button {
                height: auto;
        }
        [type="search"] {
                -webkit-appearance: textfield; /* 1 */
                outline-offset: -2px; /* 2 */
        }
        [type="search"]::-webkit-search-decoration {
                -webkit-appearance: none;
        }
        ::-webkit-file-upload-button {
                -webkit-appearance: button; /* 1 */
                font: inherit; /* 2 */
        }
        details {
                display: block;
        }
        summary {
                display: list-item;
        }
        template {
                display: none;
        }
        [hidden] {
                display: none;
        }
        """

    @staticmethod
    def get_demo_css() -> str:
        style = """
                    body {
                        /* font-family: Helvetica; */
                        font-family: Helvetica, Arial, sans-serif;
                        /*
                           font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
                        */
                        padding: 0.5em;
                    }
                    a {
                        text-decoration: none;
                        color: steelblue;
                        font-weight: bold;
                    }
                    
                    a:hover {
                        color: navy;
                    }
                    
                    .steelblue {
                        color: steelblue;
                    }
                    .red {
                        color: #aa0000;
                    }
                    .green {
                        color: #00aa00;
                    }
                    .centered {
                        text-align: center;
                    }
                    .wrapped {
                        display: flex;
                        flex-wrap: wrap;
                        word-break: break-all;
                        word-wrap: break-word;
                        width: 80%;
                        max-width: 80%;
                        min-width: 80%;
                        padding: 10px;
                        margin-left: 10%;
                        border: solid 1px steelblue;
                        border-radius: 5px;
                    }
                    .panel {
                       display: flex;
                       flex-direction: column;
                       padding: 5px;
                       border: solid 1px steelblue;
                       border-radius: 5px;
                    }
                    .w33 {
                       width: 33%;
                       /* max-width: 33%; */
                       min-width: 33%;
                       margin-left: 33%;
                    }
                    .w40 {
                       width: 40%;
                       /* max-width: 40%; */
                       min-width: 40%;
                       margin-left: 30%;
                    }
                    .w50 {
                       width: 50%;
                       /* max-width: 50%; */
                       min-width: 50%;
                       margin-left: 25%;
                    }
                    .w60 {
                       width: 60%;
                       /* max-width: 60%; */
                       min-width: 60%;
                       margin-left: 20%;
                    }
                    .w80 {
                       width: 80%;
                       /* max-width: 80%; */
                       min-width: 80%;
                       margin-left: 10%;
                    }
                    .row {
                      display: flex;
                      flex-direction: row;
                      justify-content: space-between;
                      padding-right: 1em;
                      padding-left: 1em;
                      padding-top: 10px;
                      padding-bottom: 10px;
                      align-items: center;
                      margin-bottom: 10px;
                    }
                """
        return style

    @staticmethod
    def get_demo_prefix() -> str:
        return """
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="utf-8">
                    <title>Bicchiere Demo App</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=yes">
                    <!--[if lt IE 9]><script src="js/html5shiv-printshiv.js" media="all"></script><![endif]-->
                    <link rel="icon" href="/static/img/bicchiere-rosso-2.png" type="image/x-icon" />
                    <style>
                      {normalize_css}
                    </style>
                    <style>
                      {demo_css}
                    </style>
                </head>
                <body>
        """

    @staticmethod
    def get_demo_suffix() -> str:
        return """
                     <hr/>
                     <h2 class="centered steelblue">Demo Links</h2>
                     <hr/>
                     <section>
                       <h3 class="red">General</h3>
                       <p><a href="/">Home, sweet home...</a></p>
                       <p>
                          <form action="/hello" method="GET">
                          <a href="/hello">Demo Hello Page (what you write after /hello will be greeted)</a>
                          &nbsp;&nbsp;
                          <span>By the way, you are...</span>
                          &nbsp;&nbsp;
                          <input style="display: inline; width: 20em;" type="text" name="who" />
                          </form>
                       </p>
                       <p><a href="/environ">HTTP and WSGI variables</a></p>
                       <p><a href="/upload">Upload example</a></p>
                       <p>
                         <form method="POST" action="/factorial">
                           <label>Number:&nbsp;</label>
                           <input type="number" value="10" required name="number" />
                           &nbsp;
                           <input type="submit" value="Factorial" />
                         </form>
                       </p>
                     </section>
                     <hr/>
                     <section>
                       <h3 class="red">Session and Cookies variables</h3>
                       <p><a href="/showsession">Session Variables</a></p>
                       <p><a href="/showcookies">Cookies</a></p>
                     </section>
                     <hr/>
                     <section>
                       <h3 class="red">Redirection Examples</h3>
                       <p><a href="/f42">Number 42 factorial</a></p>
                       <p><a href="/python">Where all this began: Python!</a></p>
                       <p><a href="/python_it">Where all this began: Python! (Italian version)</a></p>
                       <p><a href="/wsgiwiki">WSGI (Web Server Gateway Interface, the tech behind Bicchiere) Wikipedia page</a></p>
                       <p><a href="/wsgisecret">WSGI Python secret web weapon (Part I)</a></p>
                       <p><a href="/wsgisecret2">WSGI Python secret web weapon (Part II)</a></p>
                     </section>
                     <hr/>
                     <section>
                       <h3 class="red">Static Content Example</h3>
                       <p><a href="/showstatic">Show '/static' directory</a></p>
                     </section>
                     <hr/>
          </body>
        </html>
        """

    @staticmethod
    def get_demo_content():
        return """
        <h1 class="centered steelblue">{heading}</h1>
        <div class="container">
           {contents}
        </div>
        """

    # @staticmethod
    # def group_capitalize(stri):
    #    return  ' '.join(list(map(lambda w: w.capitalize(), re.split(r'\s+', stri))))

    @staticmethod
    def get_favicon():
        favicon = 'data:image/jpg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBwcGBwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCABoAE8DASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD98AeFoB5/OnDovH60Dr09e9ADQeKCeKcOnT9aD06frQA3PP40Z+T8Kd36d/Wj+Dp29aAG5oJ4p34frQenT9aAG55/GgHind+nf1oHTp+tAACcLQCc/nTB0WgdfzoA868TfHfUPC3xRvPDtx4ft44Vt4ruwu5tTMZ1OFsLK6IIjjyZSEddxYCSJsYcY8f+K3/BSu7+E3jaXRb/AOHrSMo3LMmugK4+hgzXsX7THwfvvi78MLqHw/eWuj+NdLSS78NatLbxzf2de7GVch1YeXIpMb/KfkckcgEfi3+1r/wVq+LHiL4ZWYXw7p3hf4jeCL5/D/i2K50yyuWF0hZCwSS3bZlk6ZIznHGK8vMMwjhVepe26sl80foHBvBOL4jqcmXQjJxaUk5NNX2lbdp2tpe0tLJNH6peAP8AgpBZ+Nztk8LiwfsH1bfn8oqZrn/BRhtKv5LePwYtwEON39t7c/h5FfhJo3/Bb79orwZcf6L4g0aybdn934Z0tOPT/j2qrqX/AAW9/aC1K58ybxFoL55bPhfSyzH6/Zv5V464qw7Stzfcv8z77/iAueQqvn9lbs5zuv8AyQ/e7wv+37qXizVorO1+H+ZJWCg/26Dj/wAgV3fwW/aYufjL8XfFnhmDwxcWtn4Ljgh1HWFvPOs/t8oD/YY8orPLHEVeQj5U8yMcliB+NX7EX/BS748fFG902PS4NH1jxZ401MeHvC9i+k2UMTXLgmS7kKW4byYIw8rnOAqGv22+APwV039n/wCFem+GdNZbhrbdcX175Qjk1S9lYyXN3IBxvllZ3IHAyFGAAB7WX45Ypc0U7LvY/OOLuE6uQVPYYxR55L3VGTeiesne3or7u/Y7bJz+NAJxTO/40o6V6R8QALYWgFs/nShuF60Bue/egAG4r/8AWr8nv+C7P7DsfhP4jp8ZNCsf+JH48hXw542hiXCwXW3FlqJAyc5AjYgdUTu5z+sQbjvXOfF34Y6R8avhrrXhTXoPtGk67ava3C91B+66+jKwVlPYqDXHjsLHEUXTfy9T7LgPi6tw3nVLM6d3FO01/NB2uvVaSj/eSZ/JJ458IyaTeSRyZ3RuY2z2IOK5/QPBd14t8S2OlWUbSXmoTpbxKB1ZmAH86+y/+Cl/7HXiD9mz4sasmqWjSadNdvAl9FE3ktcIAWQkjAZ0ZJQvdZAR3xk/8Emv2OdQ/a1/aVtdOspZrSFGMEt7GvzWMJXNzcA9mSEsqZ/5azQ+9fjOBpVJYt4JbqVv6+R/pRxVm2TrJo8TUqieHnT9pdO/TVd730P07/4IJ/sQ23hbRpvi5qVqptre0k8MeCUdB8tojgX+ogf3rq4Qxo33vJg6kSV+lpLYrM8E+EdL+Hng/S9A0Wzi03R9EtIrCxtIhiO2giQJHGvsqqB+FahbjvX7Rg8LHD0lSj/TP8xuKuIq+d5nVzGv9p6L+WK2XyW/d3fUbls/jSgtijdz360objvXUfPDR0X71A6/xd6AvC8frQF56evegBR0/ioPT+KgLx0/Wgrx0/WgD4i/4LE/scWP7S/wr1qTUtY1KxttF8O3viGytbcfu59QsY+A/vLDMEyOQIM88g+R/wDBsV+y1N8MP2VfEnj/AFiwa11nxdrd1ZWqySea8VpbybGIbA4kkUZAA/1C9a+yf+Cg9pcH9nW8uLbavk3AgnYjJ8m4iktnH4+ap/AVo/sBeDV8DfsWfDWxCKrSaFBeuF6b7jNw36ymvNjl9COLeIjFczWr+5H2FTijHyyBZTKq3RUtI9FrzP8AG3lq+up7AM4/ipD0/ipdvt+tIV46frXpHx4nf+LrSjp/FSbeenf1pQvHT9aAEAbC0ANn86AOFoA5/OgBQGxQQ2KQDigjigDw7/gpRqcmifsRePLyP/WWsNpMOem28gP+Nei/AXTDo3wM8F2fT7JoFhDj0220Y/pXj3/BXDU20T/gnJ8VrpeGi0uHH1N1AP61734PtvsfhDSoQuBDYwpgdsRqKz/5efI7JNfVUv7z/KJqYakIbFJigjitDjDDZ/GlAbFJjn8aAOKAFCcL0oCc9u9AHC8mgDnqe9ACheO1JtyOn6Guf+ITeIk0OT/hHDZ/bijBDcjKqxHBI74POK+Q/id4f/aIutMuLXVfC+va/BNKXkuPDnjk2LFT2ELwgbf9jPHqetTKVjqoYdVFdyS/M9H/AOCufhe4+JP7AXxE8H6ZrHh/Rdf8SWUMVhNrFw8FohS5ilZpWRXZE2xsNxUjcVB61794B1218VeCtLvrGaO6tri0iZXTPeNTgg4Kn2IBHcCvgvwH4B/4Vj4V16EfB/4mWupatpFzY3l3fzWl1dTmRW2ss804UFWIZQoJ3DIxWLqnwv17Xb221DT/AIX/ABruvE2Y5JNStdWtNNaYiFECyPE7Rt93Jk5YnNZ83vXO+WHpOmqKb0bd7Lqktr+Xf5H6TYoKcdq+QPhZZftEfbdHxoN94fsbMBLk694vXWJrlM85RIFXfjjO/jPevqnwidWbSI/7Y8kXnG4RfdrSMr9DgxGHVPVST9DV2c9utKE47UmOep60oHHU1RyjR0XpQOvbvRRQADp2oJIHaiigDD+JvhmTxl4E1LS45preS8iCLJFIUdDuHII5HGRx61sWsRt7OKPoI41XHpgYoooHzO1iU80h6dqKKBB37daB07UUUAf/2Q=='
        return favicon

    @staticmethod
    def get_img_favicon():
        return f'<img src="{Bicchiere.get_favicon()}" alt="favicon.ico" title="favicon"/>'

# End of static stuff

    def default_handler(self):
        del self.headers['content-type']
        self.headers.add_header('Content-Type', 'text/html', charset="utf-8")
        # self.set_new_start_response()

        final_response = []
        final_response.append("""
       <!doctype html>
       <html lang=it>
         <head>
           <link rel="icon" href="/static/img/bicchiere-rosso-2.png" type="image/x-icon" />
           <title>Bicchiere Environment Vars</title>
         </head>
         <body style="color: blue; font-family: Helvetica; padding: 0.5em;">\n
       """)

        #response = simple_demo_app(self.environ, self.start_response)
        response = simple_demo_app(self.environ, lambda *args, **kw: None)

        for line in response:
            line = line.decode("utf-8").replace(
                '\n', '<br/><br/>\n').replace(
                'Hello world!',
                '''
              <a style="text-decoration: none; color: steelblue;" href="/" title="Home">
                <h2>Ciao, Mondo Bicchiere!</h2>
              </a>
              <h1 style="color: red; text-align: center;">
                WSGI Environment Variables
              </h1>
           ''')
            final_response.append("<p>{0}</p>".format(line))

        final_response.append("</body></html>")
        final_response = "".join(final_response)

        #self.debug(f"Yielding final response from Bicchiere default_handler: {final_response[ : 30]} ...")
        #self.start_response("200 OK", self.headers.items())
        return final_response

    @classmethod
    def register_template_filter(cls, filter_name: str, filter_func):
        # or (filter_func.__class__.__name__ != "function"):
        if (not isinstance(filter_name, str)):
            return False
        else:
            cls.template_filters[filter_name] = filter_func
            return True

    @classmethod
    def unregister_template_filter(cls, filter_name: str):
        if filter_name in cls.template_filters:
            del cls.template_filters[filter_name]
            return True
        else:
            return False

    @classmethod
    def tre_stanze(cls):
        acasa = cls("Casa")
        acocina = cls("Cocina")
        acomedor = cls("Comedor")

        #acasa.config.debug = True
        #acasa.mount("/cocina", acocina)
        #acasa.mount("/comedor", acomedor)

        @acasa.get("/")
        def casa():
            return "Esta es la casa."

        @acocina.get("/")
        def cocina():
            return "Esta es la cocina."

        @acocina.get("/show")
        def cocina():
            return "<h1>Vi mostro la cucina</h1>"

        @acomedor.get("/")
        def comedor():
            return "Este es el comedor."

        return acasa, acocina, acomedor

    @classmethod
    def demo_app(cls):

        is_local = "ernesto" in os.getcwd()
        bevanda = random.choice(cls.bevande)
        FileSession.secret = "20181209"
        app = cls(f"Demo {bevanda} App")
        app.config.debug = False
        app.config.allow_directory_listing = True
        app.config.session_class = FileSession
        if is_local:
            try:
                #from oven.mount_test import cocina, comedor, casa
                acasa, acocina, acomedor = cls.tre_stanze()
                app.mount("/cocina", acocina)
                app.mount("/comedor", acomedor)
                app.mount("/casa", acasa)
            except:
                pass

        #app.config.debug = True

        # prefix = Bicchiere.get_demo_prefix().format(normalize_css = Bicchiere.get_normalize_css(),
        #        demo_css = Bicchiere.get_demo_css())
        #suffix = Bicchiere.get_demo_suffix()

        # Demo page template includes 3 placeholders: 'page_title', 'menu_content' and 'main_contents'
        demo_page_template = chr(10).join([
            header_prefix_html,
            body_style,
            fontawesome_style,
            menu_style,
            """
              <style>
                {}
              </style>
            """.format(Bicchiere.get_demo_css()),
            header_suffix_html,
            body_prefix_html,
            "{{ main_contents }}",
            body_suffix_html
        ])

        menu = MenuBuilder()

        menu.addItem(MenuItem("Home", "/"))

        dropdown = DropdownMenu("Miscelaneous")
        dropdown.addItem(MenuItem("Hello Page", "/hello"))
        dropdown.addItem(MenuItem("HTTP and WSGI variables", "/environ"))
        dropdown.addItem(MenuItem("Upload example", "/upload"))
        dropdown.addItem(MenuItem("CGI examples", "/cgi"))
        dropdown.addItem(MenuItem("Favicon - Text Mode", "/favicon.ico"))
        dropdown.addItem(MenuItem("Favicon - Image", "/img/favicon.ico"))
        menu.addItem(dropdown)

        dropdown = DropdownMenu("Session variables and cookies")
        dropdown.addItem(MenuItem("Session variables", "/showsession"))
        dropdown.addItem(MenuItem("Cookies", "/showcookies"))
        menu.addItem(dropdown)

        dropdown = DropdownMenu("Redirection Examples")
        dropdown.addItem(MenuItem("Factorial of 42", "/f42"))
        dropdown.addItem(
            MenuItem("The origin of everything: Python!", "/python"))
        dropdown.addItem(MenuItem("Python per noi...", "/python_it"))
        dropdown.addItem(MenuItem(
            "WSGI (Web Server Gateway Interface, the tech behind Bicchiere) Wikipedia page", "/wsgiwiki"))
        dropdown.addItem(
            MenuItem("WSGI Python secret web weapon (Part I)", "/wsgisecret"))
        dropdown.addItem(
            MenuItem("WSGI Python secret web weapon (Part II)", "/wsgisecret2"))
        menu.addItem(dropdown)

        dropdown = DropdownMenu("Static Content Example")
        dropdown.addItem(MenuItem("Show '/static' directory", "/showstatic"))
        menu.addItem(dropdown)

        dropdown = DropdownMenu("Downloads")
        dropdown.addItem(
            MenuItem("Chat Room Websockets Example App - gevent version", "/downlchatroom?version=gevent"))
        dropdown.addItem(
            MenuItem("Chat Room Websockets Example App - Bicchiere Websocket version", "/downlchatroom?version=native"))

        dropdown = DropdownMenu("WebSocket")
        dropdown.addItem(
            MenuItem("Echo Server Example", "/echo"))

        menu.addItem(dropdown)
        menu.addItem(MenuItem("About", "/about"))

        @app.get("/cgi")
        def cgi():
            retval = """
            <hr>
            <div style="display: flex; flex-direction: row:">
            <div style="width: 50%; min-width: 50%; padding-left: 2em;">
            """
            for f in os.listdir("cgi-bin"):
                retval += f'<p><a href="/cgi-bin/{f}">{f}</a></p>'
            retval += '</div><div style="width: 25%; min-width: 25%; padding-left: 2em;">'
            retval += """
                    <h2 style="text-align: center;">CGI Form</h2>
                    <form action="/cgi-bin/cgiform.py", method="POST">
                        <p style="text-align: right;"><label>Name  </label><input type="text" name="username" required /></p>
                        <p style="text-align: right;"><label>Password  </label><input type="password" name="passwd" required /></p>
                        <p style="text-align: right"><input type="reset" value="Reset" />&nbsp;&nbsp;<input type="submit" value="Submit to /cgi-bin/cgiform.py" /></p>
                    </form>
                    </div>
                </div>
                <hr>
                <p style="text-align: center;">
                  <a href=\"/\" style=\"text-decoration: none; color:steelblue;\">Home</a>
                </p>
                """
            heading = f"CGI Tests"
            info = Bicchiere.get_demo_content().format(heading=heading, contents=retval)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Hello Page",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get("/echo/wstest")
        @app.websocket_handler
        async def wstest():
            wsock = app.environ.get("wsgi.websocket")
            if not wsock:
                return "Something went awry, no websocket :-(( "
            else:
                app.debug("Got a shiny new websocket!")

            def do_hb():
                while True:
                    try:
                        sleep(1)
                        wsock.heartbeat()
                    except Exception as exc:
                        app.debug(
                            f"Exception ocurred during heartbeat loop: {repr(exc)}")
                        return

            def pong_handler(evt):
                current_millis = Bicchiere.millis()
                prev_millis = int(evt.data)
                roundtrip = current_millis - prev_millis
                logger.info(
                    f"Received PONG frame with payload: {prev_millis} milliseconds, implying a roundtrip of {roundtrip} milliseconds.")
            wsock.onpong += pong_handler

            def message_handler(evt):
                #data = wsock.receive()
                data = evt.data.decode("utf-8")
                if data != None:
                    for i in range(1, 2):
                        dt = datetime.now()
                        sdate = dt.strftime("%Y-%m-%d %H:%M:%S")
                        msg = f"\tECHO at ({sdate}):\t{repr(data)}"
                        app.logger.info(msg)
                        wsock.send(msg)
                        # sleep(2)
            wsock.onmessage += message_handler

            try:
                wsock.send("Ciao, straniero!")
                hbt = threading.Thread(
                    target=do_hb, name="h_b_thread", args=())
                hbt.setDaemon(True)
                hbt.start()
            except WebSocketError as wserr:
                app.debug(f"WebSocketError: {repr(wserr)}")
                return b''
            except Exception as exc:
                app.debug(f"{exc.__class__.__name__}: {repr(exc)}")
                return b''
            while True:
                try:
                    wsock.receive()
                except WebSocketError as wserr:
                    app.debug(f"WebSocketError: {repr(wserr)}")
                    break
                except Exception as exc:
                    app.debug(f"{exc.__class__.__name__}: {repr(exc)}")
                    break

            return b''

        @app.get("/")
        def home():
            # randomcolor = random.choice(
            #    ['red', 'blue', 'green', 'green', 'green', 'steelblue', 'navy', 'brown', '#990000'])
            heading = "WSGI, Bicchiere Flavor"
            #url = "https://pypi.org/project/bicchiere/"
            #inner_contents = urllib.request.urlopen(url).read().decode()
            # contents = """
            # <iframe
            #   style="scroll = auto; height: 30em; min-height: 30em; width: 100%; min-width: 100%; border: none; background: white;"
            #   src="https://pypi.org/project/bicchiere/"
            # />
            # """
            inner_contents = """
          <div class="project-description" style="padding: 1em; padding-bottom: 2em;">
<p align=center><img src="https://warehouse-camo.ingress.cmh1.psfhosted.org/71d9fac8780e8e001faaab7589244d9f1b8ba56e/68747470733a2f2f6269636368696572652e73797465732e6e65742f7374617469632f696d672f6269636368696572652d726f73736f2d322e6a7067" alt="Bicchiere Logo"></p>
<h2>Yet another Python web (WSGI) micro-framework</h2>
<p>Following <a href="https://flask.palletsprojects.com/en/2.1.x/" rel=nofollow>Flask</a> and <a href="https://bottlepy.org/docs/dev/" rel=nofollow>Bottle</a> footsteps, adding a bit of italian flavor :-)</p>
<h2>Install</h2>
<pre lang=bash>pip install bicchiere
</pre>
<h2><a href="https://bicchiere.sytes.net" rel=nofollow>Project Demo App</a></h2>
<p>
    <a href="https://pypi.python.org/pypi/bicchiere" rel=nofollow><img alt="GitHub tag (latest by date)" src="https://warehouse-camo.ingress.cmh1.psfhosted.org/513b792130833b398f24fb529aa8e3f5913d3a50/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f762f7461672f73616e647939382f6269636368696572653f636f6c6f723d253233306363303030266c6162656c3d626963636869657265"></a>           
       
    <a href="https://pepy.tech/project/bicchiere" rel=nofollow>
        <img src="https://warehouse-camo.ingress.cmh1.psfhosted.org/3b92fa3bf75d67905050c519d1027d52af3da3b4/68747470733a2f2f7374617469632e706570792e746563682f706572736f6e616c697a65642d62616467652f6269636368696572653f706572696f643d746f74616c26756e6974733d696e7465726e6174696f6e616c5f73797374656d266c6566745f636f6c6f723d626c61636b2672696768745f636f6c6f723d626c7565266c6566745f746578743d446f776e6c6f616473">
    </a>
</p>
<h2>A drop from Bicchiere</h2>
<pre lang=python3 style="background: #eeeeee; padding: 8px;"><span class=kn>from</span> <span class=nn>bicchiere</span> <span class=kn>import</span> <span class=n>Bicchiere</span>

<span class=n>app</span> <span class=o>=</span> <span class=n>Bicchiere</span><span class=p>()</span>
<span class=ow>or</span>
<span class=n>app</span> <span class=o>=</span> <span class=n>Bicchiere</span><span class=p>(</span><span class=s2>"La mia bella App"</span><span class=p>)</span>

<span class=nd>@app</span><span class=o>.</span><span class=n>get</span><span class=p>(</span><span class=s2>"/"</span><span class=p>)</span>
<span class=k>def</span> <span class=nf>home</span><span class=p>():</span>
    <span class=k>return</span> <span class=s2>"Bon giorno, cosa bevete oggi?"</span>
    
<span class=k>if</span> <span class=vm>__name__</span> <span class=o>==</span> <span class=s2>"__main__"</span><span class=p>:</span>
    <span class=c1>#This will run default server on http://localhost:8086</span>
    <span class=n>app</span><span class=o>.</span><span class=n>run</span><span class=p>()</span>
</pre>
<p>... and this is just about the classical WSGI <strong>Hello, World</strong>, for everything else please refer to <a href="https://github.com/sandy98/bicchiere/wiki" rel=nofollow>Bicchiere Wiki</a></p>
<p>Well... not really. A bit of rationale is in order here.</p>
<p>So, why Bicchiere?</p>
<ul>
<li>
<p>For one thing, reinventing the wheel is not only fun but highly educational, so, by all means, do it!</p>
</li>
<li>
<p>I like Flask and Bottle. A lot. Both have things that I highly appreciate, simplicity in the first
place. But it doesn't end there.</p>
</li>
<li>
<p>There's also the single file/no dependencies approach (Bottle), which I intend to mimic with Bicchiere. Although not a   mandatory thing, I like  it that way.</p>
</li>
<li>
<p>Built-in sessions (Flask). Although the user of the library must be free to choose whatever he likes regarding sessions or any other component of the application for that matter, I think session-handling is one of those must-have things in any web app these days. So, I provided basic session handling mechanism, in 3 flavors: memory, filesystem, and sqlite. This was the most that could be done without falling out of the boundaries of the Python Standard Library. Details on this at <a href="https://github.com/sandy98/bicchiere/wiki/Bicchiere-session" rel=nofollow>the wiki (under construction)</a></p>
</li>
<li>
<p>Built-in templating mechanism (Bottle). Similar considerations apply. In my opinion, this is also a must have, regardless how micro is the framework/library. Then again, end-user must be free to choose. As a good WSGI compliant middleware, Bicchiere doesn't come in the way of the user if he prefers to use <a href="https://www.makotemplates.org/" rel=nofollow>Mako</a>, <a href="https://jinja.palletsprojects.com/en/3.1.x/" rel=nofollow>Jinja2</a>, <a href="https://genshi.edgewall.org/" rel=nofollow>Genshi</a> or whatever he likes. Details at <a href="https://github.com/sandy98/bicchiere/wiki/Bicchiere-templates" rel=nofollow>the wiki (under construction)</a></p>
</li>
<li>
<p>WebSockets handling: to me, this is the fruit on the cake, for various reasons:</p>
<ol>
<li>It's been said that it can't be done under WSGI, reason the more to do it.</li>
<li>Real time communication looks like another must have in the current landscape of web app development</li>
<li>Then again, its a lot of fun. A lot of pain, too...
In any case, Bicchiere comes bundled with native WebSocket support - just taken out from the oven :-))
Details at <a href="https://github.com/sandy98/bicchiere/wiki/Bicchiere-Websocket" rel=nofollow>the wiki (under construction)</a> . Regretably, <a href="https://bicchiere.eu.pythonanywhere.com" rel=nofollow>the original Demo App</a> won't work with websockets, because <strong>Pythonanywhere</strong> hasn't yet implemented the feature. As of now, there's a mirror at <a href="http://bicchiere.sytes.net" rel=nofollow>bicchiere.sytes.net</a> which works fine, test at the home page and all. In any case, these issues are related to reverse proxy configuration and have nothing to see with the app/library itself.</li>
</ol>
</li>
<li>
<p>And still, there's a lot of stuff to be mentioned. More to come...</p>
</li>
</ul>

          </div>            
            """
            contents = """
            <div
              id = "pypi-contents"
              style="scroll = auto; height: 30em; min-height: 30em; width: 100%; min-width: 100%; border: none; background: white;" 
            >
            {}
            </div>
            """.format(inner_contents)
            info = Bicchiere.get_demo_content().format(heading=heading, contents=contents)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Echo Server",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get('/echo')
        # @app.html_content()
        def echo():
            randomcolor = random.choice(
                ['red', 'blue', 'green', 'green', 'green', 'steelblue', 'navy', 'brown', '#990000'])
            heading = "Bicchiere WebSocket Test - Simple Echo Server"
            onkeyup = """
               txt_chat.addEventListener("keyup", function(ev) {
                 if (ev.keyCode != 13 || !ev.target.value.length || myws.readyState != 1)
                   return false;
                 myws.send(ev.target.value);
                 ev.target.value = "";
                 ev.target.focus();
                 return true;
               });
            """
            print_msg = """
               function print_msg(msg) {
                while (chat_msgs.childElementCount > 7)
                  chat_msgs.removeChild(chat_msgs.firstChild);
                var p = document.createElement("p");
                p.innerText = msg;
                p.style.padding = "3px" 
                p.style.height = "1em"
                chat_msgs.appendChild(p);
                document.body.scrollTop = document.body.scrollHeight;
               }
            """
            onmessage = """
               myws.onmessage = function(ev) {
                console.log("RECEIVED: " + ev.data ? ev.data : ev);
                print_msg(ev.data ? ev.data : ev);
               }
            """
            contents = '''
            <br>
            <hr>
            <div id="chat_send">
              <label for="txt_chat">Send message to Bicchiere echo server</label>
              &nbsp;
              <input type="text" name="txt_chat" id="txt_chat" style="height: 1.5em; margin-top: 10px; width: 50%; max-width: 50%; min-width: 80%;"/>
            </div>
            <div id="chat_msgs" style="background: black; color: white;">
            </div>
            <script>
               var txt_chat = document.getElementById("txt_chat");
               var chat_msgs = document.getElementById("chat_msgs");
               {0}
               {1}
               var myws = new WebSocket(location.href.replace("http", "ws") + "/wstest")
               myws.onopen = ev => console.log("My beautiful websocket is open! : " + ev.data ? ev.data : ev)
               myws.onerror = ev => console.info(ev)
               myws.onclose = ev => console.log("Websocket is now closing :-( " + ev.data ? ev.data : ev)
               {2}
               if (location.href.indexOf("pythonanywhere") > -1)
                 //alert("Regretably websockets do not work in Pythonanywhere, so webchat functionality will not be available. Suggestion is installing the app and trying it locally, or in any websocket compliant server.");
                 location.href = location.href.replace("eu.pythonanywhere.com", "sytes.net");
            </script>
            '''
            contents = contents.format(onkeyup, print_msg, onmessage)
            info = Bicchiere.get_demo_content().format(heading=heading, contents=contents)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Echo Server",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get('/favicon.ico')
        @app.html_content()
        def favicon():
            info = f"""
            <p>{Bicchiere.get_favicon()}</p>
            <p><a href="/">Home</a></p>
            """
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Favicon source",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get('/img/favicon.ico')
        @app.html_content()
        def favicon_img():
            info = f"""
            <p>{Bicchiere.get_img_favicon()}</p>
            <p><a href="/">Home</a></p>
            """
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Favicon source",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.route("/upload", methods=['GET', 'POST'])
        def upload():
            pinfo = "Arriverà presto..."
            if app.environ.get('request_method'.upper()) == 'GET':
                pinfo = """
                        <div class="panel w40">
                          <form action="/upload" method="POST" enctype="multipart/form-data">
                            <div class="row">
                               <label class="steelblue">Description</label>
                               <input type="text" name="description" />
                            </div>
                            <div class="row">
                               <label class="steelblue">File</label>
                               <input type="file" name="archivo" />
                            </div>
                            <div class="row">
                               <input type="submit" value="Send" />
                               <input type="reset" value="Reset" />
                            </div>
                          </form>
                        </div>
                        """
            else:
                body = None
                body_len = 0
                filetype = None

                description = app.form['description'].value or '<span class="red">Non hai detto niente...</span>'
                archivo = app.form['archivo'].file
                filename = app.form['archivo'].filename or '<span class="red">Non hai scelto niente!</span>'
                if filename:
                    body = archivo.read()
                    body_len = len(body)
                    file_type = app.form['archivo'].type
                pinfo = """
                        <div class="panel w40">
                        """
                pinfo += f'<div class="row"><label class="steelblue">Description</label><strong>{description}</strong></div></hr>'
                pinfo += f'<div class="row"><label class="steelblue">Filename</label><strong>{filename}</strong></div></hr>'
                if filename:
                    pinfo += f'<div class="row"><label class="steelblue">File length</label><strong>{body_len} bytes</strong></div></hr>'
                    if "image" in file_type:
                        img_src = Bicchiere.encode_image(body, file_type)
                        pinfo += f'<div class="centered"><img src="{img_src}" style="max-width: 100%; height: auto;" /></div></hr>'
                    elif 'text' in file_type:
                        pinfo += f'<div class="centered"><textarea style="width=12em; height: 10em;">{body}</textarea></div></hr>'
                    else:
                        pinfo += f'<div class="row red">Unknown file type ({file_type}), can\'t show it. :-(</div>' if body_len else ''
                pinfo += '''
                         <form action="" method="GET">
                            <div class="centered"><input type="submit" value="Back" /></div>
                         </form>
                         '''
                pinfo += "</div>"

            heading = "Upload Example"
            info = Bicchiere.get_demo_content().format(heading=heading, contents=pinfo)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Upload example",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get("/hello")
        @app.get("/hello/<who>")
        @app.html_content()
        def hello(who=app.name):
            if who == app.name and 'who' in app.args and len(app.args.get('who', '')):
                who = app.args.get('who')
            heading = f"Benvenuto, {who.title()}!!!"
            info = Bicchiere.get_demo_content().format(heading=heading, contents="")
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Hello Page",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get("/downlchatroom")
        # @app.content_type('text/x-python')
        @app.custom_header("Content-Disposition", "attachment", filename="chat_room.py")
        def downlchatroom():
            version = app.args.get("version", "native")
            url = f"https://raw.githubusercontent.com/sandy98/bicchiere/main/oven/chat_room_{version}.py"
            try:
                contents = urllib.request.urlopen(url).read()
            except Exception as exc:
                app.debug(f"Exception downloading URL {url}: {repr(exc)}")
                raise exc
            return contents

        @app.get("/showstatic")
        def showstatic():
            heading = 'Static Contents'
            contents = '''
                <div class="w60 panel">
                  <iframe src="/static" style="min-height: 22em; height: 22em; padding: 1em; border: none;"></iframe>
                </div>
                      '''
            info = Bicchiere.get_demo_content().format(heading=heading, contents=contents)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Contents of static directory",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app._any("/factorial")
        @app._any("/factorial/<int:number>")
        @app.html_content()
        def factorial(number=7):
            if app.environ.get('REQUEST_METHOD') == 'GET':
                n = number
            else:
                try:
                    n = int(app.form['number'].value)
                except Exception as exc:
                    app.debug("Exception in factorial: {}".format(str(exc)))
                    n = number
            result = reduce(lambda a, b: a * b, range(1, n + 1))
            pinfo = f'<div class="wrapped">Factorial of {n} is: <br/>&nbsp;<br/>{result}</div>'
            info = Bicchiere.get_demo_content().format(
                heading="Factorials", contents=pinfo)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Factorial",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get('/environ')
        # @app.content_type("text/html")
        # @app.html_content()
        def env():
            contents = ''.join([x for x in app.default_handler()])
            info = Bicchiere.get_demo_content().format(heading="", contents=contents)
            #app.headers.add_header("Content-Type", "text/html", charset = "utf-8")
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Environment vars",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get("/f42")
        def f42():
            return app.redirect("/factorial/42")

        @app.get("/python")
        def wsgiwiki():
            return app.redirect("https://en.wikipedia.org/wiki/Python_(programming_language)")

        @app.get("/python_it")
        def wsgiwiki():
            return app.redirect("https://it.wikipedia.org/wiki/Python")

        @app.get("/wsgiwiki")
        def wsgiwiki():
            return app.redirect("https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface")

        @app.get("/wsgisecret")
        def wsgiwiki():
            return app.redirect("https://www.xml.com/pub/a/2006/09/27/introducing-wsgi-pythons-secret-web-weapon.html")

        @app.get("/wsgisecret2")
        def wsgiwiki():
            return app.redirect("https://www.xml.com/pub/a/2006/10/04/introducing-wsgi-pythons-secret-web-weapon-part-two.html")

        @app.post("/setacookie")
        def setacookie():
            app.debug(
                f"POST: cookie posteada!   -   {app.form['key']}={app.form['value']}")
            if app.form['key'].value.lower() == 'sid':
                raise KeyError(
                    "SID cannot be modified/deleted. It's meant only for internal use")
            cookie_opts = {}
            if app.form['value'].value:
                if app.form['max_age'].value:
                    cookie_opts['Max-Age'] = app.form['max_age'].value
            else:
                cookie_opts['Max-Age'] = '0'

            app.set_cookie(key=app.form['key'].value.strip(
            ),  value=app.form["value"].value.strip(), **cookie_opts)
            return app.redirect('/showcookies')

        @app.route("/showcookies", methods=['GET'])
        @app.html_content()
        def showcookies():
            contents = '<div class="w60 panel">'
            for k in app.cookies:
                contents += f'''<div class="row" style="border-bottom: solid 1px;">
                <span class="green">{k}&nbsp;:&nbsp;</span><span class="red">{app.cookies[k].value}</span>
                </div>'''
            contents += '''
                <div class="panel" style="border: none;">
                    <h3 class="centered steelblue">Set/Unset Cookie</h3>
                    <form action="/setacookie" method="POST">
                    <div class="row" style="margin-bottom: 12px"><label>Cookie key:&nbsp;</label>&nbsp;&nbsp;&nbsp;<input type="text" name="key" required /></div>
                    <div class="row" style="margin-bottom: 12px"><label>Cookie Value:&nbsp;</label>&nbsp;&nbsp;&nbsp;<input type="text" name="value" /></div>
                    <div class="row" style="margin-bottom: 12px"><label>Cookie Max. Age:&nbsp;</label>&nbsp;&nbsp;&nbsp;<input type="number" name="max_age" /></div>
                    <div class="row"><input type="submit" value="Submit" />&nbsp;&nbsp;&nbsp;<input type="reset" value="Reset" /></div>
                    </form>
                </div>
            '''
            info = Bicchiere.get_demo_content().format(
                heading="Cookies", contents=contents)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Cookies",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.route("/showsession", methods=["GET", "POST"])
        @app.html_content()
        def showsession():
            if app.environ.get('request_method'.upper(), 'GET').upper() == "POST":
                if app.form['key'].value.lower() == 'sid':
                    raise KeyError(
                        "SID cannot be modified/deleted. It's meant only for internal use")
                if app.form['value'].value:
                    app.session[app.form['key'].value] = app.form['value'].value
                else:
                    try:
                        del app.session[app.form['key'].value]
                    except:
                        pass

            contents = '<div class="w60 panel">'
            for k in app.session:
                contents += f'''<div class="row" style="border-bottom: solid 1px;">
                <span class="green">{k}&nbsp;:&nbsp;</span><span class="red">{app.session[k]}</span>
                </div>'''
            contents += '''
                <div class="panel" style="border: none;">
                  <h3 class="centered steelblue">Set/Unset Session vars</h3>
                  <form action="" method="POST">
                  <div class="row" style="margin-bottom: 12px"><label>Session key:&nbsp;</label>&nbsp;&nbsp;&nbsp;<input type="text" name="key" required /></div>
                  <div class="row" style="margin-bottom: 12px"><label>Value:&nbsp;</label>&nbsp;&nbsp;&nbsp;<input type="text" name="value" /></div>
                  <div class="row"><input type="submit" value="Submit" />&nbsp;&nbsp;&nbsp;<input type="reset" value="Reset" /></div>
                  </form>
                </div>
            '''
            contents += "</div>"
            info = Bicchiere.get_demo_content().format(
                heading="Session Data", contents=contents)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - Session vars",
                                             menu_content=str(menu),
                                             main_contents=info)

        @app.get("/about")
        def about():
            contents = """
            <hr>
            <p style="text-align: left;">
               <a href="https://pypi.python.org/pypi/bicchiere" target="_blank" rel="nofollow"><img alt="GitHub tag (latest by date)" src="https://img.shields.io/github/v/tag/sandy98/bicchiere?color=%230cc000&label=bicchiere"></a>           
                &nbsp;&nbsp;&nbsp;
               <a href="https://pepy.tech/project/bicchiere" rel="nofollow" target="_blank">
                  <img src="https://static.pepy.tech/personalized-badge/bicchiere?period=total&units=international_system&left_color=black&right_color=blue&left_text=Downloads"/>
               </a>
            </p>
            <hr>
            <p>
            Lorem ipsum dolor sit amet consectetur adipisicing elit. Maxime mollitia,
            molestiae quas vel sint commodi repudiandae consequuntur voluptatum laborum
            numquam blanditiis harum quisquam eius sed odit fugiat iusto fuga praesentium
            optio, eaque rerum! Provident similique accusantium nemo autem. Veritatis
            obcaecati tenetur iure eius earum ut molestias architecto voluptate aliquam
            nihil, eveniet aliquid culpa officia aut! Impedit sit sunt quaerat, odit,
            tenetur error, harum nesciunt ipsum debitis quas aliquid. Reprehenderit,
            quia. Quo neque error repudiandae fuga? Ipsa laudantium molestias eos 
            sapiente officiis modi at sunt excepturi expedita sint? Sed quibusdam
            recusandae alias error harum maxime adipisci amet laborum. Perspiciatis 
            minima nesciunt dolorem! Officiis iure rerum voluptates a cumque velit 
            quibusdam sed amet tempora. Sit laborum ab, eius fugit doloribus tenetur 
            fugiat, temporibus enim commodi iusto libero magni deleniti quod quam 
            consequuntur! Commodi minima excepturi repudiandae velit hic maxime
            doloremque. Quaerat provident commodi consectetur veniam similique ad 
            earum omnis ipsum saepe, voluptas, hic voluptates pariatur est explicabo 
            fugiat, dolorum eligendi quam cupiditate excepturi mollitia maiores labore 
            suscipit quas? Nulla, placeat. Voluptatem quaerat non architecto ab laudantium
            modi minima sunt esse temporibus sint culpa, recusandae aliquam numquam 
            totam ratione voluptas quod exercitationem fuga. Possimus quis earum veniam 
            quasi aliquam eligendi, placeat qui corporis!
            </p>
            <hr>
            <div>
               Version: @version@ 
            </div>
            <div>
               App Type: @apptype@ 
            </div>
            <hr>
            """.replace("@version@", app.version).replace("@apptype@", Bicchiere.config.get("apptype", "None"))
            info = Bicchiere.get_demo_content().format(
                heading="The proverbial about page", contents=contents)
            return Bicchiere.render_template(demo_page_template,
                                             page_title="Demo Bicchiere App - About page",
                                             menu_content=str(menu),
                                             main_contents=info)

        Bicchiere.config.apptype = "WSGI"
        return app

    @classmethod
    def get_version(cls):
        obj = cls()
        version = obj.version
        del obj
        return version

    def run(self, host="localhost", port=8086, app=None, server_name=None, **options):
        app = app or self
        server_name = server_name or ('asgiserver' if self.is_asgi(app) else 'bicchiereserver')
        orig_server_name = server_name
        server_name = server_name.lower()
        known_servers = self.known_asgi_servers if self.is_asgi(
            app) else self.known_wsgi_servers

        if server_name not in known_servers:
            self.debug(f"Server '{orig_server_name}' not known as of now. Switching to built-in BicchiereServer")
            #server_name = 'wsgiref'
            server_name = 'asgiserver' if Bicchiere.is_asgi(app) else 'bicchiereserver'

        server = None
        server_action = None

        if re.match(r"asgiserver", server_name):
            pass

        if re.match(r"w?hypercorn", server_name):
            #print(f"Server name matched {server_name}")
            try:
                from hypercorn.config import Config
                config = Config()
                config.bind = [f"{host}:{port}"]
                from hypercorn.asyncio import serve

                def server_action():
                    return asyncio.run(serve(app, config))
            except ImportError:
                print(
                    "Module 'hypercorn' not installed.\nRun 'python -m pip install hypercorn' prior to using this server.")
                os.sys.exit()
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start Waitress: {str(exc)}")
                os.sys.exit()

        if server_name == 'uvicorn':
            try:
                import uvicorn

                def server_action():
                    return uvicorn.run(app, host=f"{host}", port=port)
            except ImportError:
                print(
                    "Module 'uvicorn' not installed.\nRun 'python -m pip install uvicorn' prior to using this server.")
                os.sys.exit()
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start Uvicorn: {str(exc)}")
                os.sys.exit()

        if server_name == 'daphne':
            try:
                import daphne.server
                import daphne.cli
                dserver_version = daphne.__version__
                #app_asgi = build_asgi_i(application)
                #app_daphne = daphne.cli.ASGI3Middleware(application)
                dserver = daphne.server.Server(
                    app, endpoints=["tcp:port=%d:interface=%s" % (port, host)])

                def server_action():
                    return dserver.run()
            except ImportError:
                print(
                    "Module 'daphne' not installed.\nRun 'python -m pip install daphne' prior to using this server.")
                os.sys.exit()
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start Daphne: {repr(exc)}")
                os.sys.exit()

        if server_name == 'waitress':
            try:
                import waitress as server

                def server_action():
                    return server.serve(app, listen=f"{host}:{port}")
            except ImportError:
                print(
                    "Module 'waitress' not installed.\nRun 'python -m pip install waitress' prior to using this server.")
                os.sys.exit()
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start Waitress: {str(exc)}")
                os.sys.exit()

        if server_name == 'bjoern':
            try:
                import bjoern as server

                def server_action():
                    return server.run(app, host, port)
            except ImportError:
                print(
                    "Module 'bjoern' not installed.\nRun 'python -m pip install bjoern' prior to using this server.")
                os.sys.exit()
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start Bjoern: {str(exc)}")
                os.sys.exit()

        if server_name == 'gevent':
            try:
                from gevent.pywsgi import WSGIServer as GWSGIServer
                #from geventwebsocket import WebSocketError as GWebSocketError, websocket as GWebSocket
                #from geventwebsocket.handler import WebSocketHandler as GWebSocketHandler

                def server_action():
                    #app.config.websocket_class = GWebSocket
                    app.config.websocket_class = WebSocket
                    #server = GWSGIServer((host, port), application, handler_class=GWebSocketHandler)
                    server = GWSGIServer((host, port), app)
                    return server.serve_forever()
            except ImportError:
                print("Module 'gevent-websockets' not installed.\nRun 'python -m pip install gevent-websockets' prior to using this server.")
                os.sys.exit()
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start Bjoern: {str(exc)}")
                os.sys.exit()

        if server_name == 'uwsgi':
            try:
                os.system(
                    f"uwsgi --module=bicchiere:application --master --enable-threads --threads=9 --http={host}:{port} --processes=4")
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start uWSGI: {str(exc)}")
                os.sys.exit()

        if server_name == 'gunicorn':
            try:
                import gunicorn.app.base

                def server_action():
                    class StandaloneApplication(gunicorn.app.base.BaseApplication):

                        def __init__(self, app, options=None):
                            self.options = options or {}
                            self.application = app
                            super().__init__()

                        def load_config(self):
                            config = {key: value for key, value in self.options.items()
                                      if key in self.cfg.settings and value is not None}
                            for key, value in config.items():
                                self.cfg.set(key.lower(), value)

                        def load(self):
                            return self.application

                    options = {'workers': 4, 'bind': f'{host}:{port}',
                               'handler_class': BicchiereHandler, 'server_class': BicchiereServer}

                    server = StandaloneApplication(app, options)
                    return server.run()

            except ImportError:
                print(
                    "Module 'gunicorn' not installed.\nRun 'python -m pip install gunicorn' prior to using this server.")
                os.sys.exit()
            except Exception as exc:
                print(
                    f"Exception ocurred while trying to start Gunicorn: {str(exc)}")
                os.sys.exit()

        if server_name == 'wsgiref':
            #application.config['debug'] = True
            server = make_server(host, port, app, server_class=options.get(
                "server_class") or WSGIServer, handler_class=options.get("handler_class") or BicchiereHandler)
            server_action = server.serve_forever

        if server_name == 'bicchiereserver':
            #application.config['debug'] = True
            server = make_server(host, port, app, server_class=options.get(
                "server_class") or BicchiereServer, handler_class=options.get("handler_class") or BicchiereHandler)
            server_action = server.serve_forever

        if server_name == 'asgiserver':
            server = ASGIServer(host, port, app)
            def server_action():
                try:
                    asyncio.run(server.serve_forever())
                except KeyboardInterrupt:
                    print("\nServer quitting due to keyboard interrupt.\n")
                    sys.exit()
                except Exception as exc:
                    print(f"\nServer quitting due to {repr(exc)}.\n")
                    sys.exit(255)

        try:
            # server.serve_forever()
            stype = "ASGI" if Bicchiere.is_asgi(app) else "WSGI"
            appname = app.name if hasattr(app, "name") else app.__class__.__name__
            print("\n\n", f"Running Bicchiere {stype} ({appname}) version {Bicchiere.get_version()}",
                  f"using {(server_name or 'bicchiereserver').capitalize()}",
                  f"at {host}:{port if port else ''}")  # ,
            # f"\n Current working file: {os.path.abspath(__file__)}", "\n")
            server_action()
        except KeyboardInterrupt:
            print("\n\nBicchiere è uscito del palco...\n")
        except Exception as exc:
            print(
                f"\n\n{'-' * 12}\nUnexpected exception: {str(exc)}\n{'-' * 12}\n")
        finally:
            if hasattr(server, 'socket') and hasattr(server.socket, 'close'):
                try:
                    # if self.session_manager and self.session_manager.clock:
                    #    self.session_manager.clock.stop()
                    server.socket.close()
                    print("Socket chiuso.\n")
                except:
                    pass
            if hasattr(server, 'server_close'):
                try:
                    server.server_close()
                    print("Server chiuso (server_close).\n")
                except:
                    pass
            elif hasattr(server, 'close'):
                try:
                    server.close()
                    print("Server chiuso.\n")
                except:
                    pass
            print("\nBicchiere  è finito.\n")

# End main Bicchiere App class

# Miscelaneous exports


def demo_app():
    "Returns demo app for test purposes"
    return Bicchiere.demo_app()


application = demo_app()  # Rende uWSGI felice :-)


def run(host='localhost', port=8086, app=application, server_name='bicchiereserver'):
    "Shortcut to run demo app, or any WSGI/ASGI compliant app, for that matter"
    runner = application if server_name in Bicchiere.known_wsgi_servers else asgi_application

    if Bicchiere.is_wsgi(app):
        if server_name in Bicchiere.known_wsgi_servers:
            pass
        else:
            print(f"You must choose a WSGI server to run a WSGI app.\nQuitting.\n")
            os.sys.exit()

    if Bicchiere.is_asgi(app):
        if server_name in Bicchiere.known_asgi_servers:
            pass
        else:
            print(f"You must choose an ASGI server to run an ASGI app.\nQuitting.\n")
            os.sys.exit()

    runner.run(host, port, app, server_name)

# End Miscelaneous exports


# End of Part I - The sync world

#########################################################################################################

# Part II - The async world

# Async descendant of Bicchiere

class AsyncBicchiere(Bicchiere):
    "ASGI version of Bicchiere"

    async def redirect(self, path, status_code=302, status_msg="Found"):
        self.headers.add_header('Location', path)
        status_line = f"{status_code} {status_msg}"
        self.logger.info(f"Redirecting (status code {status_code}) to {path}")
        contents = dict(type='http.response.body', body=self.tobytes(status_line), more_body=False)
        sentcontents = b""
        try:
            await self.send(dict(type="http.response.start", status=status_code, headers=[(b'Location', BicchiereMiddleware.tobytes(path))]))
            self.headers_sent = True
        except Exception as exc:
            self.logger.debug(f"EXCEPTION ocurred in REDIRECT while sending headers: {repr(exc)}")
            pass
        try:
            sentcontents = await self.send(contents)
        except Exception as exc:
            self.logger.debug(f"EXCEPTION ocurred in REDIRECT while sending body: {repr(exc)}")
        finally: #self.headers_sent = False
            return sentcontents


    @staticmethod
    async def no_response(*args, **kwargs):
        pass

    async def _start_response(self, status = None, headers = None):
        if not status or not headers:
            return self.send
        if isinstance(headers, (dict, Headers)):
            headers = headers.items()
        start = dict(type="http.response.start", status=status, headers=headers)
        await self.send(start)
        self.write = self.send
        return self.send

    async def start_response(self, status=200, headers=[]):
        if self.headers_sent:
            return self.send or None
        if isinstance(headers, (dict, Headers)):
            headers = list(headers.items())
        self.headers_sent = True
        #await self._start_response(status, headers)
        if type(status) == str or type(status) == bytes:
            status = int(status.split(" ", 1)[0])
        # await self.send(dict(type="http.response.start", status=status, headers=headers))
        self.headers_sent = True
        return self.send

    async def _send_response(self, status_msg, response):

        if not self.headers_sent and 'content-type' not in self.headers:
            if response and self.is_html(response):
                self.headers.add_header(
                    'Content-Type', 'text/html', charset='utf-8')
            else:
                self.headers.add_header(
                    'Content-Type', 'text/plain', charset='utf-8')

        if response and self.config.debug:
            bresponse = self.tobytes(response)
            if hasattr(bresponse, "split"):
                dbg_msg_l = bresponse.split(b'\n')
            else:
                dbg_msg_l = bresponse
            dbg_msg = ''
            for msg in dbg_msg_l:
                if len(msg) > len(dbg_msg):
                    dbg_msg = msg
            self.debug(f"\nRESPONSE: '{dbg_msg[ : 79]}{'...' if len(dbg_msg) > 79 else ''}'")

        retval = b""
        # for i in range(len(response)):
        #     retval += self.tobytes(response[i])
        retval += self.tobytes(response)
        return [retval]

    async def _try_routes(self):
        route = None
        response = None
        status_msg = None

        try:
            self.full_path = self.environ.get('PATH_INFO')
            route = self.get_route_match(self.full_path)
            if route:
                if self.environ.get('REQUEST_METHOD', 'GET') in route.methods:
                    status_msg = BicchiereMiddleware.get_status_line(200)
                    if asyncio.iscoroutinefunction(route.func):
                        response = await route.func(**route.args)
                    else:
                        response = route.func(**route.args)
                    return status_msg, response
                else:
                    status_msg, response = self._abort(405, self.environ.get('REQUEST_METHOD'), f'not allowed for URL: {self.environ.get("PATH_INFO", "")}')
                    return status_msg, response
            else:
                #status_msg, response = self._abort(404, self.environ.get('path_info'.upper()), " not found.")
                #return status_msg, response
                return None, None
        except Exception as exc:
            status_msg, response = self._abort(500, self.environ.get('PATH_INFO'),
                               f'raised an error: {str(exc)}')
            return status_msg, response

    def __init__(self, application = None, name = None, wsgi_app = None):
        super().__init__(application, name or self.__class__.__name__)
        #self.routes = []
        self.wsgi_app = wsgi_app
        self.scope = {}
        self.receive = None
        self.send = None
        self.body = None


    async def websocket_handler(self, route: Route = None):
        while True:
            event = await self.receive()

            if event['type'] == 'websocket.connect':
                self.logger.info("Accepting incoming websocket connection request.")
                await self.send({
                    'type': 'websocket.accept'
                })
            elif event['type'] == 'websocket.disconnect':
                self.logger.info("Handling disconnect...")
                break
            elif event['type'] == 'websocket.receive':
                text = event['text'] if event.get('text') else event['bytes'].decode()
                self.logger.info(f"Websocket received this text: {text}")
                if route:
                    if asyncio.iscoroutinefunction(route.func):
                        response = await route.func(event)
                    else:
                        response = route.func(event)
                    await self.send({
                        'type': 'websocket.send',
                        'text': response
                    })
                else:
                    await self.send({
                        'type': 'websocket.send',
                        'text': text
                    })
            else:
                print(f"Received event type: {event.get('type')} (Don't know what to do with that...)")
                #await send({
                #    'type': 'websocket.accept'
                #})

    async def __call__(self, scope, receive, send):
        # self.init_local_data()
        self.scope = scope
        self.receive = receive
        self.send = send
        self.body = b""
        self.environ = self.scope2env(self.scope, self.body)
        self.headers = Headers()

        self.full_path = self.scope.get('path')
        self.msgtype = self.scope.get("type")


        self._init_session()

        self._init_args()

        response = None
        status_msg = None
        status = 200

        if self.msgtype in ["http", "https"]:
            self.logger.info(f"Received a {self.msgtype} message")
            self.logger.info(f"Message contents:\n{repr(self.scope)}")
            if not self.wsgi_app:
                more_body = True
                while more_body:
                    msg = await self.receive()
                    if msg.get("type") == "http.request":
                        self.body += msg.get("body", b"")
                    more_body = msg.get("more_body", False)
                self.environ = self.scope2env(self.scope, self.body)
                self.body = BytesIO(self.body)
                self.body.seek(0)
            if not self._test_environ():
                return [b'']
            self._config_environ()
        elif self.msgtype in ["websocket"]:
            self.logger.info("Received a WEBSOCKET request")
            #self.logger.info(json.dumps(self.scope, default=lambda x: repr(x)))
            route = self.get_route_match(self.scope.get("path"))
            if route:
                return await self.websocket_handler(route)
            else:
                return await self.websocket_handler(None)
        elif self.msgtype in ["lifespan"]:
            self.logger.info("Received a LIFESPAN msessage")
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    # Do some startup here!
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    # Do some shutdown here!
                    await send({'type': 'lifespan.shutdown.complete'})
                    return        
        elif self.msgtype in ["disconnect"]:
            self.logger.info("Received a DISCONNECT msessage")
        else:
            raise HTTPException(f"Received a message type({self.msgtype}) this app can't handle.")

        async def diamocidafare(status_msg, response):
            status = int(status_msg.split(" ", 1)[0])
            body = await self._send_response(status_msg, response)
            contents = dict(type='http.response.body', body=self.tobytes(body), more_body=False)
            try:
                await self.send(dict(type="http.response.start", status=status, headers=self.headers.items()))
                self.headers_sent = True
            except:
                pass
            try:
                sentcontents = await self.send(contents)
                self.headers_sent = False
            except:
                sentcontents = None
            finally:
                return sentcontents

        if self.msgtype in ["http", "https"]:

            if self.wsgi_app and self.is_wsgi(self.wsgi_app):
                try:
                    asgi_app = WsgiToAsgi(self.wsgi_app)
                    return await asgi_app(self.scope, self.receive, self.send)
                except Exception as exc:
                    self.logger.error(f"Exeption while trying to convert WSGI app to ASGI: {repr(exc)}")

            status_msg, response = self._try_static()
            if status_msg and response:
                self.logger.info(f"Proceeding from _try_static with status: {status_msg}")
                return await diamocidafare(status_msg, response)

            status_msg, response = self._try_cgi()
            if status_msg and response:
                self.logger.info(f"Proceeding from _try_static with status: {status_msg}")
                return await diamocidafare(status_msg, response)

            status_msg, response = self._try_default()
            if status_msg and response:
                self.logger.info(f"Proceeding from _try_default with status: {status_msg}")
                return await diamocidafare(status_msg, response)

            status_msg, response = await self._try_routes()
#            if status_msg and response and re.match(r"^[235]", status_msg):
            if status_msg and response:
                self.logger.info(f"Proceeding from _try_routes with status: {status_msg}")
                return await diamocidafare(status_msg, response)

            status_msg, response = self._try_mounted()
            if status_msg and response:
                self.logger.info(f"Proceeding from _try_mount with status: {status_msg}")
                return await diamocidafare(status_msg, response)

            status_msg, response = self._abort(404, self.environ.get('PATH_INFO'), " not found AT ALL.")
            self.logger.info(f"Resource {self.full_path} not found.\n")
            status = int(status_msg.split(" ", 1)[0])
            body = await self._send_response(status_msg, response)
            contents = dict(type='http.response.body', body=self.tobytes(body), more_body=False)
            if not self.headers_sent:
                await self.send(dict(type="http.response.start", status=status, headers=[('Content-Type', 'text/html; charset=utf-8')]))
                self.headers_sent = True
            return await self.send(contents)
        elif self.msgtype in ["websocket"]:
            self.logger.debug("Received message type 'websocket'.\nThis has been processed elsewhere and thus, this message should never appear.")
        else:
            self.logger.debug(f"Received message type '{self.msgtype}'.\nFor now, this won't be processed.")


    @classmethod
    def demo_app(cls):
        app = cls(name="Demo Async App")
        app.counter = 0
        app.wsgi_app = Bicchiere.demo_app()


        @app.get("/echo/wstest")
        async def wstest(evt):
            text: str = evt.get("text") or evt.get("bytes").decode()
            app.logger.info(f"\n\n/echo/wstest received '{text}'\n\n")
            dt = datetime.now()
            sdate = dt.strftime("%Y-%m-%d %H:%M:%S")
            full_text = f"\tECHO at ({sdate}):\t{repr(text)}"
            app.logger.info(f"Returning ws message: '{full_text}'\n\n")
            #return text.upper()
            return full_text

        @app.get("/showscope")
        async def showscope():
            body = [f"{clave} =  {valor}\n".encode("utf-8") for clave, valor in app.environ.items()]
            body.insert(0, b'ASGI Environment\n________________\n\n')
            body.append(b'_' * 80)
            body.append(b"\n\n")
            body.append(b'ASGI Scope\n__________\n\n')
            body.extend([f"{clave} =  {valor}\n".encode("utf-8") for clave, valor in app.scope.items()])
            body.append(b'_' * 80)
            body.append(b"\n\n")
            app.counter += 1
            body.append(f"This app was visited {app.counter} times.\n".encode("utf-8"))
            return b"".join(body)


        @app.get("/demo/hello/<name>")
        @app.get("/demo/hello")
        #@app.plain_content()
        def hello(name="Straniero"):
            return f"<h1>Ciao, {name.title()}!</h1>\n<p>Bicchiere ti saluta.</p>"

        # app.mount("/", app.wsgi_app)

        @app.get("demo/f42")
        async def myf42():
            return await app.redirect("/factorial/42")

        Bicchiere.config.apptype = "ASGI"
        return app

# End AsyncBicchiere


asgi_application = AsyncBicchiere.demo_app()

# End of Part II - The async world

# ASGIServer stuff beginning

class SplitBuffer:
    def __init__(self):
        self.data = b""

    def feed_data(self, data: bytes):
        self.data += data

    def pop(self, separator: bytes):
        first, *rest = self.data.split(separator, maxsplit=1)
        # no split was possible
        if not rest:
            return None
        else:
            self.data = separator.join(rest)
            return first

    def flush(self):
        temp = self.data
        self.data = b""
        return temp


class HttpRequestParser:
    def __init__(self, protocol):
        self.protocol = protocol
        self.buffer = SplitBuffer()
        self.http_method = ""
        self.done_parsing_start = False
        self.done_parsing_headers = False
        self.expected_body_length = 0

    def feed_data(self, data: bytes):
        self.buffer.feed_data(data)
        self.parse()

    def parse(self):
        if not self.done_parsing_start:
            self.parse_startline()
        elif not self.done_parsing_headers:
            self.parse_headerline()
        elif self.expected_body_length:
            data = self.buffer.flush()
            self.expected_body_length -= len(data)
            self.protocol.on_body(data)
            self.parse()
        else:
            self.protocol.on_message_complete()

    def parse_startline(self):
        line = self.buffer.pop(separator=b"\r\n")
        if line is not None:
            http_method, url, http_version = line.strip().split()
            self.http_method = http_method
            self.done_parsing_start = True
            self.protocol.on_url(url)
            self.parse()

    def parse_headerline(self):
        line = self.buffer.pop(separator=b"\r\n")
        if line is not None:
            if line:
                name, value = line.strip().split(b": ", maxsplit=1)
                if name.lower() == b"content-length":
                    self.expected_body_length = int(value.decode("utf-8") if hasattr(value, "decode") else value)
                self.protocol.on_header(name, value)
            else:
                self.done_parsing_headers = True
                self.protocol.on_headers_complete()
            self.parse()


def create_status_line(status_code: int = 200):
    code = str(status_code).encode()
    code_phrase = http.HTTPStatus(status_code).phrase.encode()
    return b"HTTP/1.1 " + code + b" " + code_phrase + b"\r\n"


def format_headers(headers: List[Tuple[bytes, bytes]]):
    return b"".join([BicchiereMiddleware.tobytes(key) + b": " + BicchiereMiddleware.tobytes(value) + b"\r\n" for key, value in headers])


def make_response(status_code: int = 200, headers: List[Tuple[bytes, bytes]] = None,  body: bytes = b""):
    if headers is None:
        headers = []
    content = [create_status_line(status_code), format_headers(headers), b"\r\n" if body else b"", body]
    return b"".join(content)



@dataclass
class ASGIRequest:
    http_method: str = ""
    path: str = ""
    headers: List[Tuple[bytes, bytes]] = field(default_factory=lambda: [])
    body_buffer: bytes = b""
    trigger_more_body: asyncio.Event = asyncio.Event()
    last_body: bool = False

    def to_scope(self):
        path_parts = self.path.split("?")
        scope = {
            "type": "http",
            "asgi": {"version": "2.1", "spec_version": "2.1"},
            "http_version": "1.1",
            "method": self.http_method,
            "scheme": "http",
            "path": path_parts[0],
            "query_string": path_parts[1] if len(path_parts) > 1 else "",
            "headers": self.headers,
        }
        return scope

    def to_event(self):
        event = {
            "type": "http.request",
            "body": self.body_buffer,
            "more_body": not self.last_body,
        }
        self.body_buffer = b""
        return event


@dataclass
class ASGIResponse:
    status_code: int = 200
    headers: List[Tuple[bytes, bytes]] = field(default_factory=lambda: [])
    body: bytes = b""
    is_complete: bool = False

    def to_http(self):
        return make_response(self.status_code, self.headers, self.body)

    def feed_event(self, event):
        if event["type"] == "http.response.start":
            self.status_code = event["status"]
            self.headers = event["headers"]
        elif event["type"] == "http.response.body":
            self.body += event.get("body", b"")
            if not event.get("more_body", False):
                self.is_complete = True


class ASGISession:
    def __init__(self, client_socket, address, app):
        self.loop = asyncio.get_event_loop()
        self.client_socket = client_socket
        self.address = address
        self.app = app
        self.trigger_run_asgi = asyncio.Event()
        self.parser = HttpRequestParser(self)
        self.request = ASGIRequest()
        self.response = ASGIResponse()

    async def run(self):
        self.loop.create_task(self.run_asgi())
        while True:
            if self.response.is_complete:
                break
            data = await self.loop.sock_recv(self.client_socket, 1024)
            print(f"Received {data}")
            self.parser.feed_data(data)
        self.client_socket.close()
        print(f"Socket with {self.address} closed.")

    # ASGI Server protocol methods
    async def run_asgi(self):
        await self.trigger_run_asgi.wait()
        return await self.app(self.request.to_scope(), self.receive, self.send)

    async def receive(self):
        while True:
            await self.request.trigger_more_body.wait()
            return self.request.to_event()

    async def send(self, event):
        self.response.feed_event(event)
        if self.response.is_complete:
            resp_http = self.response.to_http()
            await self.loop.sock_sendall(self.client_socket, resp_http)
            print("Response sent.")
            try:
                self.client_socket.close()
            except:
                pass

    # HTTP parser callbacks
    def on_url(self, url):
        print(f"Received url: {url}")
        self.request.http_method = self.parser.http_method.decode("utf-8") if hasattr(self.parser.http_method, "decode") else self.parser.http_method
        self.request.path = url.decode("utf-8") if hasattr(url, "decode") else url

    def on_header(self, name: bytes, value: bytes):
        print(f"Received header: ({name}, {value})")
        self.request.headers.append((name, value))

    def on_headers_complete(self):
        print("Received all headers.")
        self.trigger_run_asgi.set()

    def on_body(self, body: bytes):
        print(f"Received body: {body}")
        self.request.body_buffer += body
        self.request.trigger_more_body.set()

    def on_message_complete(self):
        print("Received request completely.")
        self.request.last_body = True
        self.request.trigger_more_body.set()


class ASGIServer:
    def __init__(self, host: str, port: int, app):
        self.host = host
        self.port = port
        self.app = app

    async def serve_forever(self):
        server_socket = socket.socket()
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)
        server_socket.setblocking(False)

        loop = asyncio.get_event_loop()
        try:
            while True:
                client_socket, address = await loop.sock_accept(server_socket)
                print(f"Socket established with {address}.")
                session = ASGISession(client_socket, address, self.app)
                loop.create_task(session.run())
        except KeyboardInterrupt:
            print("Server stopped due to keyboard interrupt.")
            server_socket.close()
            sys.exit(0)
        except Exception as exc:
            print(f"Server stopped due to exception: {repr(exc)}")    
            server_socket.close()
            sys.exit(255)

test_visitors = 0

async def test_asgi_app(scope, receive, send):
    if scope.get("type") not in ("http", "https"):
        print(f"Unknown scope type: {scope.get('type')}")
        return

    global test_visitors
    start_response, html, body = None, None, None
    if scope.get("path") == "/":
        test_visitors += 1
        start_response = dict(type="http.response.start", status=200, headers=[(b'Content-Type', b'text/html; charset=utf-8')])
        html = """
    <!DOCTYPE html>
    <html lang="it">
        <head>
            <title>ASGI Test Page</title>
            <style>
              .sign {
                background: #effeef; 
                font-size: 14pt; 
                margin-left: 2em; 
                padding: 10px; 
                border: solid 1px; 
                border-radius: 4px; 
                width: 20%;
                margin-top: 10px;
                text-align: center;
              }
            </style>
        </head>
        <body style="font-family: Helvetica, Arial, sans-serif;">
          <h1 style="padding: 0.5em; text-align: center; color: steelblue;">Hello, ASGI!</h1>
          <div class="sign">
            <span>You're visitor number</span>
            &nbsp;
            <span style="color: red;">{test_visitors}</span>
          </div>
          <div class="sign" style="border: none; background: transparent;">
            <button onclick="location.href=location.href">Reload</button>
          </div>
        </body>
    </html>
    """.replace("{test_visitors}", str(test_visitors))
    else:
        start_response = dict(type="http.response.start", status=404, headers=[(b'Content-Type', b'text/html; charset=utf-8')])
        html =f"""
          <h2><strong style="color: #888; font-size: 20pt;">404</strong>&nbsp;Resource <strong style="color: red;">{scope.get("path")}</strong> not found.</h2>
        """
    body = dict(type="http.response.body", more_body=False, body=html.encode() + b"")
    await send(start_response)
    await send(body)
    return b""

test_asgi_app.name = "Test ASGI App"

# End of ASGIServer stuff

# WSGI2ASGI beginning


class _WorkItem:
    """
    Represents an item needing to be run in the executor.
    Copied from ThreadPoolExecutor (but it's private, so we're not going to rely on importing it)
    """

    def __init__(self, future, fn, args, kwargs):
        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        if not self.future.set_running_or_notify_cancel():
            return
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Break a reference cycle with the exception 'exc'
            self = None
        else:
            self.future.set_result(result)


class CurrentThreadExecutor(Executor):
    """
    An Executor that actually runs code in the thread it is instantiated in.
    Passed to other threads running async code, so they can run sync code in
    the thread they came from.
    """

    def __init__(self):
        self._work_thread = threading.current_thread()
        self._work_queue = queue.Queue()
        self._broken = False

    def run_until_future(self, future):
        """
        Runs the code in the work queue until a result is available from the future.
        Should be run from the thread the executor is initialised in.
        """
        # Check we're in the right thread
        if threading.current_thread() != self._work_thread:
            raise RuntimeError(
                "You cannot run CurrentThreadExecutor from a different thread"
            )
        future.add_done_callback(self._work_queue.put)
        # Keep getting and running work items until we get the future we're waiting for
        # back via the future's done callback.
        try:
            while True:
                # Get a work item and run it
                work_item = self._work_queue.get()
                if work_item is future:
                    return
                work_item.run()
                del work_item
        finally:
            self._broken = True

    def submit(self, fn, *args, **kwargs):
        # Check they're not submitting from the same thread
        if threading.current_thread() == self._work_thread:
            raise RuntimeError(
                "You cannot submit onto CurrentThreadExecutor from its own thread"
            )
        # Check they're not too late or the executor errored
        if self._broken:
            raise RuntimeError("CurrentThreadExecutor already quit or is broken")
        # Add to work queue
        f = Future()
        work_item = _WorkItem(f, fn, args, kwargs)
        self._work_queue.put(work_item)
        # Return the future
        return f


class Local:
    """
    A drop-in replacement for threading.locals that also works with asyncio
    Tasks (via the current_task asyncio method), and passes locals through
    sync_to_async and async_to_sync.

    Specifically:
     - Locals work per-coroutine on any thread not spawned using asgiref
     - Locals work per-thread on any thread not spawned using asgiref
     - Locals are shared with the parent coroutine when using sync_to_async
     - Locals are shared with the parent thread when using async_to_sync
       (and if that thread was launched using sync_to_async, with its parent
       coroutine as well, with this working for indefinite levels of nesting)

    Set thread_critical to True to not allow locals to pass from an async Task
    to a thread it spawns. This is needed for code that truly needs
    thread-safety, as opposed to things used for helpful context (e.g. sqlite
    does not like being called from a different thread to the one it is from).
    Thread-critical code will still be differentiated per-Task within a thread
    as it is expected it does not like concurrent access.

    This doesn't use contextvars as it needs to support 3.6. Once it can support
    3.7 only, we can then reimplement the storage more nicely.
    """

    def __init__(self, thread_critical: bool = False) -> None:
        self._thread_critical = thread_critical
        self._thread_lock = threading.RLock()
        self._context_refs: "weakref.WeakSet[object]" = weakref.WeakSet()
        # Random suffixes stop accidental reuse between different Locals,
        # though we try to force deletion as well.
        self._attr_name = "_asgiref_local_impl_{}_{}".format(
            id(self),
            "".join(random.choice(string.ascii_letters) for i in range(8)),
        )

    def _get_context_id(self):
        """
        Get the ID we should use for looking up variables
        """
        # Prevent a circular reference
        #from .sync import AsyncToSync, SyncToAsync

        # First, pull the current task if we can
        context_id = SyncToAsync.get_current_task()
        context_is_async = True
        # OK, let's try for a thread ID
        if context_id is None:
            context_id = threading.current_thread()
            context_is_async = False
        # If we're thread-critical, we stop here, as we can't share contexts.
        if self._thread_critical:
            return context_id
        # Now, take those and see if we can resolve them through the launch maps
        for i in range(sys.getrecursionlimit()):
            try:
                if context_is_async:
                    # Tasks have a source thread in AsyncToSync
                    context_id = AsyncToSync.launch_map[context_id]
                    context_is_async = False
                else:
                    # Threads have a source task in SyncToAsync
                    context_id = SyncToAsync.launch_map[context_id]
                    context_is_async = True
            except KeyError:
                break
        else:
            # Catch infinite loops (they happen if you are screwing around
            # with AsyncToSync implementations)
            raise RuntimeError("Infinite launch_map loops")
        return context_id

    def _get_storage(self):
        context_obj = self._get_context_id()
        if not hasattr(context_obj, self._attr_name):
            setattr(context_obj, self._attr_name, {})
            self._context_refs.add(context_obj)
        return getattr(context_obj, self._attr_name)

    def __del__(self):
        try:
            for context_obj in self._context_refs:
                try:
                    delattr(context_obj, self._attr_name)
                except AttributeError:
                    pass
        except TypeError:
            # WeakSet.__iter__ can crash when interpreter is shutting down due
            # to _IterationGuard being None.
            pass

    def __getattr__(self, key):
        with self._thread_lock:
            storage = self._get_storage()
            if key in storage:
                return storage[key]
            else:
                raise AttributeError(f"{self!r} object has no attribute {key!r}")

    def __setattr__(self, key, value):
        if key in ("_context_refs", "_thread_critical", "_thread_lock", "_attr_name"):
            return super().__setattr__(key, value)
        with self._thread_lock:
            storage = self._get_storage()
            storage[key] = value

    def __delattr__(self, key):
        with self._thread_lock:
            storage = self._get_storage()
            if key in storage:
                del storage[key]
            else:
                raise AttributeError(f"{self!r} object has no attribute {key!r}")


def _restore_context(context):
    # Check for changes in contextvars, and set them to the current
    # context for downstream consumers
    for cvar in context:
        try:
            if cvar.get() != context.get(cvar):
                cvar.set(context.get(cvar))
        except LookupError:
            cvar.set(context.get(cvar))


def _iscoroutinefunction_or_partial(func: Any) -> bool:
    # Python < 3.8 does not correctly determine partially wrapped
    # coroutine functions are coroutine functions, hence the need for
    # this to exist. Code taken from CPython.
    if sys.version_info >= (3, 8):
        return asyncio.iscoroutinefunction(func)
    else:
        while inspect.ismethod(func):
            func = func.__func__
        while isinstance(func, functools.partial):
            func = func.func

        return asyncio.iscoroutinefunction(func)


class ThreadSensitiveContext:
    """Async context manager to manage context for thread sensitive mode

    This context manager controls which thread pool executor is used when in
    thread sensitive mode. By default, a single thread pool executor is shared
    within a process.

    In Python 3.7+, the ThreadSensitiveContext() context manager may be used to
    specify a thread pool per context.

    This context manager is re-entrant, so only the outer-most call to
    ThreadSensitiveContext will set the context.

    Usage:

    >>> import time
    >>> async with ThreadSensitiveContext():
    ...     await sync_to_async(time.sleep, 1)()
    """

    def __init__(self):
        self.token = None

    async def __aenter__(self):
        try:
            SyncToAsync.thread_sensitive_context.get()
        except LookupError:
            self.token = SyncToAsync.thread_sensitive_context.set(self)

        return self

    async def __aexit__(self, exc, value, tb):
        if not self.token:
            return

        executor = SyncToAsync.context_to_thread_executor.pop(self, None)
        if executor:
            executor.shutdown()
        SyncToAsync.thread_sensitive_context.reset(self.token)


class AsyncToSync:
    """
    Utility class which turns an awaitable that only works on the thread with
    the event loop into a synchronous callable that works in a subthread.

    If the call stack contains an async loop, the code runs there.
    Otherwise, the code runs in a new loop in a new thread.

    Either way, this thread then pauses and waits to run any thread_sensitive
    code called from further down the call stack using SyncToAsync, before
    finally exiting once the async task returns.
    """

    # Maps launched Tasks to the threads that launched them (for locals impl)
    launch_map: "Dict[asyncio.Task[object], threading.Thread]" = {}

    # Keeps track of which CurrentThreadExecutor to use. This uses an asgiref
    # Local, not a threadlocal, so that tasks can work out what their parent used.
    executors = Local()

    # When we can't find a CurrentThreadExecutor from the context, such as
    # inside create_task, we'll look it up here from the running event loop.
    loop_thread_executors: "Dict[asyncio.AbstractEventLoop, CurrentThreadExecutor]" = {}

    def __init__(self, awaitable, force_new_loop=False):
        if not callable(awaitable) or (
            not _iscoroutinefunction_or_partial(awaitable)
            and not _iscoroutinefunction_or_partial(
                getattr(awaitable, "__call__", awaitable)
            )
        ):
            # Python does not have very reliable detection of async functions
            # (lots of false negatives) so this is just a warning.
            warnings.warn(
                "async_to_sync was passed a non-async-marked callable", stacklevel=2
            )
        self.awaitable = awaitable
        try:
            self.__self__ = self.awaitable.__self__
        except AttributeError:
            pass
        if force_new_loop:
            # They have asked that we always run in a new sub-loop.
            self.main_event_loop = None
        else:
            try:
                self.main_event_loop = asyncio.get_running_loop()
            except RuntimeError:
                # There's no event loop in this thread. Look for the threadlocal if
                # we're inside SyncToAsync
                main_event_loop_pid = getattr(
                    SyncToAsync.threadlocal, "main_event_loop_pid", None
                )
                # We make sure the parent loop is from the same process - if
                # they've forked, this is not going to be valid any more (#194)
                if main_event_loop_pid and main_event_loop_pid == os.getpid():
                    self.main_event_loop = getattr(
                        SyncToAsync.threadlocal, "main_event_loop", None
                    )
                else:
                    self.main_event_loop = None

    def __call__(self, *args, **kwargs):
        # You can't call AsyncToSync from a thread with a running event loop
        try:
            event_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            if event_loop.is_running():
                raise RuntimeError(
                    "You cannot use AsyncToSync in the same thread as an async event loop - "
                    "just await the async function directly."
                )

        # Wrapping context in list so it can be reassigned from within
        # `main_wrap`.
        context = [contextvars.copy_context()]

        # Make a future for the return information
        call_result = Future()
        # Get the source thread
        source_thread = threading.current_thread()
        # Make a CurrentThreadExecutor we'll use to idle in this thread - we
        # need one for every sync frame, even if there's one above us in the
        # same thread.
        if hasattr(self.executors, "current"):
            old_current_executor = self.executors.current
        else:
            old_current_executor = None
        current_executor = CurrentThreadExecutor()
        self.executors.current = current_executor
        loop = None
        # Use call_soon_threadsafe to schedule a synchronous callback on the
        # main event loop's thread if it's there, otherwise make a new loop
        # in this thread.
        try:
            awaitable = self.main_wrap(
                args, kwargs, call_result, source_thread, sys.exc_info(), context
            )

            if not (self.main_event_loop and self.main_event_loop.is_running()):
                # Make our own event loop - in a new thread - and run inside that.
                loop = asyncio.new_event_loop()
                self.loop_thread_executors[loop] = current_executor
                loop_executor = ThreadPoolExecutor(max_workers=1)
                loop_future = loop_executor.submit(
                    self._run_event_loop, loop, awaitable
                )
                if current_executor:
                    # Run the CurrentThreadExecutor until the future is done
                    current_executor.run_until_future(loop_future)
                # Wait for future and/or allow for exception propagation
                loop_future.result()
            else:
                # Call it inside the existing loop
                self.main_event_loop.call_soon_threadsafe(
                    self.main_event_loop.create_task, awaitable
                )
                if current_executor:
                    # Run the CurrentThreadExecutor until the future is done
                    current_executor.run_until_future(call_result)
        finally:
            # Clean up any executor we were running
            if loop is not None:
                del self.loop_thread_executors[loop]
            if hasattr(self.executors, "current"):
                del self.executors.current
            if old_current_executor:
                self.executors.current = old_current_executor
            _restore_context(context[0])

        # Wait for results from the future.
        return call_result.result()

    def _run_event_loop(self, loop, coro):
        """
        Runs the given event loop (designed to be called in a thread).
        """
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        finally:
            try:
                # mimic asyncio.run() behavior
                # cancel unexhausted async generators
                tasks = asyncio.all_tasks(loop)
                for task in tasks:
                    task.cancel()

                async def gather():
                    await asyncio.gather(*tasks, return_exceptions=True)

                loop.run_until_complete(gather())
                for task in tasks:
                    if task.cancelled():
                        continue
                    if task.exception() is not None:
                        loop.call_exception_handler(
                            {
                                "message": "unhandled exception during loop shutdown",
                                "exception": task.exception(),
                                "task": task,
                            }
                        )
                if hasattr(loop, "shutdown_asyncgens"):
                    loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()
                asyncio.set_event_loop(self.main_event_loop)

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        func = functools.partial(self.__call__, parent)
        return functools.update_wrapper(func, self.awaitable)

    async def main_wrap(
        self, args, kwargs, call_result, source_thread, exc_info, context
    ):
        """
        Wraps the awaitable with something that puts the result into the
        result/exception future.
        """
        if context is not None:
            _restore_context(context[0])

        current_task = SyncToAsync.get_current_task()
        self.launch_map[current_task] = source_thread
        try:
            # If we have an exception, run the function inside the except block
            # after raising it so exc_info is correctly populated.
            if exc_info[1]:
                try:
                    raise exc_info[1]
                except BaseException:
                    result = await self.awaitable(*args, **kwargs)
            else:
                result = await self.awaitable(*args, **kwargs)
        except BaseException as e:
            call_result.set_exception(e)
        else:
            call_result.set_result(result)
        finally:
            del self.launch_map[current_task]

            context[0] = contextvars.copy_context()


class SyncToAsync:
    """
    Utility class which turns a synchronous callable into an awaitable that
    runs in a threadpool. It also sets a threadlocal inside the thread so
    calls to AsyncToSync can escape it.

    If thread_sensitive is passed, the code will run in the same thread as any
    outer code. This is needed for underlying Python code that is not
    threadsafe (for example, code which handles SQLite database connections).

    If the outermost program is async (i.e. SyncToAsync is outermost), then
    this will be a dedicated single sub-thread that all sync code runs in,
    one after the other. If the outermost program is sync (i.e. AsyncToSync is
    outermost), this will just be the main thread. This is achieved by idling
    with a CurrentThreadExecutor while AsyncToSync is blocking its sync parent,
    rather than just blocking.

    If executor is passed in, that will be used instead of the loop's default executor.
    In order to pass in an executor, thread_sensitive must be set to False, otherwise
    a TypeError will be raised.
    """

    # If they've set ASGI_THREADS, update the default asyncio executor for now
    if "ASGI_THREADS" in os.environ:
        # We use get_event_loop here - not get_running_loop - as this will
        # be run at import time, and we want to update the main thread's loop.
        loop = asyncio.get_event_loop()
        loop.set_default_executor(
            ThreadPoolExecutor(max_workers=int(os.environ["ASGI_THREADS"]))
        )

    # Maps launched threads to the coroutines that spawned them
    launch_map: "Dict[threading.Thread, asyncio.Task[object]]" = {}

    # Storage for main event loop references
    threadlocal = threading.local()

    # Single-thread executor for thread-sensitive code
    single_thread_executor = ThreadPoolExecutor(max_workers=1)

    # Maintain a contextvar for the current execution context. Optionally used
    # for thread sensitive mode.
    thread_sensitive_context: "contextvars.ContextVar[str]" = contextvars.ContextVar(
        "thread_sensitive_context"
    )

    # Contextvar that is used to detect if the single thread executor
    # would be awaited on while already being used in the same context
    deadlock_context: "contextvars.ContextVar[bool]" = contextvars.ContextVar(
        "deadlock_context"
    )

    # Maintaining a weak reference to the context ensures that thread pools are
    # erased once the context goes out of scope. This terminates the thread pool.
    context_to_thread_executor: "weakref.WeakKeyDictionary[object, ThreadPoolExecutor]" = (
        weakref.WeakKeyDictionary()
    )

    def __init__(
        self,
        func: Callable[..., Any],
        thread_sensitive: bool = True,
        executor: Optional["ThreadPoolExecutor"] = None,
    ) -> None:
        if (
            not callable(func)
            or _iscoroutinefunction_or_partial(func)
            or _iscoroutinefunction_or_partial(getattr(func, "__call__", func))
        ):
            raise TypeError("sync_to_async can only be applied to sync functions.")
        self.func = func
        functools.update_wrapper(self, func)
        self._thread_sensitive = thread_sensitive
        self._is_coroutine = asyncio.coroutines._is_coroutine  # type: ignore
        if thread_sensitive and executor is not None:
            raise TypeError("executor must not be set when thread_sensitive is True")
        self._executor = executor
        try:
            self.__self__ = func.__self__  # type: ignore
        except AttributeError:
            pass

    async def __call__(self, *args, **kwargs):
        loop = asyncio.get_running_loop()

        # Work out what thread to run the code in
        if self._thread_sensitive:
            if hasattr(AsyncToSync.executors, "current"):
                # If we have a parent sync thread above somewhere, use that
                executor = AsyncToSync.executors.current
            elif self.thread_sensitive_context and self.thread_sensitive_context.get(
                None
            ):
                # If we have a way of retrieving the current context, attempt
                # to use a per-context thread pool executor
                thread_sensitive_context = self.thread_sensitive_context.get()

                if thread_sensitive_context in self.context_to_thread_executor:
                    # Re-use thread executor in current context
                    executor = self.context_to_thread_executor[thread_sensitive_context]
                else:
                    # Create new thread executor in current context
                    executor = ThreadPoolExecutor(max_workers=1)
                    self.context_to_thread_executor[thread_sensitive_context] = executor
            elif loop in AsyncToSync.loop_thread_executors:
                # Re-use thread executor for running loop
                executor = AsyncToSync.loop_thread_executors[loop]
            elif self.deadlock_context and self.deadlock_context.get(False):
                raise RuntimeError(
                    "Single thread executor already being used, would deadlock"
                )
            else:
                # Otherwise, we run it in a fixed single thread
                executor = self.single_thread_executor
                if self.deadlock_context:
                    self.deadlock_context.set(True)
        else:
            # Use the passed in executor, or the loop's default if it is None
            executor = self._executor

        context = contextvars.copy_context()
        child = functools.partial(self.func, *args, **kwargs)
        func = context.run
        args = (child,)
        kwargs = {}

        try:
            # Run the code in the right thread
            future = loop.run_in_executor(
                executor,
                functools.partial(
                    self.thread_handler,
                    loop,
                    self.get_current_task(),
                    sys.exc_info(),
                    func,
                    *args,
                    **kwargs,
                ),
            )
            ret = await asyncio.wait_for(future, timeout=None)

        finally:
            _restore_context(context)
            if self.deadlock_context:
                self.deadlock_context.set(False)

        return ret

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        return functools.partial(self.__call__, parent)

    def thread_handler(self, loop, source_task, exc_info, func, *args, **kwargs):
        """
        Wraps the sync application with exception handling.
        """
        # Set the threadlocal for AsyncToSync
        self.threadlocal.main_event_loop = loop
        self.threadlocal.main_event_loop_pid = os.getpid()
        # Set the task mapping (used for the locals module)
        current_thread = threading.current_thread()
        if AsyncToSync.launch_map.get(source_task) == current_thread:
            # Our parent task was launched from this same thread, so don't make
            # a launch map entry - let it shortcut over us! (and stop infinite loops)
            parent_set = False
        else:
            self.launch_map[current_thread] = source_task
            parent_set = True
        # Run the function
        try:
            # If we have an exception, run the function inside the except block
            # after raising it so exc_info is correctly populated.
            if exc_info[1]:
                try:
                    raise exc_info[1]
                except BaseException:
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        finally:
            # Only delete the launch_map parent if we set it, otherwise it is
            # from someone else.
            if parent_set:
                del self.launch_map[current_thread]

    @staticmethod
    def get_current_task():
        """
        Implementation of asyncio.current_task()
        that returns None if there is no task.
        """
        try:
            return asyncio.current_task()
        except RuntimeError:
            return None


# Lowercase aliases (and decorator friendliness)
async_to_sync = AsyncToSync


@overload
def sync_to_async(
    func: None = None,
    thread_sensitive: bool = True,
    executor: Optional["ThreadPoolExecutor"] = None,
) -> Callable[[Callable[..., Any]], SyncToAsync]:
    ...


@overload
def sync_to_async(
    func: Callable[..., Any],
    thread_sensitive: bool = True,
    executor: Optional["ThreadPoolExecutor"] = None,
) -> SyncToAsync:
    ...


def sync_to_async(
    func=None,
    thread_sensitive=True,
    executor=None,
):
    if func is None:
        return lambda f: SyncToAsync(
            f,
            thread_sensitive=thread_sensitive,
            executor=executor,
        )
    return SyncToAsync(
        func,
        thread_sensitive=thread_sensitive,
        executor=executor,
    )


class WsgiToAsgi:
    """
    Wraps a WSGI application to make it into an ASGI application.
    """

    def __init__(self, wsgi_application):
        self.wsgi_application = wsgi_application

    async def __call__(self, scope, receive, send):
        """
        ASGI application instantiation point.
        We return a new WsgiToAsgiInstance here with the WSGI app
        and the scope, ready to respond when it is __call__ed.
        """
        await WsgiToAsgiInstance(self.wsgi_application)(scope, receive, send)


class WsgiToAsgiInstance:
    """
    Per-socket instance of a wrapped WSGI application
    """

    def __init__(self, wsgi_application):
        self.wsgi_application = wsgi_application
        self.response_started = False
        self.response_content_length = None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            raise ValueError("WSGI wrapper received a non-HTTP scope")
        self.scope = scope
        with SpooledTemporaryFile(max_size=65536) as body:
            # Alright, wait for the http.request messages
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    raise ValueError("WSGI wrapper received a non-HTTP-request message")
                body.write(message.get("body", b""))
                if not message.get("more_body"):
                    break
            body.seek(0)
            # Wrap send so it can be called from the subthread
            self.sync_send = AsyncToSync(send)
            # Call the WSGI app
            await self.run_wsgi_app(body)

    def build_environ(self, scope, body):
        """
        Builds a scope and request body into a WSGI environ object.
        """
        environ = {
            "REQUEST_METHOD": scope["method"],
            "SCRIPT_NAME": scope.get("root_path", "").encode("utf8").decode("latin1"),
            "PATH_INFO": scope["path"].encode("utf8").decode("latin1"),
            "QUERY_STRING": scope["query_string"].decode("ascii"),
            "SERVER_PROTOCOL": "HTTP/%s" % scope["http_version"],
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": scope.get("scheme", "http"),
            "wsgi.input": body,
            "wsgi.errors": BytesIO(),
            "wsgi.multithread": True,
            "wsgi.multiprocess": True,
            "wsgi.run_once": False,
        }
        # Get server name and port - required in WSGI, not in ASGI
        if "server" in scope:
            environ["SERVER_NAME"] = scope["server"][0]
            environ["SERVER_PORT"] = str(scope["server"][1])
        else:
            environ["SERVER_NAME"] = "localhost"
            environ["SERVER_PORT"] = "80"

        if "client" in scope:
            environ["REMOTE_ADDR"] = scope["client"][0]

        # Go through headers and make them into environ entries
        for name, value in self.scope.get("headers", []):
            name = name.decode("latin1")
            if name == "content-length":
                corrected_name = "CONTENT_LENGTH"
            elif name == "content-type":
                corrected_name = "CONTENT_TYPE"
            else:
                corrected_name = "HTTP_%s" % name.upper().replace("-", "_")
            # HTTPbis say only ASCII chars are allowed in headers, but we latin1 just in case
            value = value.decode("latin1")
            if corrected_name in environ:
                value = environ[corrected_name] + "," + value
            environ[corrected_name] = value
        return environ

    def start_response(self, status, response_headers, exc_info=None):
        """
        WSGI start_response callable.
        """
        # Don't allow re-calling once response has begun
        if self.response_started:
            raise exc_info[1].with_traceback(exc_info[2])
        # Don't allow re-calling without exc_info
        if hasattr(self, "response_start") and exc_info is None:
            raise ValueError(
                "You cannot call start_response a second time without exc_info"
            )
        # Extract status code
        status_code, _ = status.split(" ", 1)
        status_code = int(status_code)
        # Extract headers
        headers = [
            (name.lower().encode("ascii"), value.encode("ascii"))
            for name, value in response_headers
        ]
        # Extract content-length
        self.response_content_length = None
        for name, value in response_headers:
            if name.lower() == "content-length":
                self.response_content_length = int(value)
        # Build and send response start message.
        self.response_start = {
            "type": "http.response.start",
            "status": status_code,
            "headers": headers,
        }

    @sync_to_async
    def run_wsgi_app(self, body):
        """
        Called in a subthread to run the WSGI app. We encapsulate like
        this so that the start_response callable is called in the same thread.
        """
        # Translate the scope and incoming request body into a WSGI environ
        environ = self.build_environ(self.scope, body)
        # Run the WSGI app
        bytes_sent = 0
        for output in self.wsgi_application(environ, self.start_response):
            # If this is the first response, include the response headers
            if not self.response_started:
                self.response_started = True
                self.sync_send(self.response_start)
            # If the application supplies a Content-Length header
            if self.response_content_length is not None:
                # The server should not transmit more bytes to the client than the header allows
                bytes_allowed = self.response_content_length - bytes_sent
                if len(output) > bytes_allowed:
                    output = output[:bytes_allowed]
            self.sync_send(
                {"type": "http.response.body", "body": output, "more_body": True}
            )
            bytes_sent += len(output)
            # The server should stop iterating over the response when enough data has been sent
            if bytes_sent == self.response_content_length:
                break
        # Close connection
        if not self.response_started:
            self.response_started = True
            self.sync_send(self.response_start)
        self.sync_send({"type": "http.response.body"})


# WSGI2ASGI end

# Provervial main function

def main():
    "Executes demo app or, alternatively, return current version."

    import argparse
    server_choices = Bicchiere.known_wsgi_servers + Bicchiere.known_asgi_servers
    parser = argparse.ArgumentParser(description='Command line arguments for Bicchiere')
    parser.add_argument('-p', '--port', type=int, default=8086, help="Server port number.")
    #parser.add_argument('--app', type=str, default="bicchiere:application", help="App to serve.")
    parser.add_argument('--app', type=str, default="bicchiere:asgi_application", help="App to serve.")
    parser.add_argument('-a', '--addr', type=str, default="127.0.0.1", help="Server address.")
    #parser.add_argument('-s', '--server', type=str, default="bicchiereserver", help="Server software.", choices=server_choices)
    parser.add_argument('-s', '--server', type=str, default="uvicorn", help="Server software.", choices=server_choices)
    parser.add_argument('-V', '--version', action="store_true", help="Outputs Bicchiere version and quits")
    parser.add_argument('-D', '--debug', action="store_true", help="Turn on debugging mode")

    args = parser.parse_args()

    if args.version:
        print(f"\nBicchiere version {application.version}\n")
        return

    os.system("clear")
    d = globals()
    if ":" in args.app:
        nmodule, napp = args.app.split(":")[:2]
    else:
        nmodule, napp = args.app, "asgi_application"
    try:
        os.sys.path.append(os.getcwd())
        os.sys.path.append(os.path.split(os.path.abspath(__file__))[0])
        exec(f"from {nmodule} import {napp} as userapp", d)
        userapp = d.get("userapp")
        logger.info(f"userapp: {repr(userapp)}\n\n")
    except ImportError as impErr:
        logger.error(f"ImportError: {repr(impErr)}.\nQuitting.\n\n")
        os.sys.exit()
    except Exception as exc:
        logger.error(
            f"Exception ocurred while importing {napp} from {nmodule}: {repr(exc)}.\nQuitting.\n\n")
        os.sys.exit()

    if not userapp:
        print("\nA valid application wasn't provided.\nQuitting.\n")
        os.sys.exit()

    if args.debug:
        logger.setLevel(10)
        Bicchiere.config.debug = True
        hop_modified = f"wsgiref.util.is_hop_by_hop has {'not ' if _is_hop_by_hop == wsgiref.util.is_hop_by_hop else ''}been monkey-patched"
        logger.debug(hop_modified)
        logger.debug(f"Added paths: {repr(os.sys.path[-2:])}")
        # sleep(3)
    run(port=args.port, app=userapp, host=args.addr, server_name=args.server)


if __name__ == '__main__':
    main()
