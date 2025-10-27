import json
import time
from typing import List, Dict
from pynput import mouse, keyboard


class Recorder:
    def __init__(self):
        self.events: List[Dict] = []
        self._start_time = None
        self._mouse_listener = None
        self._kb_listener = None
        self._mods = set()  # current modifiers: {'ctrl','alt','shift','win'}

    def _ts(self):
        return time.time() - self._start_time

    def on_move(self, x, y):
        self.events.append({"type": "move", "x": x, "y": y, "t": self._ts()})

    def on_click(self, x, y, button, pressed):
        self.events.append({
            "type": "click",
            "x": x,
            "y": y,
            "button": str(button),
            "pressed": pressed,
            "t": self._ts()
        })

    def on_scroll(self, x, y, dx, dy):
        self.events.append({"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy, "t": self._ts()})

    @staticmethod
    def _key_name(key) -> str:
        try:
            if hasattr(key, 'char') and key.char is not None:
                return key.char
        except Exception:
            pass
        k = str(key)
        # Normalize common special keys
        mapping = {
            'Key.ctrl': 'ctrl', 'Key.ctrl_l': 'ctrl', 'Key.ctrl_r': 'ctrl',
            'Key.alt': 'alt', 'Key.alt_l': 'alt', 'Key.alt_r': 'alt',
            'Key.shift': 'shift', 'Key.shift_l': 'shift', 'Key.shift_r': 'shift',
            'Key.cmd': 'win', 'Key.cmd_l': 'win', 'Key.cmd_r': 'win', 'Key.win': 'win',
            'Key.enter': 'enter', 'Key.tab': 'tab', 'Key.esc': 'esc',
            'Key.backspace': 'backspace', 'Key.delete': 'delete',
            'Key.up': 'up', 'Key.down': 'down', 'Key.left': 'left', 'Key.right': 'right',
            'Key.space': 'space',
        }
        return mapping.get(k, k.replace('Key.', ''))

    def _is_control_hotkey(self, main_key: str) -> bool:
        # Ignore Alt+1/Alt+2/Alt+3 in recording
        return (self._mods == {'alt'} and main_key in {'1', '2', '3'})

    def on_press(self, key):
        name = self._key_name(key)
        if name in {'ctrl', 'alt', 'shift', 'win'}:
            self._mods.add(name)
            # 不记录单独的修饰键按下，避免与 hotkey 事件重复
            return
        # If there are modifiers, record as hotkey
        if self._mods:
            if self._is_control_hotkey(name):
                # Do not record the control hotkeys
                return
            keys = sorted(list(self._mods)) + [name]
            self.events.append({"type": "hotkey", "keys": keys, "t": self._ts()})
        else:
            self.events.append({"type": "key", "action": "press", "key": name, "t": self._ts()})

    def on_release(self, key):
        name = self._key_name(key)
        if name in {'ctrl', 'alt', 'shift', 'win'}:
            if name in self._mods:
                self._mods.remove(name)
            return
        # For non-modifier release, we can skip explicit release if we already recorded hotkey
        # Still record release for non-modifier singles
        if not self._mods:
            self.events.append({"type": "key", "action": "release", "key": name, "t": self._ts()})

    def start(self):
        self._start_time = time.time()
        self._mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click,
            on_scroll=self.on_scroll,
        )
        self._kb_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release,
        )
        self._mouse_listener.start()
        self._kb_listener.start()

    def stop(self):
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._kb_listener:
            self._kb_listener.stop()

    def save(self, out_path: str):
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({"events": self.events}, f, ensure_ascii=False, indent=2)
