# -*- coding: utf-8 -*-
"""GeoScope 订阅研报 -> data/subscriptions.json。
只拉文章清单(标题/日期/slug),不拉正文;链接指向本地 Obsidian 里已同步的笔记。
需要环境变量 GEOSCOPE_API_KEY;缺 key 或接口失败时保留上次存档。
"""
import json
import os
import re
import time
from urllib.parse import quote

from common import DATA_DIR, get_json, load_config, now_iso, save_json

API = "https://geoscopeapp.com/api/v1/member"


def _safe_name(s):
    """与本地 geoscope_client.py 完全一致的文件名规则,保证能拼出 vault 里的路径。"""
    s = re.sub(r"[^\w\-. ]+", "_", str(s)).strip().strip(".")
    return (s or "untitled")[:120]


def _as_list(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("data", "items", "articles", "publishers", "results", "list"):
            if isinstance(obj.get(k), list):
                return obj[k]
    return []


def _field(item, *names, default=""):
    if isinstance(item, dict):
        for n in names:
            if item.get(n) not in (None, ""):
                return item[n]
    return default


def _load_previous():
    try:
        with open(os.path.join(DATA_DIR, "subscriptions.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run():
    cfg = load_config().get("subscriptions", {})
    key = os.environ.get("GEOSCOPE_API_KEY", "").strip()
    pubs = cfg.get("publishers", [])
    vault = cfg.get("obsidian_vault", "")
    vdir = cfg.get("vault_dir", "")
    out = {"generated_at": now_iso(), "has_key": bool(key), "publishers": pubs, "items": []}
    fails = []

    if key:
        h = {"Authorization": f"Bearer {key}", "User-Agent": "geoscope-client/1.0",
             "Accept": "application/json"}
        for pub in pubs:
            try:
                d = get_json(
                    f"{API}/publishers/{quote(pub, safe='')}/articles?limit={cfg.get('per_publisher', 8)}",
                    headers=h,
                )
                for a in _as_list(d):
                    slug = _field(a, "slug", "id", "articleId")
                    title = _field(a, "title", "name", default=slug)
                    date = str(_field(a, "date", "published_at", "createdAt"))[:10]
                    if not slug or not title:
                        continue
                    note = f"{vdir}/{_safe_name(pub)}/{_safe_name(title)}__{_safe_name(slug)}.md"
                    obs = (f"obsidian://open?vault={quote(vault, safe='')}"
                           f"&file={quote(note, safe='')}") if vault else ""
                    out["items"].append({
                        "pub": pub, "title": title, "date": date,
                        "slug": slug, "obsidian": obs,
                    })
            except Exception as e:
                fails.append(f"{pub}: {e}")
            time.sleep(0.5)
        out["items"].sort(key=lambda x: x["date"], reverse=True)
        out["items"] = out["items"][: cfg.get("max_total", 30)]

    # 存档保护:没 key 或全部失败时,保留上次的清单
    if not out["items"]:
        prev = _load_previous()
        if prev and prev.get("items"):
            out["items"] = prev["items"]
            out["stale"] = True
    if fails:
        out["failed"] = fails

    save_json("subscriptions.json", out)
    if fails and not out["items"]:
        raise RuntimeError("GeoScope 全部失败: " + "; ".join(fails))
    return {
        "count": len(out["items"]),
        "status": ("ok" if key and not fails else
                   "缺 GEOSCOPE_API_KEY,已跳过" if not key else f"部分失败: {fails}"),
    }


if __name__ == "__main__":
    print(run())
