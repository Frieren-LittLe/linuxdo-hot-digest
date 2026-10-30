# linuxdo-hot-digest

> Linux.do 每日热榜追踪与技术内参生成工具链：抓取 Top 100 热帖元数据 → 筛选 3~5 篇高价值内容精读 → 生成以日期命名的 Markdown 日报。

[样例日报（2026-10-23）](日报/2026-10-23.md)

## 背景：为什么抓 Linux.do 这么麻烦

linux.do 部署了相当严格的 Cloudflare 防护，实测（2026-10）各方案的可用性：

| 方案 | 结果 | 对应脚本 |
| :-- | :-- | :-- |
| 直连 Discourse JSON 接口（`/hot.json`、`/top.json`） | ❌ 403 "Just a moment"，换 Chrome TLS 指纹（curl_cffi）也无效 | `fetch_hot.py` |
| Playwright 驱动本机真实 Edge（有头 + 持久化 Profile） | ⚠️ 主页能过验证，但 JSON 接口仍间歇性 403，仅作备用通道 | `browser_fetch.py` |
| **r.jina.ai 阅读服务中转** | ✅ 稳定可用，jina 的服务端基础设施可正常访问 Discourse JSON | `jina_fetch.py` |

因此日常使用以 `jina_fetch.py` 为主通道，`browser_fetch.py` 备用，`fetch_hot.py` 保留作为直连方案的历史记录（若未来防护策略变化可能复活）。

## 工作流

```
python 脚本/daily_runner.py hot             # 1. 抓 Top 100 元数据 -> data/hot_100.json
                                            #    （运行器自带守护：等代理恢复/卡死超时/空结果重试）
python 脚本/shortlist.py [N] [YYYY-MM-DD]  # 2. 规则初筛：剔除窗口外旧帖/往期已解读，按分类权重+互动质量
                                            #    排序输出候选短名单（控制 AI 阅读量，节省 token）
                                            #    ★ 补做历史日报时必须传日期，否则窗口按"当前时间"算，会与
                                            #      gen_report.py 的口径错一天、误杀本该入选的帖子
python 脚本/jina_fetch.py topic <id> ...    # 3. 对入选的 3~5 篇抓主帖正文 -> data/topic_<id>.json
python 脚本/shortlist.py read <id> ...      # 4. 输出清洗版正文（剥离推广申明模板/图片占位符）供精读
python 脚本/gen_report.py [YYYY-MM-DD]      # 5. 组装日报 -> 日报/YYYY-MM-DD.md
```

第 2~4 步之间是"人工/AI 精读并撰写 `data/analysis.md`"的分析环节（四段式解读无法全自动生成）；
`shortlist.py` 把筛选中的机械部分（去旧帖、去重、降噪、排序）固化成本地脚本，AI 只需在
~15 条候选里做判断。脚本按自身位置锚定 `data/` 与 `日报/`，在任意工作目录下运行均有效；
日期参数缺省取当天，可用历史数据重跑时显式指定。

筛选标准（实用性 / 独创性 / 社区反响）：优先开源工具、深度踩坑、实践教程与高质量首发方案；
过滤纯水帖、打卡、抽奖与无实质内容的福利帖。

日报格式包含：frontmatter 元信息（日期 / 来源 / 分析总数 / 精选数）、今日大盘概览、
每篇精选帖的四段式解读（核心分类 / 解决痛点 / 技术要点 / 价值总结）、Hot 100 快速索引表
（📌 标记置顶旧帖）。

## 补做往期日报（热榜没有历史存档）

Linux.do 热榜是**实时快照，没有历史存档**：某天 21:00 没跑，事后就只能重建。两条路径：

| 情况 | 办法 | 完整度 |
| :-- | :-- | :-- |
| 那天抓过一次 | 直接复用 `data/snapshots/hot_<时间戳>.json` 归档快照 | ✅ 完整 100 条 |
| 那天完全没抓 | `python data/_fetch_weekly.py weekly` 抓周榜，再 `slice <日期>` 按 `created_at` 反筛 | ⚠️ 实测只捞回 ~25 条，且浏览/赞是**当前累计值** |

`jina_fetch.py` 每次 `hot` 抓取都会自动归档一份带时间戳的快照到 `data/snapshots/`（按文件名轮转，保留最近 14 份），
就是为了把第一类情况变成常态。走周榜重建时，`gen_report.py` 检测到条数 < 100 会自动把索引表说明切换为"补记"口径，
报告里也应写明数据来源与局限。

## 安装

```bash
pip install -r requirements.txt
```

- `curl_cffi`：主通道（jina 中转）依赖
- `playwright`：仅备用通道 `browser_fetch.py` 需要，首次使用还需 `playwright install` 或直接使用本机 Edge（脚本已配置 `channel="msedge"`）

## 配置

脚本默认**自动探测系统代理**（Windows 注册表 / 环境变量）。如需显式指定：

```bash
export LINUXDO_PROXY=http://127.0.0.1:7897   # jina 通道与浏览器通道均生效
```

中国大陆网络环境下访问 r.jina.ai 通常需要代理；直连可用的环境无需任何配置。

## 目录结构

```
├── README.md          # 本说明文档
├── 脚本/              # 全部可执行脚本（见下方说明）
│   ├── jina_fetch.py      # 主通道：经 r.jina.ai 抓取热榜与帖子正文
│   ├── daily_runner.py    # 抓取运行器：等代理恢复 / 卡死超时 / 空结果自动重试
│   ├── shortlist.py       # 候选短名单 + 正文清洗（筛选机械化，节省 token）
│   ├── browser_fetch.py   # 备用通道：Playwright + Edge 过 Cloudflare
│   ├── fetch_hot.py       # 历史方案：直连（现被拦截，仅作参考）
│   └── gen_report.py      # 日报组装：拼合分析正文与 Hot 100 表格
├── 日报/              # 生成的日报（样例：2026-10-23.md）
└── data/              # 运行时产物（热榜 JSON、帖子正文等；被 git 忽略，不上传）
```

根目录另有三个**行业约定的标准文件名**，改名会失去对应功能，故保留原样：

| 文件 | 作用 | 为什么不能改名 |
| :-- | :-- | :-- |
| `.gitignore` | Git 忽略规则（阻止 `data/` 内的浏览器配置、抓取产物上传） | git 只识别这个固定文件名 |
| `LICENSE` | 开源协议（MIT） | GitHub 靠它自动识别协议并在仓库页展示标识 |
| `requirements.txt` | Python 依赖清单（`pip install -r requirements.txt`） | Python 生态的通用约定，工具链默认查找该文件名 |

`data/analysis.md` 由使用者（人或 AI）撰写——日报的"深度解读"部分本质上是分析产物，
无法全自动生成；本仓库负责把采集与组装环节工程化。

## 使用须知

- **控制频率**：脚本内置请求间隔（jina 通道 3s），请勿移除；r.jina.ai 免费通道有速率限制，且内容可能存在分钟级缓存。
- **尊重社区**：数据仅来自公开只读接口（`/hot.json`、`/top.json`、`/t/{id}.json`），请遵守 Linux.do 社区规则，本工具仅供个人学习与研究。
- **数据时效**：日报统计窗口为滚动 24 小时（前一日 21:00 至报告日 21:00 抓取）；`top.json?period=daily` 本身即滚动 24h 榜单，与该窗口天然对齐。

## License

[MIT](LICENSE)
