import json
from typing import List, Dict
from .vision import locate_template_on_screen
from .player import simple_action


def run_sequence(sequence_json: str, threshold: float = 0.85):
    with open(sequence_json, 'r', encoding='utf-8') as f:
        steps: List[Dict] = json.load(f).get("steps", [])
    for step in steps:
        template = step["template"]
        action = step.get("action", "click")
        params = step.get("params", {})
        preprocess = step.get("preprocess", "none")
        multi_scale = bool(step.get("multi_scale", False))
        found = locate_template_on_screen(template, threshold=threshold, preprocess=preprocess, multi_scale=multi_scale)
        if found:
            x, y = found["center"]
            simple_action(action, x, y, params=params)


def add_sequence_step(sequence_json: str, template: str, action: str = "click", params: Dict = None, preprocess: str = "none", multi_scale: bool = False):
    try:
        with open(sequence_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"steps": []}
    item = {"template": template, "action": action}
    if params:
        item["params"] = params
    if preprocess and preprocess != "none":
        item["preprocess"] = preprocess
    if multi_scale:
        item["multi_scale"] = True
    data.setdefault("steps", []).append(item)
    with open(sequence_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_conditionals(conditionals_json: str, threshold: float = 0.85):
    with open(conditionals_json, 'r', encoding='utf-8') as f:
        items: List[Dict] = json.load(f).get("items", [])
    # choose highest priority among matched templates
    matched: List[Dict] = []
    for it in items:
        template = it["template"]
        preprocess = it.get("preprocess", "none")
        multi_scale = bool(it.get("multi_scale", False))
        res = locate_template_on_screen(template, threshold=threshold, preprocess=preprocess, multi_scale=multi_scale)
        if res:
            it = {**it, **res}
            matched.append(it)
    if not matched:
        return
    matched.sort(key=lambda x: x.get("priority", 1), reverse=True)
    top = matched[0]
    x, y = top["center"]
    action = top.get("action", "click")
    params = top.get("params", {})
    simple_action(action, x, y, params=params)


def add_conditional_item(conditionals_json: str, template: str, action: str = "click", priority: int = 1, params: Dict = None, preprocess: str = "none", multi_scale: bool = False):
    try:
        with open(conditionals_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"items": []}
    item = {"template": template, "action": action, "priority": int(priority)}
    if params:
        item["params"] = params
    if preprocess and preprocess != "none":
        item["preprocess"] = preprocess
    if multi_scale:
        item["multi_scale"] = True
    data.setdefault("items", []).append(item)
    with open(conditionals_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_sequence(sequence_json: str, steps: List[Dict]):
    data = {"steps": steps or []}
    with open(sequence_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
