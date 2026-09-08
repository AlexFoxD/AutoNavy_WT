import threading
import inspect
import ctypes
import time

class thread_control:
    def __init__(self):
        pass

    class submit:
        """Run a callable repeatedly in a controllable background thread.

        Use ``pause()``, ``resume()``, and ``stop()`` to control execution.
        The wrapper already supplies the loop, so the submitted callable must
        not contain its own infinite loop.
        """

        def __init__(self, func, name, state=False, *args, **kwargs):
            self.func = func
            self.name = name
            self.args = args
            self.kwargs = kwargs
            self.result = None
            self.__flag = threading.Event()  # Controls whether the worker is paused.
            self.__flag.set()  # Start in the resumed state.
            self.__running = threading.Event()  # Controls worker termination.
            self.__running.set()  # Mark the worker as running.
            self.thread = threading.Thread(target=self.run, name=self.name)
            self.thread.setDaemon(state)
            self.thread.start()

        def run(self):
            while self.__running.is_set():
                self.__flag.wait()  # Block here while the worker is paused.
                try:
                    ret = self.func(*self.args, **self.kwargs)
                    self.result = ret
                except Exception as e:
                    print(e)
                    self.result = None
                # if ret == 'end':
                #     self.stop()
                #     break

        def pause(self):
            self.__flag.clear()  # Pause the worker at its next wait.

        def resume(self):
            self.__flag.set()  # Resume the worker.

        def stop(self):
            self.__flag.set()  # Wake a paused worker before stopping it.
            self.__running.clear()  # Mark the worker as stopped.
            self.shutdown(self.thread)

        def get_result(self):
            if self.result:
                return self.result
            elif self.result is None:
                return None
            else:
                return None

        def alive(self):
            alive = self.thread.is_alive()
            # print('{} is alive: {}'.format(self.name, alive))
            return alive

        def shutdown(self, thread):
            def _async_raise(tid, exctype):

                """raises the exception, performs cleanup if needed"""

                tid = ctypes.c_long(tid)
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))

                if not inspect.isclass(exctype):
                    exctype = type(exctype)

                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))

                if res == 0:

                    raise ValueError("invalid thread id")

                elif res != 1:

                    # """if it returns a number greater than one, you're in trouble,

                    # and you should call it again with exc=NULL to revert the effect"""

                    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)

                    raise SystemError("PyThreadState_SetAsyncExc failed")

            try:
                _async_raise(thread.ident, SystemExit)
            except:
                pass

    class once:
        def __init__(self, func, name, state=True, *args, **kwargs):
            self.func = func
            self.name = name
            self.args = args
            self.kwargs = kwargs
            self.result = None
            self.thread = threading.Thread(target=self.run, name=self.name)
            self.thread.setDaemon(state)
            self.thread.start()
        def run(self):
            self.result = self.func(*self.args, **self.kwargs)

        def stop(self):
            self.shutdown(self.thread)

        def get_result(self):
            if self.result:
                return self.result
            elif self.result is None:
                return None
            else:
                return None

        def shutdown(self, thread):
            def _async_raise(tid, exctype):

                """raises the exception, performs cleanup if needed"""

                tid = ctypes.c_long(tid)
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))

                if not inspect.isclass(exctype):
                    exctype = type(exctype)

                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))

                if res == 0:

                    raise ValueError("invalid thread id")

                elif res != 1:

                    # """if it returns a number greater than one, you're in trouble,

                    # and you should call it again with exc=NULL to revert the effect"""

                    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)

                    raise SystemError("PyThreadState_SetAsyncExc failed")

            try:
                _async_raise(thread.ident, SystemExit)
            except:
                pass

        def alive(self):
            alive = self.thread.is_alive()
            # print('{} is alive: {}'.format(self.name, alive))
            return alive


def attempt(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception as e:
        print(e)
        pass

def get_time():
    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))

if __name__ == '__main__':
    thread_control = thread_control()
    a = thread_control.once(get_time, 'get_time', True)
