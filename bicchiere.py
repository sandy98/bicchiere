#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from email import charset
import os, random, re, json, cgi, threading, base64, sqlite3

from io import StringIO
from datetime import datetime, timedelta
from time import time
import time as o_time
from functools import reduce, wraps
from http.cookies import SimpleCookie, Morsel
from wsgiref.headers import Headers
from wsgiref.simple_server import make_server, demo_app as simple_demo_app
from uuid import uuid4
from urllib.parse import parse_qsl
from mimetypes import guess_type

### Support classes

class EventEmitter:
    "Utility class for adding objects the ability to emit events and registering handlers. Meant to be used as a mixin."

    def __init__(self, name = 'EventEmitter'):
        self.name = name
        self.event_handlers = {}

    def __repr__(self):
        return f"""
                Name:           {self.name}
                Handlers:       {self.event_handlers.items()}
                """

    def __str__(self):
        return repr(self)

    def emit(self, event_name = "change", event_data = {}):
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        for evh in self.event_handlers[event_name]:
            evh(self, event_name, event_data)

    def on(self, event_name, callback):
        uid = uuid4().hex
        callback.id = uid
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(callback)

        def off_event():
            i = 0
            for evh in self.event_handlers[event_name]:
                if evh.id == uid:
                    self.event_handlers[event_name].pop(i)
                    break
                i += 1

        off_event.id = uid

        return off_event


class EventedDict(dict, EventEmitter):
    def __init__(self, name = "EventedDict", *args, **kwargs):
        super(EventedDict, self).__init__(*args, **kwargs)
        self.name = name
        self.event_handlers = {}

    def __del__(self):
        #self.publish_change()
        self.publish_terminate()

    def __setitem__(self, key, value):
        super(EventedDict, self).__setitem__(key, value)
        self.publish_change(key, value)

    def __delitem__(self, key):
        super(EventedDict, self).__delitem__(key)
        self.publish_change(key, None)

    def __getattr__(self, key):
        return super(EventedDict, self).get(key, None)

    def publish_change(self, key = None, value = None):
        print(f"{self.__class__.__name__} emitting change event with key: {key} = value: {value}")
        self.emit("change", {'key': key, 'value': value, 'obj': self})

    def publish_terminate(self):
        print(f"{self.__class__.__name__} emitting terminate event")
        self.emit("terminate", self)


class Clock(EventEmitter):
    def __init__(self, seconds = 0, name = "Clock"):
       super(Clock, self).__init__(name)
       self.seconds = seconds
       self.interval = Bicchiere.config['session_saving_interval']
       self.running = False
       self.runner = None

    @staticmethod
    def pad(text, pad_len = 4, pad_char = '0', pad_left = True):
        text = str(text)
        padlen = pad_len - len(text)
        padstring = ''
        if padlen > 0:
            padstring = pad_char * padlen
        retstri = "{}{}"
        if pad_left:
            return retstri.format(padstring, text)
        else:
            return retstri.format(text, padstring)

    @staticmethod
    def run(this):
        #print("Beggining threaded execution")
        try:
             while this.running:
                this.emit("change", this.seconds)
                o_time.sleep(this.interval)
                this.seconds += this.interval
        except Exception as exc:
            print(f"Threaded execution interrupted due to: {str(exc)}")
            this.running = False
        finally:
            return

    def start(self):
        if self.runner and self.runner.is_alive():
            return
        self.running = True
        self.runner = threading.Thread(name = f"{self.name}-runner", target = self.run, args = (self,), daemon = True)
        #self.runner = multiprocessing.Process(name = f"{self.name}-runner", target = self.run, args = (self,), daemon = True)
        print("Starting clock...")
        self.runner.start()

    def stop(self):
        print("Stopping clock...")
        while self.runner and self.runner.is_alive():
            self.running = False
        self.child = None

    def restart(self):
        if self.running:
            self.stop()
        self.seconds = 0
        self.start()

    def gen_handler(self):
        def evh(obj, evt, seconds):
            print(f"{self.pad(seconds)} seconds ellapsed.")
        return evh


