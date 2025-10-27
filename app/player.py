import json
import time
import pyautogui
from typing import Dict, Optional

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.0
try:
    # Reduce internal throttling in PyAutoGUI
    pyautogui.MINIMUM_DURATION = 0.0
    pyautogui.MINIMUM_SLEEP = 0.0
except Exception:
    pass


def _sleep_until(next_t: float, start_time: float):
    now = time.time()
    target_abs = start_time + next_t
    if target_abs > now:
        time.sleep(target_abs - now)


def play_recording(json_path: str, loop: int = 1, interval: float = 1.0, pause: float = 0.0):
    # Ensure no extra implicit delay is added between actions
    try:
        pyautogui.PAUSE = float(pause)
    except Exception:
        pyautogui.PAUSE = 0.0
    with open(json_path, 'r', encoding='utf-8') as f:
        data: Dict = json.load(f)
    events = data.get("events", [])

    for i in range(loop):
        start_run = time.time()
        base_t = events[0]["t"] if events else 0.0
        for ev in events:
            t = max(0.0, ev.get("t", 0.0) - base_t)
            _sleep_until(t, start_run)
            et = ev.get("type")
            if et == "move":
                pyautogui.moveTo(ev["x"], ev["y"], duration=0.0)
            elif et == "click":
                if ev.get("pressed"):
                    # skip press event; act on release to avoid double action
                    continue
                btn = ev.get("button", "Button.left")
                button = "left" if "left" in btn else ("right" if "right" in btn else "middle")
                pyautogui.click(ev["x"], ev["y"], button=button)
            elif et == "scroll":
                pyautogui.scroll(ev.get("dy", 0), x=ev["x"], y=ev["y"]) 
            elif et == "key":
                key = ev.get("key")
                action = ev.get("action")
                if action == "press":
                    try:
                        pyautogui.keyDown(key)
                    except Exception:
                        pass
                elif action == "release":
                    try:
                        pyautogui.keyUp(key)
                    except Exception:
                        pass
            elif et == "hotkey":
                keys = ev.get("keys", [])
                if keys:
                    try:
                        norm = [
                            ('winleft' if k == 'win' else k)
                            for k in keys
                        ]
                        pyautogui.hotkey(*norm)
                    except Exception:
                        pass
        if i < loop - 1:
            time.sleep(interval)

def simple_action(action: str, x: int, y: int, params: Optional[Dict] = None):
    params = params or {}
    if action == "click":
        button = params.get("button", "left")
        clicks = int(params.get("clicks", 1))
        interval = float(params.get("interval", 0.0))
        pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
    elif action == "double":
        pyautogui.doubleClick(x, y)
    elif action == "right_click":
        pyautogui.click(x, y, button='right')
    elif action == "move_duration":
        duration = float(params.get("duration", 0.3))
        pyautogui.moveTo(x, y, duration=duration)
    elif action == "long_press":
        button = params.get("button", "left")
        duration = float(params.get("duration", 0.5))
        pyautogui.mouseDown(x=x, y=y, button=button)
        time.sleep(duration)
        pyautogui.mouseUp(x=x, y=y, button=button)
    elif action == "drag":
        to_x = int(params.get("to_x", x))
        to_y = int(params.get("to_y", y))
        duration = float(params.get("duration", 0.2))
        button = params.get("button", "left")
        pyautogui.moveTo(x, y)
        pyautogui.dragTo(to_x, to_y, duration=duration, button=button)
    else:
        duration = float(params.get("duration", 0.1))
        pyautogui.moveTo(x, y, duration=duration)
