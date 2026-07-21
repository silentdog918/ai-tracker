# -*- coding: utf-8 -*-
"""公共工具:HTTP 请求(带重试)、JSON 读写。全部用标准库,零依赖。"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (compatible; ai-jingqidu-tracker/1.0; personal use)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")


def http_get(url, timeout=30, retries=2, headers=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - 单源失败不致命,由上层记录
            last = e
            if i < retries:
                time.sleep(1.5 * (i + 1))
    raise last


def get_json(url, **kw):
    return json.loads(http_get(url, **kw).decode("utf-8"))


def save_json(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  -> data/{name} 已写入")


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
