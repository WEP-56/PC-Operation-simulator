import json
import os
import zipfile
from typing import List


def export_project(out_zip: str, files: List[str], resource_dirs: List[str]):
    os.makedirs(os.path.dirname(out_zip) or ".", exist_ok=True)
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if os.path.isfile(f):
                zf.write(f, arcname=os.path.basename(f))
        for d in resource_dirs:
            if not os.path.isdir(d):
                continue
            for root, _, filenames in os.walk(d):
                for name in filenames:
                    path = os.path.join(root, name)
                    arcname = os.path.relpath(path, os.path.dirname(d))
                    zf.write(path, arcname=arcname)


def import_project(zip_path: str, extract_to: str):
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_to)
