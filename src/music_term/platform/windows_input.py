"""Preserve ConPTY-generated escape sequences in native Windows terminals."""
import asyncio
import ctypes
from ctypes import wintypes
from textual.drivers import win32
from textual.drivers.windows_driver import WindowsDriver
from textual.drivers._writer_thread import WriterThread
from textual._xterm_parser import XTermParser


def key_character(key_event) -> str:
    """Synthetic VT characters may carry modifier flags and a zero virtual key."""
    char = key_event.uChar.UnicodeChar
    return char if key_event.bKeyDown and char != '\x00' else ''


class InputMonitor(win32.EventMonitor):
    def run(self) -> None:
        parser = XTermParser()
        kernel = win32.KERNEL32
        read_console = kernel.ReadConsoleInputW
        read_console.argtypes = [wintypes.HANDLE, ctypes.POINTER(win32.INPUT_RECORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        read_console.restype = wintypes.BOOL
        handle = win32.GetStdHandle(win32.STD_INPUT_HANDLE)
        records = (win32.INPUT_RECORD * 1024)()
        count = wintypes.DWORD()
        try:
            while not self.exit_event.is_set():
                for event in parser.tick():
                    self.process_event(event)
                if win32.wait_for_handles([handle], 100) is None:
                    continue
                if not read_console(handle, records, 1024, ctypes.byref(count)):
                    raise ctypes.WinError(ctypes.get_last_error())
                keys = []
                size = None
                for record in records[:count.value]:
                    if record.EventType == 1:
                        keys.append(key_character(record.Event.KeyEvent))
                    elif record.EventType == 4:
                        dimensions = record.Event.WindowBufferSizeEvent.dwSize
                        size = (dimensions.X, dimensions.Y)
                text = ''.join(keys)
                if text:
                    text = text.encode('utf-16', 'surrogatepass').decode('utf-16')
                    for event in parser.feed(text):
                        self.process_event(event)
                if size is not None:
                    self.on_size_change(*size)
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Windows terminal input failed')


class NativeWindowsDriver(WindowsDriver):
    def start_application_mode(self) -> None:
        self._restore_console = win32.enable_application_mode()
        self._writer_thread = WriterThread(self._file)
        self._writer_thread.start()
        self.write('\x1b[?1049h')
        self._enable_mouse_support()
        self.write('\x1b[?25l\x1b[?1004h\x1b[>1u')
        self.flush()
        self._enable_bracketed_paste()
        self._event_thread = InputMonitor(asyncio.get_running_loop(), self._app, self.exit_event, self.process_message)
        self._event_thread.start()