class Session(EventedDict):
    def __init__(self, sid = None, name = None, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        if sid and self.validate_sid(sid):
            sid = sid
        else:
            sid = uuid4().hex
        self.__setitem__('sid', sid)
        self.name = name or f"sid-{sid}"

    @staticmethod
    def validate_sid(sid):
        return not not re.match(r'[a-f0-9]{32}', sid)


class EventHandler:
    "Utility class for registering event handlers"

    def __init__(self, name = 'EventHandler'):
        self.name = name
        self.handlers = []
        self.unsuscribers = []

    def __repr__(self):
        return f"""
                Name:           {self.name}
                Handlers:       {list(map(lambda h: h.id, self.handlers))}
                Total Handlers: {len(self.handlers)}
                """

    def __str__(self):
        return repr(self)

    def make_handler(self, cb, obj, evt):
        if hasattr(obj, 'on') and hasattr(obj.on, '__call__'):
            self.unsuscribers.append(obj.on(evt, cb))
            self.handlers.append(cb)

    def unsuscribe(self, index):
        if index >= 0 and index < len(self.unsuscribers):
            self.unsuscribers[index]()
            f = self.unsuscribers.pop(index)
            del f
            f = self.handlers.pop(index)
            del f

    def unsuscribe_all(self):
        for i in range(len(self.unsuscribers)):
            self.unsuscribe(i)


class SessionManager(EventHandler):
    "Manages sessions on behalf of a Bicchiere App"

    def __init__(self, name = 'SessionManager'):
        #print(f"Starting {self.__class__.__name__}")
        super(SessionManager, self).__init__(name)
        self.sessions = {}
        self.clock = Clock()
        self.clock.on("change", self.handle_clock())
        self.clock_started = False

    def handle_clock(self):
        def on_change(*args, **kwargs):
            self.save_all()
        return on_change

    def start_clock(self):
        if not self.clock_started:
            self.clock.start()
            self.clock_started = True

    def __del__(self):
        print(f"Stopping {self.__class__.__name__}")
        self.save_all()

    def manage_session(self, session):
        print(f"{self.__class__.__name__}.manage_session preparing to handle session {session.sid}")
        self.sessions[session.sid] = session
        def handle_session_change(sess, evt, data):
            self.save_session(sess)
        self.make_handler(handle_session_change, session, "change")
        self.make_handler(handle_session_change, session, "terminate")

    def create_session(self, sid = None):
        ssid = None
        if not sid:
            ssid = uuid4().hex
        else:
            if Session.validate_sid(sid):
                ssid = sid
                print(f"{self.__class__.__name__}.create_session found valid sid: {sid}")
            else:
                ssid = uuid4().hex
                print(f"{self.__class__.__name__}.create_session found invalid sid: {sid}, thus returning a new one: {ssid}")
        session = Session(ssid)
        self.manage_session(session)
        self.save_session(session)
        return session

    def get_session(self, sid):
        if not self.clock_started:
            self.start_clock()
        if sid in self.sessions:
            print(f"{self.__class__.__name__}.get_session returning existing session: {sid}")
            return self.sessions[sid]
        else:
            print(f"{self.__class__.__name__}.get_session returning new session: {sid}")
            return self.create_session(sid)

    def load_session(self, sid):
        return self.get_session(sid)

    def save_session(self, session):
        if not self.clock.seconds % (100 * self.clock.interval): # log it every 100 times
            print(f"{self.__class__.__name__} saving session {session.sid} at {o_time.strftime('%d/%m/%Y %X')}")
        self.sessions[session.sid] = session

    def save_all(self):
        try:
            for sid in self.sessions:
                self.save_session(self.sessions[sid])
        except:
            pass


class FileSessionManager(SessionManager):
    "Stores sessions in file system"

    def __init__(self, name = 'FileSessionManager'):
        super(FileSessionManager, self).__init__(name)
        self.directory = os.path.join(os.getcwd(), Bicchiere.config['session_directory'])
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

    def load_session(self, sid):
        session = None
        filename = os.path.join(self.directory, sid)
        if os.path.exists(filename):
            fp = open(filename, "r")
            session = Session(**json.load(fp))
            fp.close()
            self.sessions[sid] = session
        return super(FileSessionManager, self).load_session(sid)

    def save_session(self, session):
        filename = os.path.join(self.directory, session.sid)
        fp = open(filename, "w")
        json.dump(session, fp)
        fp.close()
        super(FileSessionManager, self).save_session(session)


class DbSessionManager(SessionManager):
    "Stores sessions in SQLite database"

    def __init__(self, name = 'DbSessionManager'):
        super(DbSessionManager, self).__init__(name)
        self.directory = os.path.join(os.getcwd(), Bicchiere.config['session_directory'])
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)
        self.dbfile = os.path.join(self.directory, f'{Bicchiere.config["session_directory"]}.sqlite')
        self.conn, self.cursor = self.create_db_objects()
        #try:
        #    print(f"{self.__class__.__name__} testing table 'sessions' in \n{self.dbfile}")
        #    self.cursor.execute("select count(sid) from sessions;");
        #    self.cursor.fetchone()
        #except sqlite3.OperationalError:
        #    print("Table 'sessions' does not exist, creating it.")
        #    self.cursor.execute("create table sessions(sid text, data text);")
        try:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS sessions(sid TEXT PRIMARY KEY, data TEXT);")
            self.conn.commit()
            self.cursor.close()
            self.conn.close()
        except Exception as exc:
             print(f"Error creating table 'sessions' due to: {str(exc)}\nQuitting...")
             os.sys.exit(1)

    def create_db_objects(self):
        conn = sqlite3.connect(self.dbfile)
        cursor = conn.cursor()
        return conn, cursor

    def sess_exists(self, sid):
        self.cursor.execute("select count(*) from sessions where sid = ?;", (sid, ))
        result = self.cursor.fetchone()[0]
        return not not result

    def load_session(self, sid):
        session = None
        self.conn, self.cursor = self.create_db_objects()
        if self.sess_exists(sid):
            self.cursor.execute("select * from sessions where sid = ?;", (sid, ))
            session = Session(**json.loads(self.cursor.fetchone()[1]))
            self.sessions[sid] = session
        self.cursor.close()
        self.conn.close()
        return super(DbSessionManager, self).load_session(sid)

    def save_session(self, session):
        self.conn, self.cursor = self.create_db_objects()
        if self.sess_exists(session.sid):
            self.cursor.execute('update sessions set data = ? where sid = ?;', (json.dumps(session), session.sid))
        else:
            self.cursor.execute('insert into sessions (sid, data) values (?, ?);', (session.sid, json.dumps(session)))
        self.conn.commit()
        self.cursor.close()
        self.conn.close()
        self.sessions[session.sid] = session
        super(DbSessionManager, self).save_session(session)


class Route:
    "Utility class for routing requests"

    def __init__(self, pattern, func, param_types, methods = ['GET']):
        self.pattern = pattern
        self.func = func
        self.param_types = param_types
        self.methods = methods
        self.args = {}

    def __call__(self):
        return (self.pattern, self.func, self.param_types, self.args, self.methods)

    def match(self, path):
        m = self.pattern.match(path)
        if m:
            kwargs = m.groupdict()
            self.args = {}
            for argname in kwargs:
                self.args[argname] = self.param_types[argname](kwargs[argname])
            return self
            #return m.groupdict(), self.func, self.methods, self.param_types
        return None

    def __str__(self):
        return f"""
               Pattern: {str(self.pattern)}
               Handler: {self.func.__name__}
               Parameter Types:  {self.param_types}
               Methods: {self.methods}
               Arguments: {self.args}
               """

