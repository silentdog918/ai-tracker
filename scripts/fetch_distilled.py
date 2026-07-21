# -*- coding: utf-8 -*-
"""Distilled(distilled.makinote.cn)-> data/distilled.json。
取公开的 boards.json(读/学/做 分诊),抽高分文章做每日精选;跳过实体追踪。
接口失败时保留上次存档。
"""
import json
import os

from common import DATA_DIR, get_json, load_config, now_iso, save_json

BOARD_NAMES = {"read": "读", "learn": "学", "do": "做", "skip": "跳过"}


def _load_previous():
    try:
        with open(os.path.join(DATA_DIR, "distilled.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run():
    cfg = load_config().get("distilled", {})
    out = {"generated_at": now_iso(), "items": []}
    try:
        d = get_json(cfg.get("url", "https://distilled.makinote.cn/lists/boards.json"),
                     headers={"Accept": "application/json"})
        out["src_date"] = d.get("date")
        out["src_generated_at"] = d.get("generated_at")
        out["total_articles"] = d.get("total_articles")
        out["source_count"] = d.get("source_count")
        seen = {}
        for board in cfg.get("boards", ["read", "learn", "do"]):
            topics = (d.get("boards", {}).get(board) or {}).get("topics", [])
            for t in topics:
                for a in t.get("articles", []) or []:
                    link = a.get("link", "")
                    if not link or not a.get("title"):
                        continue
                    item = {
                        "title": a["title"],
                        "source": a.get("source", ""),
                        "score": a.get("score"),
                        "link": link,
                        "date": a.get("date", ""),
                        "board": BOARD_NAMES.get(board, board),
                        "topic": t.get("title", ""),
                    }
                    # 同文可能出现在多个主题/栏目,保留分数最高的一条
                    if link not in seen or (item["score"] or 0) > (seen[link]["score"] or 0):
                        seen[link] = item
        items = sorted(seen.values(), key=lambda x: (x["score"] or 0), reverse=True)
        out["items"] = items[: cfg.get("top_n", 24)]
    except Exception as e:
        prev = _load_previous()
        if prev and prev.get("items"):
            prev["stale"] = True
            save_json("distilled.json", prev)
            return {"count": len(prev["items"]), "status": f"接口失败已用存档: {e}"}
        raise

    save_json("distilled.json", out)
    return {"count": len(out["items"]), "status": "ok"}


if __name__ == "__main__":
    print(run())
