# -*- coding: utf-8 -*-
"""OpenRouter -> data/openrouter.json。
- 公开接口: 模型目录(新上架模型、总数、定价) —— 无需 key
- datasets 接口: 每日 Top50 模型 token 排行 —— 需要环境变量 OPENROUTER_API_KEY
"""
import json
import os
from datetime import date, timedelta

from common import DATA_DIR, get_json, load_config, now_iso, save_json

API = "https://openrouter.ai/api/v1"


def _load_previous():
    """读取上一次的抓取结果,用于缺 Key / 接口失败时保留排行存档。"""
    try:
        with open(os.path.join(DATA_DIR, "openrouter.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run():
    cfg = load_config().get("openrouter", {})
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    out = {"generated_at": now_iso(), "has_key": bool(key)}

    # ---- 公开: 模型目录(仅取总数,用于缺 key 时的提示文案) ----
    d = get_json(API + "/models")
    out["model_count"] = len(d.get("data", []))

    # ---- 需 key: 每日 token 排行 ----
    rankings_status = "缺 OPENROUTER_API_KEY,已跳过"
    if key:
        try:
            h = {"Authorization": f"Bearer {key}"}
            days = cfg.get("rankings_days", 30)
            start = (date.today() - timedelta(days=days)).isoformat()
            r = get_json(API + f"/datasets/rankings-daily?start_date={start}", headers=h)
            out["daily"] = [{
                "d": x.get("date"),
                "m": x.get("model_permaslug"),
                "t": int(x.get("total_tokens") or 0),
            } for x in r.get("data", [])]
            rankings_status = "ok"
            # App 排行(接口结构未完全公开,拿到什么存什么,前端做防御性渲染)
            try:
                a = get_json(API + "/datasets/app-rankings", headers=h)
                raw = a.get("data")
                out["apps_raw"] = raw[:100] if isinstance(raw, list) else raw
            except Exception:
                out["apps_raw"] = None
        except Exception as e:
            rankings_status = f"排行接口失败: {e}"

    # ---- 存档保护:本次没拿到排行,就保留上一次的 ----
    if "daily" not in out:
        prev = _load_previous()
        if prev and prev.get("daily"):
            out["daily"] = prev["daily"]
            out["apps_raw"] = prev.get("apps_raw")
            out["rankings_stale"] = True
            rankings_status += "(已保留上次排行存档)"

    save_json("openrouter.json", out)
    return {"count": out["model_count"], "rankings": rankings_status}


if __name__ == "__main__":
    print(run())
