# -*- coding: utf-8 -*-
"""把 data/*.json 内联进 index.html,生成单文件 preview.html(无需服务器直接打开)。"""
import json
import os

from common import DATA_DIR, ROOT


def main():
    data = {}
    for fn in sorted(os.listdir(DATA_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(DATA_DIR, fn), encoding="utf-8") as f:
                data[fn[:-5]] = json.load(f)
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        html_src = f.read()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    inject = "<script>window.__DATA__ = " + payload + ";</script>"
    out = html_src.replace("<!--__PREVIEW_DATA__-->", inject)
    # 预览是单文件:把本地 echarts 也内联进去,离线可开
    ech_path = os.path.join(ROOT, "assets", "echarts.min.js")
    if os.path.exists(ech_path):
        with open(ech_path, encoding="utf-8") as f:
            ech = f.read()
        out = out.replace(
            '<script src="./assets/echarts.min.js"></script>',
            "<script>" + ech + "</script>",
        )
    out_path = os.path.join(ROOT, "preview.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    print("已生成", out_path, f"({os.path.getsize(out_path)//1024} KB)")


if __name__ == "__main__":
    main()
