"""Lazy Windows transport and owned hotkeys; no physical work at import."""
from dataclasses import replace
import ctypes
import threading
from ctypes import wintypes
from autonavy.windows import WindowsGeometry


class PhysicalPointer:
    def __init__(self, *, api=None): self.api=api
    def move(self,x,y):
        if self.api is None:
            self.api=ctypes.WinDLL('user32',use_last_error=True)
            self.api.SetPhysicalCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]
            self.api.SetPhysicalCursorPos.restype=wintypes.BOOL
        if not self.api.SetPhysicalCursorPos(int(x),int(y)):
            raise OSError(ctypes.get_last_error(),'Physical cursor input failed')


class OwnedVJoy:
    """One acquired SDK device, actual driver ranges and explicit VOID relinquish."""
    AXES={'X':0x30,'Y':0x31,'Z':0x32,'RY':0x34}
    def __init__(self, device_id, *, api=None, neutral=16384):
        self.device_id=device_id; self.ranges={}; self.acquired=False
        if api is None:
            # Preserve installed/frozen pyvjoy SDK discovery and existing packaged DLL.
            from pyvjoy import _sdk
            api=_sdk._vj
            signatures={
                'AcquireVJD':([wintypes.UINT],wintypes.BOOL),
                'RelinquishVJD':([wintypes.UINT],None),
                'GetVJDAxisExist':([wintypes.UINT,wintypes.UINT],wintypes.BOOL),
                'GetVJDAxisMin':([wintypes.UINT,wintypes.UINT,ctypes.POINTER(wintypes.LONG)],wintypes.BOOL),
                'GetVJDAxisMax':([wintypes.UINT,wintypes.UINT,ctypes.POINTER(wintypes.LONG)],wintypes.BOOL),
                'GetVJDButtonNumber':([wintypes.UINT],ctypes.c_int),
                'SetAxis':([wintypes.LONG,wintypes.UINT,wintypes.UINT],wintypes.BOOL),
                'SetBtn':([wintypes.BOOL,wintypes.UINT,ctypes.c_ubyte],wintypes.BOOL),
            }
            for name,(args,result) in signatures.items():
                method=getattr(api,name); method.argtypes=args; method.restype=result
        self.api=api
        for name in self.AXES:
            low,high=self._range(name)
            if name!='RY' and not low <= neutral <= high:
                raise RuntimeError('Configured vJoy neutral is outside device range')
        if api.GetVJDButtonNumber(device_id)<8:
            raise RuntimeError('Configured vJoy buttons 1 through 8 are required')
        if not api.AcquireVJD(device_id): raise RuntimeError('Cannot acquire configured vJoy device')
        self.acquired=True

    def _range(self,name):
        axis=self.AXES[name]
        if name not in self.ranges:
            minimum,maximum=wintypes.LONG(),wintypes.LONG()
            if not (self.api.GetVJDAxisExist(self.device_id,axis)
                    and self.api.GetVJDAxisMin(self.device_id,axis,ctypes.byref(minimum))
                    and self.api.GetVJDAxisMax(self.device_id,axis,ctypes.byref(maximum))
                    and minimum.value < maximum.value):
                raise RuntimeError(f'Invalid or missing vJoy {name} axis range')
            self.ranges[name]=minimum.value,maximum.value
        return self.ranges[name]

    def axis(self,name,value,neutral):
        if not self.acquired: raise RuntimeError('vJoy device is closed')
        axis=self.AXES[name]
        low,high=self._range(name)
        value=max(0 if name=='RY' else -100,min(100,value))
        if name=='RY': raw=low+(high-low)*value/100
        else:
            if not low <= neutral <= high: raise RuntimeError('Configured vJoy neutral is outside device range')
            raw=neutral+value/100*(high-neutral if value>=0 else neutral-low)
        if not self.api.SetAxis(round(raw),self.device_id,axis): raise RuntimeError('vJoy axis input failed')

    def button(self,button,value):
        if not 1 <= button <= self.api.GetVJDButtonNumber(self.device_id):
            raise RuntimeError('Configured vJoy button is unavailable')
        if not self.api.SetBtn(int(bool(value)),self.device_id,button): raise RuntimeError('vJoy button input failed')

    def close(self):
        if self.acquired:
            self.api.RelinquishVJD(self.device_id)  # Official SDK signature is VOID.
            self.acquired=False