### End of support classes

### Templates related code

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
        """Construct a Templite with the given `text`.
        `contexts` are dictionaries of values to use for future renderings.
        These are good for filters and global values.
        """
        self.context = {}
        #for context in contexts:
            #self.context.update(context)
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
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if {0}:".format(self._expr_code(words[1])))
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                        "for c_{0} in {1}:".format(
                            words[1],
                            self._expr_code(words[3])
                        )
                    )
                    code.indent()
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
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



    def _variable(self, name, vars_set):
        """Track that `name` is used as a variable.
        Adds the name to `vars_set`, a set of variable names.
        Raises an syntax error if `name` is not a valid name.
        """
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", name):
            self._syntax_error("Not a valid name", name)
        vars_set.add(name)

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        if "|" in expr:
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
            self._variable(expr, self.all_vars)
            code = "c_%s" % expr
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

#Page template includes 3 placeholders: 'page_title', 'menu_content' and 'main_contents'
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

    def __init__(self, label = "Dropdown"):
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


### End of templates related code


### Middleware

class BicchiereMiddleware:
    def __init__(self, application = None):
        self.application = application
        self.name = self.__class__.__name__

    def __call__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response

        self.environ["wsgi_middleware"] = str(self)

        if self.application:
            return self.application(environ, start_response)
        else:
            start_response("200 OK", [('Content-Type', 'text/html; charset=utf-8')])
            yield str(self).encode("utf-8")
            return b""

    def __str__(self):
        return f"{self.__class__.__name__} v. {Bicchiere.get_version()}"

    @property
    def last_handler(self):
        lh = self.application if hasattr(self, "application") and Bicchiere.is_callable(self.application) else self

        while hasattr(lh, "application") and Bicchiere.is_callable(lh.application):
            lh = lh.application

        return lh or self

    def run(self, *args, **kwargs):
        if self.application:
            return self.application.run(*args, **kwargs)
        else:
           self.debug(f"{self.name} was meant as middleware, therefore it will not run stand alone")


### End of middleware


### Miscelaneous configuration options

default_config = {
        'debug': True,
        'session_manager_class': SessionManager,
        'session_directory': 'bicchiere_sessions',
        'session_saving_interval': 5,
        'static_directory': 'static',
        'templates_directory': 'templates',
        'allow_directory_listing': False
        }

### End of miscelaneous configuration options


###  Main Bicchiere App class

class Bicchiere(BicchiereMiddleware):
    """
    Main WSGI application class
    """

    __version__ = (0, 2, 12)

    __author__  = "Domingo E. Savoretti"

    config = default_config

    template_filters = {}

    known_servers = ['gunicorn', 'bjoern', 'wsgiref']
    bevande = ["Campari", "Negroni", "Vermut", "Bitter", "Birra"]

    @property
    def version(self):
        major, minor, release = self.__version__
        return f"{major}.{minor}.{release}"

    def debug(self, *args, **kw):
        if hasattr(self, "config") and hasattr(self.config, "get") and self.config.get("debug", False):
           print(*args, **kw)

    def set_new_start_response(self, status = "200 OK"):
        if not self.start_response:
            self.debug("Start response not set, so cannot set new start response. Returning with empty hands")
            return
        old_start_response = self.start_response
        headers = self.headers
        applied_headers = headers.items()
        def new_start_response(status, headers, exc_info = None):
            try:
                if not self.headers_set:
                    self.headers_set = True
                return old_start_response(status, applied_headers, exc_info)
            except Exception as exc:
                self.debug(f"ERROR en set_new_start response: {str(exc)}")
                self.debug(f"INFO: {os.sys.exc_info()}")
            finally:
                return os.sys.stdout.write

        self.start_response = new_start_response

    def set_cookie(self, key, value, **attrs):
        self.headers.add_header('Set-Cookie', f'{key}={value}', **attrs)

    def get_cookie(self, key):
        return self.cookies.get(key, None)

    def redirect(self, path, status_code = 302, status_msg = "Found"):
        self.headers.add_header('Location', path)
        status_line = f"{status_code} {status_msg}"
        self.set_new_start_response(status = status_line)
        self.start_response(status_line, self.headers.items())
        return [status_line.encode("utf-8")]

