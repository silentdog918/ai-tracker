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


def _price_per_m(m, k):
    try:
        return round(float(m["pricing"][k]) * 1e6, 3)
    except Exception:
        return None


def run():
    cfg = load_config().get("openrouter", {})
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    out = {"generated_at": now_iso(), "has_key": bool(key)}

    # ---- 公开: 模型目录 ----
    d = get_json(API + "/models")
    models = d.get("data", [])
    out["model_count"] = len(models)

    def _real_model(m):
        # 过滤 Auto Router 之类的伪模型(定价为负)
        p = _price_per_m(m, "prompt")
        return p is None or p >= 0

    newest = sorted(
        (m for m in models if _real_model(m)),
        key=lambda m: m.get("created") or 0, reverse=True,
    )[:12]
    out["new_models"] = [{
        "id": m.get("id"),
        "name": m.get("name") or m.get("id"),
        "created": m.get("created"),
        "prompt_usd_per_m": _price_per_m(m, "prompt"),
        "completion_usd_per_m": _price_per_m(m, "completion"),
        "context": m.get("context_length"),
    } for m in newest]

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
