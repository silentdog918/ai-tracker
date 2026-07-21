# -*- coding: utf-8 -*-
"""Google News RSS -> data/news.json,按产业链环节分类。
链接会解码成发布方原文直链(Google 的中转链接对部分网络会弹反自动化拦截页),
解码结果跨天缓存,每天只解新增条目;解不开的保留原链接兜底。
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from common import DATA_DIR, http_get, load_config, now_iso, save_json

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
}


def _gid_of(link):
    if "/articles/" in link:
        return link.split("/articles/")[1].split("?")[0]
    return None


def _decode_gnews(gid):
    """两步解码 Google News 中转链接 -> 原文 URL(社区通用方法)。失败返回 None。"""
    html = http_get(f"https://news.google.com/rss/articles/{gid}",
                    headers=BROWSER_HEADERS, retries=1).decode("utf-8", "replace")
    sg = re.search(r'data-n-a-sg="([^"]+)"', html)
    ts = re.search(r'data-n-a-ts="([^"]+)"', html)
    if not sg or not ts:
        return None
    inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
             'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
             f'"{gid}",{ts.group(1)},"{sg.group(1)}"]')
    freq = json.dumps([[["Fbv4je", inner, None, "generic"]]])
    body = urllib.parse.urlencode({"f.req": freq}).encode()
    req = urllib.request.Request(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
        headers={**BROWSER_HEADERS,
                 "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    resp = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    try:
        parsed = json.loads(resp.split("\n\n")[1])
        url = json.loads(parsed[0][2])[1]
        return url if isinstance(url, str) and url.startswith("http") else None
    except Exception:
        return None


def _local(tag):
    return tag.split("}")[-1]


def _parse_direct_feed(xml_bytes, feed_name, category):
    """通用 RSS 解析,兼容 RSS 2.0 / RSS 1.0(RDF,如 BIS)/ 命名空间差异。"""
    root = ET.fromstring(xml_bytes)
    items = []
    for el in root.iter():
        if _local(el.tag) != "item":
            continue
        title = link = pub = None
        for c in el:
            ln = _local(c.tag)
            if ln == "title":
                title = (c.text or "").strip()
            elif ln == "link" and not link:
                link = (c.text or "").strip()
            elif ln in ("pubDate", "date") and not pub:
                pub = (c.text or "").strip()
        if not title or not link:
            continue
        published = None
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
            except Exception:
                try:
                    dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except Exception:
                    dt = None
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                published = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        items.append({
            "title": title,
            "link": link,
            "gid": None,  # 直连源,无需解码
            "source": feed_name,
            "published": published,  # 缺日期的源(如 Apollo/NBER)之后补"首见时间"
            "category": category,
            "lang": "en",
        })
    return items


def _load_prev_published():
    """上次抓取里 链接->时间戳 的映射,给无日期的 feed 条目沿用"首见时间"。"""
    prev = {}
    try:
        with open(os.path.join(DATA_DIR, "news.json"), encoding="utf-8") as f:
            for it in json.load(f).get("items", []):
                if it.get("link") and it.get("published"):
                    prev[it["link"]] = it["published"]
    except Exception:
        pass
    return prev


def _load_link_cache():
    """从上一次的 news.json 里恢复 gid -> 原文URL 的映射。"""
    cache = {}
    try:
        with open(os.path.join(DATA_DIR, "news.json"), encoding="utf-8") as f:
            for it in json.load(f).get("items", []):
                gid, link = it.get("gid"), it.get("link", "")
                if gid and link and "news.google.com" not in link:
                    cache[gid] = link
    except Exception:
        pass
    return cache


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
            "gid": _gid_of(link),
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
    # 直连 RSS 源(邮件订阅的官方渠道):Apollo / 美联储 / BIS / NBER 等
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=window)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prev_pub = _load_prev_published()
    now_dt = datetime.now(timezone.utc)
    for feed in cfg.get("feeds", []):
        try:
            h = dict(BROWSER_HEADERS)
            if feed.get("ua"):
                h["User-Agent"] = feed["ua"]
            h["Accept"] = "application/rss+xml, application/xml;q=0.9, */*;q=0.8"
            got = _parse_direct_feed(http_get(feed["url"], headers=h),
                                     feed["name"], feed["category"])
            # 无日期条目:沿用上次的首见时间,新条目打当前时间(按feed内顺序微调保持排序)
            for idx, g in enumerate(got):
                if not g["published"]:
                    g["published"] = prev_pub.get(g["link"]) or (
                        (now_dt - timedelta(seconds=idx)).strftime("%Y-%m-%dT%H:%M:%SZ"))
            got = [g for g in got if g["published"] >= cutoff]
            got.sort(key=lambda x: x["published"], reverse=True)
            for it in got[: feed.get("max_items", 8)]:
                key = re.sub(r"\s+", " ", it["title"].lower())[:80]
                if key in seen:
                    continue
                seen.add(key)
                items.append(it)
        except Exception as e:
            fails.append(f"{feed['name']}: {type(e).__name__}")

    items.sort(key=lambda x: x["published"], reverse=True)
    items = items[: cfg.get("max_total_with_feeds", cfg.get("max_total", 100))]

    # 解码为原文直链:缓存命中免请求,新条目限量解码,失败保留 Google 链接兜底
    cache = _load_link_cache()
    resolved, decode_fail, budget = 0, 0, cfg.get("decode_budget", 80)
    for it in items:
        gid = it.get("gid")
        if not gid:
            continue
        if gid in cache:
            it["link"] = cache[gid]
            resolved += 1
            continue
        if budget <= 0:
            continue
        budget -= 1
        try:
            real = _decode_gnews(gid)
        except Exception:
            real = None
        if real:
            it["link"] = real
            resolved += 1
        else:
            decode_fail += 1
        time.sleep(0.4)

    categories = list(dict.fromkeys(
        [q["category"] for q in cfg["queries"]]
        + [f["category"] for f in cfg.get("feeds", [])]))
    save_json("news.json", {
        "generated_at": now_iso(),
        "categories": categories,
        "items": items,
    })
    if fails and not items:
        raise RuntimeError("全部新闻源失败: " + "; ".join(fails))
    return {"count": len(items), "resolved": resolved,
            "decode_fail": decode_fail or None, "failed_queries": fails or None}


if __name__ == "__main__":
    print(run())
