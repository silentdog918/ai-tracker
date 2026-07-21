# -*- coding: utf-8 -*-
"""一次抓取全部数据源,单源失败不影响其他源。状态写入 data/meta.json。"""
import importlib
import json
import sys
import traceback

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from common import now_iso, save_json  # noqa: E402

MODULES = [
    ("openrouter", "fetch_openrouter"),
    ("downloads", "fetch_downloads"),
    ("news", "fetch_news"),
    ("quotes", "fetch_quotes"),
    ("podcasts", "fetch_podcasts"),
    ("subscriptions", "fetch_subscriptions"),
]


def main():
    meta = {"generated_at": now_iso(), "sources": {}}
    for name, mod_name in MODULES:
        print(f"[{name}] 抓取中…")
        try:
            mod = importlib.import_module(mod_name)
            info = mod.run() or {}
            meta["sources"][name] = {"ok": True, **info}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            meta["sources"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    save_json("meta.json", meta)
    print("\n=== 汇总 ===")
    print(json.dumps(meta["sources"], ensure_ascii=False, indent=1))
    # 永远 exit 0:部分成功也要提交部分数据


if __name__ == "__main__":
    main()
