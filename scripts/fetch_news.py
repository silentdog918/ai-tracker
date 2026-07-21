# -*- coding: utf-8 -*-
"""Google News RSS -> data/news.json,按产业链环节分类。"""
import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from common import http_get, load_config, now_iso, save_json


def _parse_feed(xml_bytes, category, lang):
    items = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate")
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        # Google News 标题自带 " - 来源" 后缀,去掉
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)].strip()
        if not title or not link or not pub:
            continue
        try:
            dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            continue
        items.append({
            "title": title,
            "link": link,
            "source": source,
            "published": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "category": category,
            "lang": lang,
        })
    return items


def run():
    cfg = load_config()["news"]
    window = cfg.get("window_days", 7)
    per_q = cfg.get("per_query", 20)
    seen = set()
    items = []
    fails = []
    for q in cfg["queries"]:
        query = f"{q['q']} when:{window}d"
        if q.get("lang") == "zh":
            url = ("https://news.google.com/rss/search?q=" + quote(query)
                   + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans")
        else:
            url = ("https://news.google.com/rss/search?q=" + quote(query)
                   + "&hl=en-US&gl=US&ceid=US:en")
        try:
            got = _parse_feed(http_get(url), q["category"], q.get("lang", "en"))[:per_q]
        except Exception as e:
            fails.append(f"{q['category']}: {type(e).__name__}")
            continue
        for it in got:
            key = re.sub(r"\s+", " ", it["title"].lower())[:80]
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
    items.sort(key=lambda x: x["published"], reverse=True)
    items = items[: cfg.get("max_total", 100)]
    categories = list(dict.fromkeys(q["category"] for q in cfg["queries"]))
    save_json("news.json", {
        "generated_at": now_iso(),
        "categories": categories,
        "items": items,
    })
    if fails and not items:
        raise RuntimeError("全部新闻源失败: " + "; ".join(fails))
    return {"count": len(items), "failed_queries": fails or None}


if __name__ == "__main__":
    print(run())
