# -*- coding: utf-8 -*-
"""npm + PyPI 下载量 -> data/downloads.json。开发者生态领先指标。"""
import time
from datetime import date, timedelta

from common import get_json, load_config, now_iso, save_json


def _wow(series):
    """用最近 7 天和上一个 7 天的合计算环比。"""
    vs = [p["v"] for p in series]
    last7 = sum(vs[-7:])
    prev7 = sum(vs[-14:-7])
    pct = round((last7 / prev7 - 1) * 100, 1) if prev7 else None
    return {"last7": last7, "prev7": prev7, "wow_pct": pct}


def run():
    cfg = load_config()["sdk"]
    days = cfg.get("history_days", 90)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days)
    out = {"generated_at": now_iso(), "npm": {}, "pypi": {}, "errors": {}}

    for pkg in cfg.get("npm", []):
        try:
            d = get_json(f"https://api.npmjs.org/downloads/range/{start}:{end}/{pkg}")
            series = [{"d": x["day"], "v": x["downloads"]} for x in d.get("downloads", [])]
            out["npm"][pkg] = {"series": series, **_wow(series)}
        except Exception as e:
            out["errors"][f"npm:{pkg}"] = f"{type(e).__name__}: {e}"
        time.sleep(0.3)

    for pkg in cfg.get("pypi", []):
        try:
            d = get_json(f"https://pypistats.org/api/packages/{pkg}/overall?mirrors=false")
            rows = [x for x in d.get("data", []) if x.get("category") == "without_mirrors"]
            rows.sort(key=lambda x: x["date"])
            series = [{"d": x["date"], "v": x["downloads"]} for x in rows][-days:]
            out["pypi"][pkg] = {"series": series, **_wow(series)}
        except Exception as e:
            out["errors"][f"pypi:{pkg}"] = f"{type(e).__name__}: {e}"
        time.sleep(1.0)  # pypistats 有限速,温柔一点

    save_json("downloads.json", out)
    ok_n = len(out["npm"]) + len(out["pypi"])
    if ok_n == 0:
        raise RuntimeError("npm/pypi 全部失败: " + str(out["errors"]))
    return {"count": ok_n, "errors": out["errors"] or None}


if __name__ == "__main__":
    print(run())
