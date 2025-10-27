import os
import cv2
import numpy as np
from typing import Optional, Tuple, Dict
import mss


def pil_to_cv(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def take_screenshot_cv() -> np.ndarray:
    # Use mss to capture the full virtual screen to avoid Pillow/pyscreeze issues
    with mss.mss() as sct:
        monitor = sct.monitors[0]  # full virtual screen
        shot = sct.grab(monitor)
        frame = np.array(shot)  # BGRA
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame


def select_roi_and_save(out_path: str) -> Tuple[int, int, int, int]:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    frame = take_screenshot_cv()
    r = cv2.selectROI("Select ROI (press ENTER to confirm)", frame, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = map(int, r)
    if w == 0 or h == 0:
        raise ValueError("No ROI selected")
    crop = frame[y:y+h, x:x+w]
    cv2.imwrite(out_path, crop)
    return x, y, w, h


def _preprocess(img_gray: np.ndarray, method: str) -> np.ndarray:
    method = (method or "none").lower()
    if method == "canny":
        return cv2.Canny(img_gray, 50, 150)
    if method == "threshold":
        _, th = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return th
    # default: gentle blur + gray
    return cv2.GaussianBlur(img_gray, (3, 3), 0)


def locate_template_on_screen(
    template_path: str,
    threshold: float = 0.85,
    preprocess: str = "none",
    multi_scale: bool = False,
) -> Optional[Dict]:
    screen = take_screenshot_cv()
    screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    screen_prep = _preprocess(screen_gray, preprocess)

    template_gray = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if template_gray is None:
        raise FileNotFoundError(f"Template not found: {template_path}")
    template_prep = _preprocess(template_gray, preprocess)

    best = None
    def try_match(tpl: np.ndarray):
        nonlocal best
        if tpl.shape[0] < 5 or tpl.shape[1] < 5:
            return
        res = cv2.matchTemplate(screen_prep, tpl, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if best is None or max_val > best[0]:
            best = (max_val, max_loc, tpl.shape[::-1])  # (score, (x,y), (w,h))

    if multi_scale:
        for scale in np.linspace(0.6, 1.4, 9):
            h, w = template_prep.shape
            nh, nw = int(h * scale), int(w * scale)
            if nh < 5 or nw < 5:
                continue
            tpl = cv2.resize(template_prep, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
            try_match(tpl)
    else:
        try_match(template_prep)

    if best is None or best[0] < threshold:
        return None
    score, (x, y), (w, h) = best
    cx, cy = x + w // 2, y + h // 2
    return {"bbox": (x, y, w, h), "center": (cx, cy), "score": float(score)}
