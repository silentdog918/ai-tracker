# -*- coding: utf-8 -*-
"""播客 RSS -> data/podcasts.json。投资向 + AI 向节目更新流。"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import json
import os

from common import DATA_DIR, http_get, load_config, now_iso, save_json

ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
# Substack 等源会拦数据中心 IP 的默认 UA,用浏览器 UA 提高成功率
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}


def _fmt_duration(raw):
    raw = (raw or "").strip()
    if not raw:
        return ""
    if re.fullmatch(r"\d+", raw):  # 纯秒数
        sec = int(raw)
        h, m = sec // 3600, (sec % 3600) // 60
        return f"{h}h{m:02d}m" if h else f"{m}m"
    return raw  # 已是 1:02:33 之类


def _itunes_fallback(itunes_id, show):
    """RSS 被拦时,用 iTunes 公共接口拿最近的节目(数据中心 IP 友好)。"""
    raw = http_get(
        f"https://itunes.apple.com/lookup?id={itunes_id}&entity=podcastEpisode&limit=8",
        headers=BROWSER_HEADERS,
    )
    eps = []
    for r in json.loads(raw).get("results", []):
        if r.get("kind") != "podcast-episode":
            continue
        ms = r.get("trackTimeMillis")
        dur = ""
        if ms:
            sec = ms // 1000
            h, m = sec // 3600, (sec % 3600) // 60
            dur = f"{h}h{m:02d}m" if h else f"{m}m"
        pub = (r.get("releaseDate") or "").replace(".000Z", "Z")
        if not pub:
            continue
        eps.append({
            "show": show,
            "title": r.get("trackName", ""),
            "published": pub,
            "link": r.get("trackViewUrl") or r.get("episodeUrl", ""),
            "duration": dur,
        })
    return eps


def _parse(xml_bytes, show):
    root = ET.fromstring(xml_bytes)
    eps = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        pub = it.findtext("pubDate")
        link = (it.findtext("link") or "").strip()
        enc = it.find("enclosure")
        audio = (enc.get("url") or "").strip() if enc is not None else ""
        dur = _fmt_duration(it.findtext(ITUNES_NS + "duration"))
        if not title or not pub:
            continue
        try:
            dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            continue
        eps.append({
            "show": show,
            "title": title,
            "published": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "link": link or audio,
            "duration": dur,
        })
        if len(eps) >= 8:  # RSS 是倒序,拿最近几期就够
            break
    return eps


def run():
    cfg = load_config()["podcasts"]
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=cfg.get("window_days", 45))).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with open(os.path.join(DATA_DIR, "podcasts.json"), encoding="utf-8") as f:
            prev_eps = json.load(f).get("episodes", [])
    except Exception:
        prev_eps = []
    episodes, fails = [], []
    for show in cfg["shows"]:
        try:
            eps = _parse(http_get(show["feed"], timeout=40, headers=BROWSER_HEADERS), show["name"])
            episodes.extend(e for e in eps if e["published"] >= cutoff)
        except Exception as e:
            # 备用通道 1:iTunes 公共接口
            if show.get("itunes_id"):
                try:
                    eps = _itunes_fallback(show["itunes_id"], show["name"])
                    episodes.extend(x for x in eps if x["published"] >= cutoff)
                    fails.append(f"{show['name']}: RSS失败已走iTunes备用通道")
                    continue
                except Exception:
                    pass
            fails.append(f"{show['name']}: {e}")
            # 备用通道 2:沿用上次抓到的存档
            episodes.extend(p for p in prev_eps
                            if p.get("show") == show["name"] and p.get("published", "") >= cutoff)
    episodes.sort(key=lambda x: x["published"], reverse=True)
    episodes = episodes[: cfg.get("max_total", 40)]
    shows = [s["name"] for s in cfg["shows"]]
    save_json("podcasts.json", {
        "generated_at": now_iso(),
        "shows": shows,
        "episodes": episodes,
        "failed_feeds": fails or None,
    })
    if fails and not episodes:
        raise RuntimeError("全部播客源失败: " + "; ".join(fails))
    return {"count": len(episodes), "failed_feeds": fails or None}


if __name__ == "__main__":
    print(run())
