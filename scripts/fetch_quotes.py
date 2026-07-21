# -*- coding: utf-8 -*-
"""Yahoo Finance 图表接口 (免 key, EOD) -> data/quotes.json。"""
import time
from datetime import datetime, timezone

from common import get_json, load_config, now_iso, save_json


def _one(sym, names):
    d = get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6mo&interval=1d"
    )
    res = d["chart"]["result"][0]
    ts = res.get("timestamp") or []
    closes_raw = res["indicators"]["quote"][0].get("close") or []
    pts = [(t, c) for t, c in zip(ts, closes_raw) if c is not None]
    if len(pts) < 25:
        raise RuntimeError("K线数据不足")
    closes = [c for _, c in pts]
    dates = [datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d") for t, _ in pts]

    def chg(n):
        if len(closes) > n:
            return round((closes[-1] / closes[-1 - n] - 1) * 100, 2)
        return None

    return {
        "name": names.get(sym) or res.get("meta", {}).get("shortName", sym),
        "price": round(closes[-1], 2),
        "chg1d": chg(1),
        "chg5d": chg(5),
        "chg20d": chg(20),
        "spark": [round(c, 2) for c in closes[-60:]],
        "asof": dates[-1],
        "currency": res.get("meta", {}).get("currency", "USD"),
    }


def run():
    cfg = load_config()["quotes"]
    names = cfg.get("names", {})
    quotes, errors = {}, {}
    for g in cfg["groups"]:
        for sym in g["symbols"]:
            try:
                quotes[sym] = _one(sym, names)
            except Exception as e:
                errors[sym] = f"{type(e).__name__}: {e}"
            time.sleep(0.6)
    save_json("quotes.json", {
        "generated_at": now_iso(),
        "groups": cfg["groups"],
        "quotes": quotes,
        "errors": errors or None,
    })
    if not quotes:
        raise RuntimeError("行情全部失败: " + str(errors))
    return {"count": len(quotes), "errors": errors or None}


if __name__ == "__main__":
    print(run())
