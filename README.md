# AI 商业化景气度追踪(自用版)

一个零成本、每日自动更新的静态数据看板,从投资视角追踪 AI 商业化的高频信号:

| 板块 | 数据 | 来源 | 费用 |
|---|---|---|---|
| 速览 | 核心指标 + 周环比 | 汇总下方各源 | 免费 |
| Token 景气度 | OpenRouter 每日 Top50 模型 token 用量、新上架模型与定价 | OpenRouter 官方 API | 免费(排行需免费 Key) |
| 开发者生态 | npm / PyPI 主流 AI SDK 下载量(7 日滚动) | npm registry / pypistats | 免费 |
| 核心标的 | AI 产业链美股 EOD 收盘价、1D/5D/20D、60 日走势 | Yahoo Finance | 免费 |
| 产业链新闻 | 按"算力/模型厂商/应用/融资"分类的近 7 天新闻 | Google News RSS | 免费 |
| 播客 | BG2 / All-In / Invest Like the Best / Dwarkesh / Latent Space / 硅谷101 / 面基 最新节目 | 各播客官方 RSS(被拦时自动走 iTunes 备用通道) | 免费 |
| 订阅研报 | FundaAI / Capital Wars / SemiAnalysis / Citrini Research 最新文章清单,点标题在 Obsidian 打开本地已同步的笔记 | GeoScope API(需 Key,见下) | 随订阅 |

整体架构:**GitHub Actions 每天定时抓数 → 提交 JSON 到仓库 → GitHub Pages 托管静态页**。
没有服务器、没有数据库、零依赖(纯 Python 标准库),月成本 0 元。

## 10 分钟上线

1. **建仓库**:在 GitHub 新建一个仓库(公开私有均可,私有仓库用 Pages 需要 Pro,公开仓库完全免费)。
2. **传代码**:把本项目所有文件推上去(保留目录结构,`.github/workflows/update.yml` 一定要在)。
   ```bash
   git init && git add -A && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```
3. **开 Pages**:仓库 Settings → Pages → Source 选 **Deploy from a branch** → 分支 `main`、目录 `/(root)` → Save。
4. **跑一次**:仓库 Actions 页 → 左侧 `daily-data-update` → Run workflow。跑完后访问
   `https://<你的用户名>.github.io/<仓库名>/` 就能看到页面。
5. 之后每天 **06:30(北京/新加坡时间)** 自动更新,无需任何操作。

> 仓库里已带一份抓好的 `data/`,所以 Pages 开通后页面立即有内容,不必等第一次 Action。

## 解锁 OpenRouter Token 排行(强烈建议,1 分钟)

Token 消耗是整个看板含金量最高的指标,官方接口免费但需要一个 Key:

1. 到 [openrouter.ai/keys](https://openrouter.ai/keys) 注册并创建一个 API Key(不需要充值)。
2. 仓库 Settings → Secrets and variables → Actions → **New repository secret**:
   - Name:`OPENROUTER_API_KEY`
   - Secret:粘贴你的 Key
3. 再手动 Run 一次 workflow。页面上会多出:近 30 天每日 Token 消耗堆叠图、Top 模型份额与周环比、Top Apps 排行。

数据接口限速 500 次/天,本项目每天只调 2 次,远低于限额;只调数据接口不产生推理费用。

## 订阅研报板块(GeoScope,可选)

同样方式再加一个 Secret:Name 填 `GEOSCOPE_API_KEY`,值为 GeoScope 的 API Key(和本地
`geoscope_config.json` 里同一把)。每天只拉 4 个专区的**文章清单**(标题/日期),不拉正文、
不占下载额度;页面上点标题通过 `obsidian://` 链接直接打开本地库里已同步的那篇笔记
(需在装有该 Obsidian 库的电脑上点击;文章清单早于本地 9 点同步时,新文章的笔记可能要到
同步后才能打开)。公开页面上只出现标题与日期,不含任何付费正文。

## 自定义(都在 `config.json`)

| 想改什么 | 改哪里 |
|---|---|
| 新闻关键词 / 分类 | `news.queries`(支持 Google News 的 OR 语法;`lang: "zh"` 走中文版) |
| 追踪的 SDK 包 | `sdk.npm` / `sdk.pypi` |
| 股票标的与分组 | `quotes.groups` / `quotes.names`(Yahoo 代码,如 `NVDA`、`0700.HK`) |
| 播客 | `podcasts.shows`(任意 RSS;不知道 RSS 地址可用 `https://itunes.apple.com/lookup?id=<Apple播客ID>` 查 `feedUrl`) |
| 订阅研报专区 / Obsidian 库名 | `subscriptions.publishers` / `subscriptions.obsidian_vault`(vault 名不对则 obsidian:// 链接打不开,改这里) |
| 更新时间 | `.github/workflows/update.yml` 里的 cron(UTC 时间,`30 22` = 北京 06:30) |

改完 `config.json` 直接 push,下次运行自动生效。

## 本地运行 / 预览

```bash
python3 scripts/fetch_all.py          # 抓全部数据到 data/(可加环境变量 OPENROUTER_API_KEY)
python3 -m http.server 8000           # 然后浏览器开 http://localhost:8000
python3 scripts/make_preview.py       # 或生成单文件 preview.html,双击即可离线打开
```

## 稳定性说明

- 单个数据源失败不影响其他源,页脚有每个源的状态灯;`data/meta.json` 里有错误详情。
- npm / pypistats / Google News / OpenRouter 都是正式公开接口,较稳。
- Yahoo Finance 是非官方接口,若哪天失效,可在 `fetch_quotes.py` 里换成 stooq 或 FMP(免费档 250 次/天)。
- Top Apps 接口结构官方文档不全,做了防御性渲染:结构对不上会自动隐藏该栏,不影响整页。

## 免责

个人自用信息聚合页。所有数据来自公开接口,可能滞后、缺失或有误;不构成任何投资建议。请勿公开分发或商用(部分数据源条款不允许转发布)。