###  Decorators
##   Content decorators

    def content_type(self, c_type = "text/html", charset = "utf-8", **attrs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                del self.headers['Content-Type']
                self.headers.add_header('Content-Type', c_type, charset = charset, **attrs)
                self.set_new_start_response()
                self.start_response("200 OK", self.headers.items())
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

##  Routing decorators

    def route(self, route_str, methods = ['GET']):
        def decorator(func):
            pattern, types = self.build_route_pattern(route_str)
            self.routes.append(Route(pattern, func, types, methods))
            return func
        return decorator

    def get(self, route_str):
        return self.route(route_str, methods = ['GET'])

    def post(self, route_str):
        return self.route(route_str, methods = ['POST'])

    def put(self, route_str):
        return self.route(route_str, methods = ['PUT'])

    def delete(self, route_str):
        return self.route(route_str, methods = ['DELETE'])

    def head(self, route_str):
        return self.route(route_str, methods = ['HEAD'])

    def _any(self, route_str):
        return self.route(route_str, methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD'])

###  End of decorators

    def __init__(self, name = None, **kwargs):
        "Prepares Bicchiere instance to run"

        # Register some common template filter functions
        Bicchiere.register_template_filter("title", str.title)
        Bicchiere.register_template_filter("capitalize", str.capitalize)
        Bicchiere.register_template_filter("upper", str.upper)
        Bicchiere.register_template_filter("lower", str.lower)

        # First, things that don't vary through calls
        self.name = name if name else random.choice(Bicchiere.bevande)
        self.session_manager = Bicchiere.config['session_manager_class']()
        self.routes = []

        # Call specific variables
        self.init_local_data()

        self.environ = None
        self.start_response = None
        self.headers = Headers()
        self.session = None
        self.cookies = SimpleCookie()

        # And whatever follows....
        for k in kwargs:
            self.__dict__[k] = kwargs[k]

### Thread specific properties, things which are in fact kept in a threading.local instance
### Necessary to handle multiprocessor/multithreading WSGI servers

    @property
    def environ(self):
        return self.__local_data.environ

    @environ.setter
    def environ(self, new_env):
        self.__local_data.environ = new_env

    @environ.deleter
    def environ(self):
        del self.__local_data.environ

    @property
    def start_response(self):
        return self.__local_data.start_response

    @start_response.setter
    def start_response(self, new_sr):
        self.__local_data.start_response = new_sr

    @start_response.deleter
    def start_response(self):
        del self.__local_data.start_response

    @property
    def headers(self):
        return self.__local_data.headers

    @headers.setter
    def headers(self, new_h):
        self.__local_data.headers = new_h

    @headers.deleter
    def headers(self):
        del self.__local_data.headers

    @property
    def session(self):
        return self.__local_data.session

    @session.setter
    def session(self, new_sess):
        self.__local_data.session = new_sess

    @session.deleter
    def session(self):
        del self.__local_data.session

    @property
    def cookies(self):
        return self.__local_data.cookies

    @cookies.setter
    def cookies(self, new_c):
        self.__local_data.cookies = new_c

    @cookies.deleter
    def cookies(self):
        del self.__local_data.cookies

    @property
    def args(self):
        return self.__local_data.args

    @args.setter
    def args(self, new_args):
        self.__local_data.args = new_args

    @args.deleter
    def args(self):
        del self.__local_data.args

    @property
    def form(self):
        return self.__local_data.form

    @form.setter
    def form(self, new_form):
        self.__local_data.form = new_form

    @form.deleter
    def form(self):
        del self.__local_data.form

    @property
    def headers_set(self):
        return self.__local_data.headers_set

    @headers_set.setter
    def headers_set(self, new_hs):
        self.__local_data.headers_set = new_hs
        self.debug(f"Setting var self.headers_set to {self.__local_data.headers_set}")

    @headers_set.deleter
    def headers_set(self):
        del self.__local_data.headers_set

    def _show_local_data(self):
        return self.__local_data.__dict__

    def get_session(self, sid):
        return self.session_manager.load_session(sid)

    def clear_headers(self):
        self.headers = Headers()

####

    def init_local_data(self):
        "Makes Bicchiere thread safe by assigning vars to thread local data"
        #self.debug("Initializing local data")
        self.__local_data = threading.local()

        self.__local_data.__dict__.setdefault('environ', None)
        self.__local_data.__dict__.setdefault('start_response', None)
        self.__local_data.__dict__.setdefault('headers', Headers())
        self.__local_data.__dict__.setdefault('session', None)
        self.__local_data.__dict__.setdefault('cookies', SimpleCookie())
        self.__local_data.__dict__.setdefault('args', None)
        self.__local_data.__dict__.setdefault('form', None)
        self.__local_data.__dict__.setdefault('headers_set', False)

    ### Template related stuff

    @staticmethod
    def get_template_dir():
        templates_root = Bicchiere.config.get('templates_directory', 'templates')
        return os.path.join(os.getcwd(), templates_root)

    @staticmethod
    def get_template_fullpath(template_file):
        return os.path.join(Bicchiere.get_template_dir(), template_file)

    @staticmethod
    def preprocess_template(tpl_str = TemplateLight.test_tpl):
        ftpl = StringIO(tpl_str)
        lines = ftpl.readlines()
        ftpl.close()
        for index, line in enumerate(lines):
            stripline = line.strip()
            m = re.match(r"\{\#\s+include\s+(?P<inc_file>[a-zA-Z0-9.\"\']+)\s+\#\}", stripline)
            if m:
                inc_file = m.group_dict().get("inc_file")
                if not inc_file:
                    raise TemplateSyntaxError("include directiva must refer to a file")
                fullpath = Bicchiere.get_template_fullpath(inc_file.replace("\"", "").replace("'", ""))
                if os.path.exists(fullpath) and os.path.isfile(fullpath):
                    fp = open(fullpath)
                    new_tpl_str = fp.read()
                    fp.close()
                    replace_line = Bicchiere.preprocess_template(new_tpl_str)
                    lines[index] = replace_line
                else:
                    raise TemplateSyntaxError("Included file {0} in line {1} does not exist.".format(inc_file, index))
        return "".join(lines)

    @staticmethod
    def compile_template(tpl_str = TemplateLight.test_tpl):
        if not tpl_str:
            return None
        words = tpl_str.split()
        if len(words) == 1:
            fullpath = Bicchiere.get_template_fullpath(tpl_str)
            if os.path.exists(fullpath) and os.path.isfile(fullpath):
                fp = open(fullpath)
                tpl_str = fp.read()
                fp.close()
        return TemplateLight(Bicchiere.preprocess_template(tpl_str), **Bicchiere.template_filters)

    @staticmethod
    def render_template(tpl_str = TemplateLight.test_tpl, **kw):
        if tpl_str.__class__.__name__ == "TemplateLight":
            return tpl_str.render(**kw)
        elif tpl_str.__class__.__name__ == "str":
            compiled = Bicchiere.compile_template(tpl_str)
            if compiled:
                return compiled.render(**kw)
            else:
                return None
        else:
            return None

    ### End of template related stuff


    def __call__(self, environ, start_response, **kwargs):
        self.init_local_data() # Most important to make this thing thread safe in presence of multithreaded/multiprocessing servers

        self.environ = environ
        self.start_response = start_response
        self.clear_headers()
        if self.session:
            del self.session
        self.session = None
        self.cookies = SimpleCookie()
        self.headers_set = False

        if self.environ is None:
            return

        for h in self.environ:
            if h.lower().endswith('cookie'):
                self.debug(f"\nLoading stored cookies: {h}: {self.environ[h]}")
                self.cookies = SimpleCookie(self.environ[h].strip().replace(' ', '_'))
                for h in self.cookies:
                    self.debug(f"Cookie {self.cookies.get(h).key} = {self.cookies.get(h).value}")
        self.environ['bicchiere_cookies'] = str(self.cookies).strip()

        sid = self.cookies.get('sid', None)
        if not sid:
            sid = self.cookies.get('_sid', None)
        if sid:
            sid = sid.value
        else:
            sid = uuid4().hex

        self.session = self.get_session(sid)
        self.session['USER_AGENT'.lower()] = self.environ['HTTP_USER_AGENT']
        self.session['REMOTE_ADDR'.lower()] = self.environ['REMOTE_ADDR']
        self.environ['bicchiere_session'] = self.session

        cookie_opts = {}
        cookie_opts['Max-Age'] = "3600"
        cookie_opts['HttpOnly'] = ""
        self.set_cookie('sid', sid, **cookie_opts)

        self.args = self.qs2dict(self.environ.get('QUERY_STRING', ''))
        #self.debug("Args from querystring: ", self.args)

        if self.environ.get('REQUEST_METHOD', 'GET') != 'GET':
            self.form = cgi.FieldStorage(fp = self.environ.get('wsgi.input'), environ = self.environ, keep_blank_values = 1)
        else:
            self.form = {}

    #def __iter__(self):

        response = None
        #status_msg = "404 Not found"
        status_msg = Bicchiere.get_status_line(404)

        static_root = Bicchiere.config.get('static_directory', 'static')
        static_path = f'/{static_root}'
        #static_dir = os.path.join(os.getcwd(), static_root)

        if self.environ.get('path_info'.upper()).startswith(static_path):
            found = False
            resource = f"{os.getcwd()}{self.environ.get('path_info'.upper())}"
            self.debug("Searching for resource '{}'".format(resource))
            if os.path.exists(resource):
                found = True
                self.debug(f"RESOURCE {resource} FOUND")
                if os.path.isfile(resource):
                    mime_type, _ = guess_type(resource) or ('text/plain', 'utf-8')
                    fp = open(resource, 'rb')
                    response = [b'']
                    r = fp.read(1024)
                    while r:
                        response.append(r)
                        r = fp.read(1024)
                    fp.close()
                    del self.headers['Content-Type']
                    self.headers.add_header('Content-Type', mime_type, charset = 'utf-8')
                    status_msg = Bicchiere.get_status_line(200)
                elif os.path.isdir(resource):
                    del self.headers['Content-Type']
                    self.headers.add_header('Content-Type', 'text/html', charset = 'utf-8')
                    if Bicchiere.config.get('allow_directory_listing', False) or Bicchiere.config.get('debug', False):
                        status_msg = Bicchiere.get_status_line(200)
                        response = ['<p style="margin-top: 15px;"><strong>Directory listing for&nbsp;</strong>']
                        response.append(f'<strong style="color: steelblue;">{self.environ.get("path_info".upper())}</strong><p><hr/>')
                        left, right = os.path.split(self.environ.get('path_info'.upper()))
                        if left != "/":
                            response.append(f'<p title="Parent directory"><a href="{left}">..</a></p>')
                        l = os.listdir(resource)
                        l.sort()
                        for f in l:
                            fullpath = os.path.join(resource, f)
                            if os.path.isfile(fullpath) or os.path.isdir(fullpath):
                                href = os.path.join(self.environ.get('path_info'.upper()) , f)
                                response.append(f'<p><a href="{href}">{f}</a></p>')
                    else:
                        status_msg = Bicchiere.get_status_line(403)
                        response =  [f'''<strong>403</strong>&nbsp;&nbsp;&nbsp;<span style="color: red;">
                                    {self.environ.get('path_info'.upper())}</span> Directory listing forbidden.''']
                else:
                    del self.headers['Content-Type']
                    self.headers.add_header('Content-Type', 'text/html', charset = 'utf-8')
                    status_msg = Bicchiere.get_status_line(400)
                    response =  [f'''<strong>400</strong>&nbsp;&nbsp;&nbsp;<span style="color: red;">
                                   {self.environ.get('path_info'.upper())}</span> Bad request, file type cannot be handled.''']
            else:
                self.debug(f"RESOURCE {resource} NOT FOUND")
                response =  [f'''<strong>404</strong>&nbsp;&nbsp;&nbsp;<span style="color: red;">
                                   {self.environ.get('path_info'.upper())}</span> not found.''']
                del self.headers['Content-Type']
                self.headers.add_header('Content-Type', 'text/html', charset = 'utf-8')
                status_msg = Bicchiere.get_status_line(404)

            self.set_new_start_response()
            self.start_response(status_msg, self.headers.items())
            for i in range(len(response)):
                yield self.tob(response[i])
            self.clear_headers()
            return b''

        if len(self.routes) == 0:
            if self.environ['path_info'.upper()] != '/':
                del self.headers['Content-Type']
                self.headers.add_header('Content-Type', 'text/html', charset = "utf-8")
                self.set_new_start_response()
                response =  f"404 {self.environ['path_info'.upper()]} not found."
            else:
                #status_msg = "200 OK"
                status_msg = Bicchiere.get_status_line(200)
                response = self.default_handler()
        else:
            route = None
            try:
                route = self.get_route_match(self.environ['PATH_INFO'])
                if route:
                    if self.environ.get('REQUEST_METHOD', 'GET') in route.methods:
                        status_msg = Bicchiere.get_status_line(200)
                        response = route.func(**route.args)
                    else:
                        del self.headers['Content-Type']
                        self.headers.add_header('Content-Type', 'text/html', charset = "utf-8")
                        self.set_new_start_response()
                        #status_msg = f'405 {self.get_status_codes()["405"]["status_msg"]}'
                        status_msg = Bicchiere.get_status_line(405)
                        response = f'''<strong>405</strong>&nbsp;&nbsp;&nbsp;Method&nbsp;
                                       <span style="color: red;">{self.environ["REQUEST_METHOD"]}</span>
                                       not allowed for this URL.'''
                else:
                    del self.headers['Content-Type']
                    self.headers.add_header('Content-Type', 'text/html', charset = "utf-8")
                    self.set_new_start_response()
                    status_msg = Bicchiere.get_status_line(404)
                    response = f'''<strong>404</strong>&nbsp;&nbsp;&nbsp;<span style="color: red;">
                                   {self.environ["PATH_INFO"]}</span> not found.'''
            except Exception as exc:
                del self.headers['Content-Type']
                self.headers.add_header('Content-Type', 'text/html', charset = "utf-8")
                self.set_new_start_response()
                status_msg = Bicchiere.get_status_line(500)
                response = f'''<strong>500</strong>&nbsp;&nbsp;&nbsp;
                                 <span style="color: red;">{self.environ["PATH_INFO"]}</span>
                                 raised an error: <span style="color: red;">{str(exc)}.</span>'''

        if not self.headers_set:
            if 'content-type' not in self.headers:
                if response and self.is_html(response):
                    self.headers.add_header('Content-Type', 'text/html', charset = 'utf-8');
                else:
                    self.headers.add_header('Content-Type', 'text/plain', charset = 'utf-8');
                self.set_new_start_response()
            self.start_response(status_msg, self.headers.items())

        if response:
            response = self.tob(response)
            self.debug(f"\n\nRESPONSE: '{response[ : 30].decode('utf-8')}...'")
            yield response
        else:
            yield b''

        self.clear_headers()
        return b''

    def get_route_match(self, path):
        "Used by the app to match received path_info vs. saved route patterns"
        for route in self.routes:
        #for route_pattern, view_function, methods, type_dict in self.routes:
            r = route.match(path)
            if r:
                return r
        return None

    def __str__(self):
        return f"{self.name} version {self.version}"


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
    def tob(s):
        retval = None
        if not hasattr(s, '__iter__'):
            #print("Not an iterable, returning an empty bytes string")
            retval = b''
        if type(s).__name__ == 'generator':
            #print("Got a generator, transforming it into a list")
            s = [x for x in s] # pack the generator in a list and then go on
        if len(s) == 0:
            #print(f"Length s for provided {s.__class__.__name__}, returning an empty bytes string")
            retval = b''
        elif type(s[0]) == int:
            #print("Got a byte string, returning it unchanged")
            retval =  s # It's a sequence of ints, i.e. bytes
        elif type(s[0]) == bytes:
            #print("Got a sequence of byte strings, joining it in one prev. to returning it.")
            retval = b''.join(s) # It's a sequence of byte strings
        elif type(s[0]) == str:
            #print(f"STRING: '{s[ : 20]}' ...")
            #if (len(s[0]) > 1):
            #    print(f"List of strings. First is '{s[0]}'. Joining the whole thing prev to return")
            #else:
            #    print("Just one string. Joining it prev to return")
            retval = b''.join([x.encode('utf-8') for x in s]) # encode each str to bytes prev to joining
            #print(f"Return value is: {retval}")
        else:
            retval = b''

        return retval

    @staticmethod
    def encode_image(image_data, image_type = 'image/jpeg'):
        img_template = "data:{0};base64,{1}"
        img_string = base64.b64encode(image_data).decode("utf-8")
        return img_template.format(image_type, img_string)

    @staticmethod
    def get_status_code(code = None):
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
                '500': {'section': 'Section 10.5.1', 'status_msg': 'Internal Server Error'},
                '501': {'section': 'Section 10.5.2', 'status_msg': 'Not Implemented'},
                '502': {'section': 'Section 10.5.3', 'status_msg': 'Bad Gateway'},
                '503': {'section': 'Section 10.5.4', 'status_msg': 'Service Unavailable'},
                '504': {'section': 'Section 10.5.5', 'status_msg': 'Gateway Time-out'},
                '505': {'section': 'Section 10.5.6',
                        'status_msg': 'HTTP Version not supported'}}
        return codes if not code else codes.get(str(code), codes.get('404'))

    @staticmethod
    def get_status_line(code = 404):
        return f"{code} {Bicchiere.get_status_code(str(code))['status_msg']}"

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
                    <link rel="icon" href="data:image/jpg;base64,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" type="image/jpeg">
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

    #@staticmethod
    #def group_capitalize(stri):
    #    return  ' '.join(list(map(lambda w: w.capitalize(), re.split(r'\s+', stri))))

    @staticmethod
    def get_favicon():
        favicon = 'data:image/jpg;base64,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'
        return favicon

    @staticmethod
    def get_img_favicon():
        return f'<img src="{Bicchiere.get_favicon()}" alt="favicon.ico" title="favicon"/>'

### End of static stuff

    def default_handler(self):
       del self.headers['content-type']
       self.headers.add_header('Content-Type', 'text/html', charset="utf-8")
       self.set_new_start_response()

       final_response = []
       final_response.append("""
       <!doctype html>
       <html lang=it><head><title>Bicchiere Environment Vars</title></head>
       <body style="color: blue; font-family: Helvetica; padding: 0.5em;">\n
       """)

       response = simple_demo_app(self.environ, self.start_response)

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
        if (not isinstance(filter_name, str)): #or (filter_func.__class__.__name__ != "function"):
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
    def demo_app(cls):
        bevanda = random.choice(Bicchiere.bevande)

        #Bicchiere.config['session_manager_class'] = SessionManager
        #Bicchiere.config['session_manager_class'] = FileSessionManager
        #Bicchiere.config['session_manager_class'] = DbSessionManager

        app = cls(f"Demo {bevanda} App")

        #prefix = Bicchiere.get_demo_prefix().format(normalize_css = Bicchiere.get_normalize_css(),
        #        demo_css = Bicchiere.get_demo_css())
        #suffix = Bicchiere.get_demo_suffix()

        #Demo page template includes 3 placeholders: 'page_title', 'menu_content' and 'main_contents'
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
        dropdown.addItem(MenuItem("Favicon - Text Mode", "/favicon.ico"))
        dropdown.addItem(MenuItem("Favicon - Image", "/img/favicon.ico"))
        menu.addItem(dropdown)
        
        dropdown = DropdownMenu("Session variables and cookies")
        dropdown.addItem(MenuItem("Session variables", "/showsession"))
        dropdown.addItem(MenuItem("Cookies", "/showcookies"))
        menu.addItem(dropdown)
        
        dropdown = DropdownMenu("Redirection Examples")
        dropdown.addItem(MenuItem("Factorial of 42", "/f42"))
        dropdown.addItem(MenuItem("The origin of everything: Python!", "/python"))
        dropdown.addItem(MenuItem("Python per noi...", "/python_it"))
        dropdown.addItem(MenuItem("WSGI (Web Server Gateway Interface, the tech behind Bicchiere) Wikipedia page", "/wsgiwiki"))
        dropdown.addItem(MenuItem("WSGI Python secret web weapon (Part I)", "/wsgisecret"))
        dropdown.addItem(MenuItem("WSGI Python secret web weapon (Part II)", "/wsgisecret2"))
        menu.addItem(dropdown)

        dropdown = DropdownMenu("Static Content Example")
        dropdown.addItem(MenuItem("Show '/static' directory", "/showstatic"))
        menu.addItem(dropdown)

        menu.addItem(MenuItem("About", "/about"))



        @app.get('/')
        @app.html_content()
        def home():
           randomcolor = random.choice(['red','blue','green', 'green', 'green', 'steelblue', 'navy', 'brown', '#990000'])
           #prefix = Bicchiere.get_demo_prefix().format(normalize_css = '', demo_css = Bicchiere.get_demo_css())
           heading =  "WSGI, Bicchiere Flavor"
           contents = '''<h2 style="font-style: italic">Buona sera, oggi beviamo un buon bicchiere di <span style="color: {0};">{1}</span>!</h2>'''
           contents = contents.format(randomcolor, bevanda)
           info = Bicchiere.get_demo_content().format(heading =  heading, contents = contents)
           #return "{}{}{}".format(prefix, info, suffix)
           #Demo page template includes 3 placeholders: 'page_title', 'menu_content' and 'main_contents'
           return Bicchiere.render_template(demo_page_template, 
           page_title = "Demo Bicchiere App - Home",
           menu_content = str(menu), 
           main_contents = info)
           
        @app.get('/favicon.ico')
        @app.html_content()
        def favicon():
            info = f"""
            <p>{Bicchiere.get_favicon()}</p>
            <p><a href="/">Home</a></p>
            """
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Favicon source",
            menu_content = str(menu), 
            main_contents = info)
           

        @app.get('/img/favicon.ico')
        @app.html_content()
        def favicon_img():
            info = f"""
            <p>{Bicchiere.get_img_favicon()}</p>
            <p><a href="/">Home</a></p>
            """
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Favicon source",
            menu_content = str(menu), 
            main_contents = info)

        @app.route("/upload", methods = ['GET', 'POST'])
        def upload():
            pinfo = "Arriverà presto..."
            if app.environ['request_method'.upper()] == 'GET':
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
                pinfo +=f'<div class="row"><label class="steelblue">Description</label><strong>{description}</strong></div></hr>'
                pinfo +=f'<div class="row"><label class="steelblue">Filename</label><strong>{filename}</strong></div></hr>'
                if filename:
                    pinfo +=f'<div class="row"><label class="steelblue">File length</label><strong>{body_len} bytes</strong></div></hr>'
                    if "image" in file_type:
                        img_src = Bicchiere.encode_image(body, file_type)
                        pinfo +=f'<div class="centered"><img src="{img_src}" style="max-width: 100%; height: auto;" /></div></hr>'
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

            heading =  "Upload Example"
            info = Bicchiere.get_demo_content().format(heading =  heading, contents = pinfo)