class WindowsBackend:
    physical = True
    neutral_resources=tuple(('axis',a) for a in ('X','Y','Z','RY'))+tuple(('button',str(n)) for n in range(1,9))
    def __init__(self, settings=None, *, pdi=None, win32=None, vjoy_factory=None, pointer=None):
        self.settings = settings
        self.pdi, self.win32, self.vjoy_factory = pdi,win32,vjoy_factory
        self.pointer=pointer if pointer is not None else PhysicalPointer()
        self.joy = None
        self._pause = None

    def start(self):
        if self.pdi is None:
            import pydirectinput
            self.pdi = pydirectinput
        if self.win32 is None:
            import win32api
            self.win32 = win32api
        self._pause = self.pdi.PAUSE
        self.pdi.PAUSE = 0  # Explicit startup only; FAILSAFE is deliberately preserved.

    def _joystick(self):
        if self.joy is None:
            self.joy=(self.vjoy_factory() if self.vjoy_factory is not None else
                      OwnedVJoy(self.settings.vjoy_device_id,neutral=self.settings.vjoy_neutral))
        return self.joy

    def dispatch(self, action, resource, value):
        if action=='wheel' and value==0: return
        release = action in {'key','mouse','axis','button'} and value == 0
        if not release: self.pdi.failSafeCheck()
        if action == 'key':
            if value: result=self.pdi.keyDown(resource)
            else:
                # Bypass only the decorator on key UP so the corner failsafe cannot
                # prevent emergency neutralization. Never change global FAILSAFE.
                method=self.pdi.keyUp
                raw=getattr(method,'__wrapped__',None)
                if raw is None: result=method(resource,_pause=False)
                elif getattr(method,'__self__',None) is not None: result=raw(method.__self__,resource,_pause=False)
                else: result=raw(resource,_pause=False)
            if result is not True: raise RuntimeError('Keyboard input was not fully inserted')
        elif action == 'mouse':
            flags = {'left':(0x0002,0x0004),'right':(0x0008,0x0010),'middle':(0x0020,0x0040)}
            self.win32.mouse_event(flags[resource][not bool(value)],0,0,0,0)
        elif action == 'move': self.win32.mouse_event(0x0001,int(value[0]),int(value[1]),0,0)
        elif action == 'position': self.pointer.move(*value)
        elif action == 'wheel':
            if value: self.win32.mouse_event(0x0800,0,0,int(value)*120,0)
        elif action == 'button': self._joystick().button(int(resource),value)
        elif action == 'axis':
            self._joystick().axis(resource,value,self.settings.vjoy_neutral if self.settings else 16384)

    def restore_timing(self):
        if self._pause is not None:
            self.pdi.PAUSE = self._pause
            self._pause = None

    def close(self):
        self.restore_timing()
        if self.joy is not None: self.joy.close()


class LiveWindowGuard:
    def __init__(self, settings, *, geometry=None, foreground=None):
        self.settings = settings
        self.geometry = geometry if geometry is not None else WindowsGeometry(settings.geometry)
        self.foreground = foreground

    def __call__(self, packet):
        if packet is None or packet.geometry is None: return False
        try:
            current = self.geometry.snapshot(packet.geometry.frame_size)
            if self.settings.capture.backend == 'obs':
                current = replace(current, content_rect=self.settings.geometry.obs_content_rect)
            if self.foreground is None:
                api = ctypes.WinDLL('user32',use_last_error=True)
                api.GetForegroundWindow.argtypes = []
                api.GetForegroundWindow.restype = wintypes.HWND
                focused = int(api.GetForegroundWindow() or 0)
            else: focused = self.foreground()
            return (current.recognition_supported and current.geometry_id == packet.geometry_id
                    and focused == current.window_handle)
        except (ValueError,OSError):
            return False


class Hotkeys:
    def __init__(self, settings, stop_signal, pause_signal, *, keyboard=None):
        self.settings, self.stop_signal, self.pause_signal = settings,stop_signal,pause_signal
        self.keyboard = keyboard
        self.handles = []
        self._lock=threading.RLock()
        self._closed=False; self._started=False

    def start(self):
        with self._lock:
            if self._closed or self._started: return
            self._started=True
            if self.keyboard is None:
                import keyboard
                self.keyboard = keyboard
            for key, callback in ((self.settings.emergency_stop_key,self.stop_signal),
                                  (self.settings.pause_key,self.pause_signal)):
                self.handles.append(self.keyboard.add_hotkey(key,callback))

    def close(self):
        with self._lock:
            self._closed=True
            errors=[]
            for handle in tuple(self.handles):
                try:
                    self.keyboard.remove_hotkey(handle)
                    self.handles.remove(handle)
                except Exception as exc: errors.append(str(exc))
            if errors: raise RuntimeError('; '.join(errors))
