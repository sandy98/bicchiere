# Following classes are deprecated. Formerly designed for support , dropped since v 0.3.0
# Kept here for reference, bound to be erased

class EventEmitter:
    "Utility class for adding objects the ability to emit events and registering handlers. Meant to be used as a mixin."

    def __init__(self, name='EventEmitter'):
        self.name = name
        self.event_handlers = {}

    def __repr__(self):
        return f"""
                Name:           {self.name}
                Handlers:       {self.event_handlers.items()}
                """

    def __str__(self):
        return repr(self)

    def emit(self, event_name="change", event_data={}):
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
    def __init__(self, name="EventedDict", *args, **kwargs):
        super(EventedDict, self).__init__(*args, **kwargs)
        self.name = name
        self.event_handlers = {}

    def __del__(self):
        # self.publish_change()
        self.publish_terminate()

    def __setitem__(self, key, value):
        super(EventedDict, self).__setitem__(key, value)
        self.publish_change(key, value)

    def __delitem__(self, key):
        super(EventedDict, self).__delitem__(key)
        self.publish_change(key, None)

    def __getattr__(self, key):
        return super(EventedDict, self).get(key, None)

    def publish_change(self, key=None, value=None):
        print(
            f"{self.__class__.__name__} emitting change event with key: {key} = value: {value}")
        self.emit("change", {'key': key, 'value': value, 'obj': self})

    def publish_terminate(self):
        print(f"{self.__class__.__name__} emitting terminate event")
        self.emit("terminate", self)


class Clock(EventEmitter):
    def __init__(self, seconds=0, name="Clock"):
        super(Clock, self).__init__(name)
        self.seconds = seconds
        self.interval = Bicchiere.config['session_saving_interval']
        self.running = False
        self.runner = None

    @staticmethod
    def pad(text, pad_len=4, pad_char='0', pad_left=True):
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
        self.runner = threading.Thread(
            name=f"{self.name}-runner", target=self.run, args=(self,), daemon=True)
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

    def __init__(self, sid=None, name=None, *args, **kwargs):
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

    def __init__(self, name='EventHandler'):
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

# End of deprecated classes