#            return "{}{}{}".format(prefix, info, suffix)
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Upload example",
            menu_content = str(menu), 
            main_contents = info)
           
        @app.get("/hello")
        @app.get("/hello/<who>")
        @app.html_content()
        def hello(who = app.name):
            if who == app.name and 'who' in app.args and len(app.args.get('who', '')):
                who = app.args.get('who')
            #heading = f"Benvenuto, {Bicchiere.group_capitalize(who)}!!!"
            heading = f"Benvenuto, {who.title()}!!!"
            info = Bicchiere.get_demo_content().format(heading =  heading, contents = "")
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Hello Page",
            menu_content = str(menu), 
            main_contents = info)

        @app.get("/showstatic")
        def showstatic():
            heading = 'Static Contents'
            contents ='''
                <div class="w60 panel">
                  <iframe src="/static" style="min-height: 22em; height: 22em; padding: 1em; border: none;"></iframe>
                </div>
                      '''
            info = Bicchiere.get_demo_content().format(heading =  heading, contents = contents)
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Contents of static directory",
            menu_content = str(menu), 
            main_contents = info)

        @app._any("/factorial")
        @app._any("/factorial/<int:number>")
        @app.html_content()
        def factorial(number = 7):
            if app.environ['REQUEST_METHOD'] == 'GET':
                n = number
            else:
                try:
                    n = int(app.form['number'].value)
                except Exception as exc:
                    app.debug("Exception in factorial: {}".format(str(exc)))
                    n = number
            result = reduce(lambda a, b: a * b, range(1, n + 1))
            pinfo = f'<div class="wrapped">El factorial de {n} es <br/>&nbsp;<br/>{result}</div>'
            info = Bicchiere.get_demo_content().format(heading =  "Factorials", contents = pinfo)
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Factorial",
            menu_content = str(menu), 
            main_contents = info)

        @app._any('/environ')
        def env():
            contents = ''.join([x for x in app.default_handler()])
            info = Bicchiere.get_demo_content().format(heading =  "", contents = contents)
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Environment vars",
            menu_content = str(menu), 
            main_contents = info)

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
            app.debug(f"POST: cookie posteada!   -   {app.form['key']}={app.form['value']}")
            if app.form['key'].value.lower() == 'sid':
                raise KeyError("SID cannot be modified/deleted. It's meant only for internal use")
            cookie_opts = {}
            if app.form['value'].value:
                if app.form['max_age'].value:
                    cookie_opts['Max-Age'] = app.form['max_age'].value
            else:
                cookie_opts['Max-Age'] = '0'

            app.set_cookie(key = app.form['key'].value.strip(),  value = app.form["value"].value.strip(), **cookie_opts)
            return app.redirect('/showcookies')

        @app.route("/showcookies", methods = ['GET'])
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
            info = Bicchiere.get_demo_content().format(heading =  "Cookies", contents = contents)
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Cookies",
            menu_content = str(menu), 
            main_contents = info)

        @app.route("/showsession", methods = ["GET", "POST"])
        @app.html_content()
        def showsession():
            if app.environ.get('request_method'.upper(), 'GET').upper() == "POST":
                if app.form['key'].value.lower() == 'sid':
                    raise KeyError("SID cannot be modified/deleted. It's meant only for internal use")
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
            info = Bicchiere.get_demo_content().format(heading =  "Session Data", contents = contents)
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - Session vars",
            menu_content = str(menu), 
            main_contents = info)

        @app.get("/about")
        def about():
            contents="""
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
            """
            info = Bicchiere.get_demo_content().format(heading =  "The proverbial about page", contents = contents)
            return Bicchiere.render_template(demo_page_template, 
            page_title = "Demo Bicchiere App - About page",
            menu_content = str(menu), 
            main_contents = info)

        return app

    @classmethod
    def get_version(cls):
        obj = cls()
        version = obj.version
        del obj
        return version

    def run(self, host = "localhost", port = 8086, application = None, server_name = None):
        application = application or self
        server_name = server_name or 'wsgiref'
        orig_server_name = server_name
        server_name = server_name.lower()

        if server_name not in self.known_servers:
            self.debug(f"Server '{orig_server_name}' not known as of now. Switching to built-in WsgiRef")
            server_name = 'wsgiref'

        server = None
        server_action = None

        if server_name == 'bjoern':
             application.config['debug'] = False
             try:
                 import bjoern as server
                 server_action = lambda: server.run(application, host, port)
             except Exception as exc:
                 print(f"Exception ocurred while trying to raise Bjoern: {str(exc)}")
                 server_name = 'wsgiref'

        if server_name == 'gunicorn':
             application.config['debug'] = False
             try:
                 from gunicorn.app.base import BaseApplication as server
                 server_action = lambda: server(application, {'workers': 4, 'bind': f'{host}:{port}'}).run()
             except Exception as exc:
                 print(f"Exception ocurred while trying to raise Gunicorn: {str(exc)}")
                 server_name = 'wsgiref'

        if server_name == 'wsgiref':
             application.config['debug'] = True
             server = make_server(host, port, application)
             server_action = server.serve_forever

        try:
            #server.serve_forever()
            print("\n\n", f"Running Bicchiere WSGI ({application.name}) version {Bicchiere.get_version()}",
                              f"using {(server_name or 'wsgiref').capitalize()}",
                              f"server on {host}:{port if port else ''}",
                              f"\n Current working file: {os.path.abspath(__file__)}", "\n")
            server_action()
        except KeyboardInterrupt:
            print("\n\nBicchiere è uscito del palco...\n")
        except Exception as exc:
            print(f"\n\n{'-' * 12}\nUnexpected exception: {str(exc)}\n{'-' * 12}\n")
        finally:
            if hasattr(server, 'socket') and hasattr(server.socket, 'close'):
                try:
                    if self.session_manager and self.session_manager.clock:
                        self.session_manager.clock.stop()
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
            print("\nBicchiere ha finito il suo compito.\n")

###  End main Bicchiere App class

### Miscelaneous exports

def demo_app():
    "Returns demo app for test purposes"
    return Bicchiere.demo_app()

application = demo_app() # Rende uWSGI felice :-)

def run(host = 'localhost', port = 8086, app = application, server_name = 'wsgiref'):
    "Shortcut to run demo app, or any WSGI compliant app, for that matter"
    runner = application
    runner.run(host, port, app, server_name)

###  End Miscelaneous exports



### Provervial main function

def main():
    "Executes demo app"

    import argparse
    parser = argparse.ArgumentParser(description='Command line arguments for Bicchiere')
    parser.add_argument('-p', '--port', type = int, default = 8086, help = "Server port number.")
    parser.add_argument('-a', '--addr', type = str, default = "127.0.0.1", help = "Server address.")
    parser.add_argument('-s', '--server', type = str, default = "wsgiref", help = "Server software.", choices = Bicchiere.known_servers)
    args = parser.parse_args()

    os.system("clear")
    run(port = args.port, host = args.addr, server_name = args.server)

if __name__ == '__main__':
    main()
