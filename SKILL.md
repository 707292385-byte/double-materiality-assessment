---
name: double-materiality-assessment
description: 双重重要性评估全流程 skill：筛选确定议题（本地页面）→ 飞书/问卷星生成问卷 → 等待回收 → 计分（影响 1~5 原始均值 + 财务 程度×可能性）→ 审核调分（本地页面）→ 导出矩阵图与议题得分 Excel。触发词：双重重要性、重要性议题、议题调研、重要性矩阵、议题评分、materiality。
---

# 双重重要性评估（Double Materiality Assessment）

为一家企业完成「重要性议题筛选 → 问卷调研 → 计分 → 审核定稿」全流程，产出：
1. **矩阵图 PNG**（影响重要性 × 财务重要性，1-5 分制）
2. **议题得分 Excel**（含审核调整前后对比）
3. **可审核调分的本地 HTML**（步骤 5 交互载体）

## 硬性门禁（违反任何一条都不许往下走）

1. **先汇报流程再动手**：开始时把下方五步流程讲给用户听，确认企业名、行业、平台后再执行步骤 1。
2. **没检查连接器不许建问卷**：飞书用 `lark-cli auth status` 确认登录；问卷星无连接器，只能半自动（见 references/platform-setup.md）。
3. **没有 project.json 不许计分**：计分、出图全部依赖项目目录下的 `project.json`。
4. **本 skill 分两次会话执行**：步骤 1–2 完成后停下，把问卷链接给用户；用户明确说"回收完成/开始计分"才执行步骤 4–5。
4b. **审核证据必须落文件**：步骤 5 必须让用户点「确认并写回项目」，Excel（三表）与审核快照落到项目目录才算交付；页面暂存不作为证据。
4c. **页面走本地服务，不走 file://**：所有交互页都通过 `dm_server.py` 以 `http://127.0.0.1:PORT/` 打开；服务只监听回环地址，任务结束关掉。
5. **数据不臆造**：议题名称与说明用议题库原文或用户提供的材料；分数只来自问卷回收数据；模拟数据必须标"模拟"且默认不进入正式交付。
6. **测完清状态**：浏览器验证页面后必须 `localStorage.clear()` 再关闭，避免用户打开带脏数据。

## 总流程

```
步骤 1 筛选议题   本地 HTML（选题页：勾选/改名/增删议题 → 导出 project.json）
步骤 2 制作问卷   飞书（lark-cli 自动建库建表建表单）或 问卷星（生成题面文件，人工导入）
步骤 3 等待回收   用户线下分发问卷；回收后从平台导出答卷
步骤 4 计算得分   dm_score.py（清洗 + 双维度计分 + 阈值建议）
步骤 5 审核确认   本地 HTML（审核页：调阈值/改分 → 确认即定稿并写回矩阵图 PNG + Excel + 快照）
```

## 数据契约：project.json

一个项目一个目录，所有命令都围绕它：

```json
{
  "schema": "dm-assessment/1.0",
  "company": "企业名", "industry": "行业",
  "libraryId": "agri-general-2025",
  "scoring": {"impact": {"mode": "bipolar", "min": -5, "max": 5}, "financial": {"combine": "geometric"}},
  "thresholds": {"impact": 3.0, "financial": 3.0},
  "platform": "feishu|wjx",
  "survey": {"impactUrl": "", "financeUrl": "", "baseToken": "", ...},
  "responses": {"impact": "答卷文件路径", "financial": "..."},
  "topics": [{"code": "Q01", "name": "...", "category": "E|S|G", "description": "..."}],
  "stage": "topics|survey|scored|reviewed"
}
```

议题 `code` 按顺序重排 Q01…Qnn，问卷题号、计分匹配、矩阵编号三处共用，删改议题后自动顺延。

## 步骤 0：汇报并初始化

向用户确认：企业名称、行业、问卷平台（飞书/问卷星）、议题库起点。然后：

```bash
python3 scripts/dm_lib.py libraries                       # 看可用议题库
python3 scripts/dm_lib.py init --company <企业> --industry <行业> \
    --workdir <项目目录>/02_调研与访谈/重要性议题问卷 --platform feishu
```

## 步骤 1：筛选确定议题（本地页面，确认即写回）

```bash
python3 scripts/build_topic_page.py --project <项目目录>
python3 scripts/dm_server.py --project <项目目录> --page topic   # 后台运行，输出 READY http://127.0.0.1:PORT/
```

用 present_files 打开服务给出的 `http://127.0.0.1:PORT/`（不要用 file://，否则页面无法写盘）。

用户在页面上：勾选、改名、改类别、改说明、新增（标"自定义"）、删除，然后点「确认选题，交给后续步骤」——页面直接把 project.json 写回项目目录，**不需要下载、不需要搬文件**。页面顶部会显示"已连接本地服务"，写完提示"已写回 <路径>，可以回到对话继续"。

agent 侧：用户说"确认了"之后，读 project.json 确认 `stage=topics` 与议题数对得上，再进步骤 2。若用户是用 file:// 打开的（离线模式），页面会退化为下载 project.json，需要请用户放回目录。

交付给用户时说明：编号会自动重排为 Q01…Qnn，问卷题号跟这次选题一一对应。

## 步骤 2：制作问卷

```bash
# 飞书（全自动；先 --dry-run 验证一次再正式跑）
python3 scripts/make_survey.py --project <项目目录> --platform feishu --dry-run
python3 scripts/make_survey.py --project <项目目录> --platform feishu
# 问卷星（半自动：生成题面 md + 录入参考 csv，人工导入后台）
python3 scripts/make_survey.py --project <项目目录> --platform wjx
```

- 飞书：脚本建 1 个多维表格 + 2 张表（影响 / 财务）+ 2 个匿名表单，题目按 10 题一批写入（批次间 sleep 1.5s 防限流），完成后把分享链接回写 project.json。
- 影响问卷：每议题 1 题（-5~+5 共 11 档）+ 利益相关方身份 + 建议题；财务问卷：每议题 2 题（影响程度、可能性各 5 档）。
- 题量提示：议题数 n 时影响问卷 n+2 题、财务问卷 2n+1 题，超过 80 题建议先砍议题。
- 交付：把两个问卷链接给用户，明确**到此暂停**，等回收。

## 步骤 3：等待回收

用户说回收完成后，请其导出答卷：
- 飞书：多维表格右上「导出」CSV，或让 agent 用 `lark-cli base +record-list` 直接拉取 ndjson；
- 问卷星：后台下载答卷 Excel。

然后回写或用参数指定路径，进入步骤 4。回收率异常时提醒：有效份数建议 ≥ 20 且覆盖主要利益相关方群体。

## 步骤 4：计算得分

```bash
python3 scripts/dm_score.py --project <项目目录> --impact <影响答卷文件> --finance <财务答卷文件>
```

- 自动清洗：答题时长 < 30 秒、影响+财务全部同分（直线作答）、整行缺答 → 剔除并报数。
- 计分口径见 references/scoring-spec.md（影响取均值后按强度折 1~5；财务 = mean(√(程度×可能性))）。
- 输出 `scores.json` + `议题得分明细.csv`，并打印四象限分布；**双重重要占比 ≥ 60% 时会提示把阈值调到中位数附近**（用 `dm_lib.py set --project <目录> thresholds.impact=x thresholds.financial=y` 写入后重跑），或留给用户在审核页拖。

## 步骤 5：审核确认（本地页面，确认即写回）

```bash
python3 scripts/build_review.py --project <项目目录>
python3 scripts/dm_server.py --project <项目目录> --page review   # 后台运行
```

present_files 打开 `http://127.0.0.1:PORT/`。

**界面（2026-10-23 起内联 assets/materiality.css，与用户 GitHub Pages 版 v=20261023-12 完全同源；线上版更新时重新下载该 CSS 替换 assets 文件即可）**：
- 页头：深绿渐变 + `dm-hero-flow` 四步流程条（评估范围→议题清单→问卷收集→评分与矩阵）**在页头内部**，无右侧圆形徽标。选题页第 1-2 步高亮，审核页第 4 步高亮。
- 配色：**环境=绿 #138a61、社会=橙 #d48a24、治理=蓝 #2878b8**（v12 起社会/治理与旧版对调，勿改回）。
- **已知线上 CSS 缺陷（2026-10-23 修正）**：`assets/materiality.css` 里 `.dm-topic--s.is-selected` 与 `.dm-topic--g.is-selected` 的渐变底色在线上版是**反的**（社会用蓝调 #f2f7fc、治理用橙调 #fcf7ee），与 `--dm-s/--dm-g` 变量冲突。本 skill 已改为 社会 `#fdf6ec`、治理 `#f1f6fb`。**重新从线上下载 CSS 替换 assets 后，必须再改这两条**，否则社会卡又变蓝。
- 矩阵：横轴＝**财务重要性**、纵轴＝**影响重要性**；圆点 r=9；象限命名与线上版一致＝**双重重要 / 单一重要 / 不重要**（单一重要两个象限同色，第四象限也填色，不再留空）；SVG 内不写象限文字，图例在矩阵下方（`dm-matrix-legend`，含区域颜色取色器，存浏览器）。区域色默认 双重 #1f5b45 / 单一 #dceee3 / 不重要 #ffffff。
- 保留双阈值滑杆（影响/财务各一根，1~5）——线上版是单阈值，skill 计分口径需要双阈值，已与用户确认（2026-10-23）。
- 选题页：议题按 E/S/G 分组（`dm-topic-group`，组头显示 n/m 已选）+ 卡片/列表视图切换（`dm-view-switch`）；审核页：逐行滑杆校准（不用线上版的单题编辑器，已确认）。
- 「逐项校准」面板：每议题一行，影响/财务两条滑杆 + 结论徽章 + 可展开的调整理由；筛选标签（全部/环境/社会/治理/已调整）；**「恢复原始分」按钮在本面板头部**；底部调整记录按时间倒序。
- **按钮只有三类**：结果工具栏的「导出矩阵图片 / 导出 Excel / 导出审核快照」（离线备用）、逐项校准的「恢复原始分」、底部唯一的「确认并写回项目（定稿）」。**没有单独的定稿按钮**——确认动作＝填审核人＋定稿＋生成文件＋写回，一步完成。

**确认即定稿并写回**：
- 确认时校验：审核人必填（为空聚焦审核人输入框）；改分未写理由时弹确认。
- 确认后服务端一次性落盘：`<企业>_议题得分明细.xlsx`（三表）、`<企业>_双重重要性矩阵.png`、`review-YYYYMMDD.json`（审核快照），并更新 project.json。**用户全程不下载文件**。
- 「导出 Excel」＝三张表：`议题得分明细`（含影响方向、原始分、审核说明）、`审核留痕`（时间/编号/议题/调整项/原值/新值/幅度/理由，含阈值调整与定稿事件）、`评估说明`（样本数与剔除情况、阈值、四象限统计、审核人、审核状态、计分口径、数据来源文件名、导出时间）。
- 「导出审核快照」＝JSON，记录阈值、逐题原始分与新分、结论、事件流水，便于回溯或第二年对比。
- localStorage 只是页面暂存；写回项目目录的 Excel + review JSON 才是审核证据。用户确认写回后，用 `ls` 核对文件名与时间戳，再向用户复述落盘位置。

## 品牌与引流（默认开启，可一键关闭）

两个页面构建脚本都带 `--brand on|off`（默认 on）与 `--qr <图片路径>`：

- **开启时**：页头左上「← 返回项目与工具」链接到社区页；页脚加一行「Xiao〇 ESG社区 · 双重重要性评估工具 · 社区入口」；导出的矩阵 PNG 右下角加同一行小字署名；Excel「评估说明」表末尾加「工具来源」行。`--qr` 可把一张本地二维码（png/jpg/svg）以 data URI 内嵌进页脚，页面仍是自包含单文件。
- **`--brand off`**：连品牌字符串都不落进 HTML（dm_lib.brand_payload 直接返回空串），用于不希望出现外部署名的客户项目。
- 链接地址与名称在 `dm_lib.py` 顶部的 `BRAND_NAME` / `BRAND_TOOL` / `BRAND_URL` 常量里，换社区地址只改这一处。

## 回归验证清单（改代码后必跑）

```bash
# 用任一已完成项目的回收答卷（impact/finance 的 ndjson 或 csv）当样例数据
dm_lib init → dm_score --impact … --finance … → build_review → 浏览器验证：
① 矩阵 30 点全部落图、区域填色（横轴财务、纵轴影响），图例在矩阵下方且含区域取色器
①b 页面样式与 assets/materiality.css 同源（四步流程条在页头内、S橙G蓝）；点「确认并写回项目」后项目目录出现 xlsx / png / review-*.json
② 拖阈值 / 改分 → 概览计数、结论徽章、矩阵联动（结论只有 双重重要/单一重要/不重要 三档）
③ 导出 PNG 白底完整；XLSX 用 openpyxl 校验三张表（明细 A1:O31、审核留痕、评估说明），分数为 number 类型
④ 改分后行不跳位、理由跟随同一议题；「恢复原始分」一键还原；确认写回即定稿
⑤ 测后 localStorage.clear()
⑥ 品牌开关：默认版页头有返回链接、页脚有署名、PNG/Excel 带工具来源；--brand off 版 grep 不到「Xiao〇」与社区地址
```

## 边界

- 只覆盖议题重要性评估，不做评级、绿色金融、碳核算。
- 审核页改分不回写问卷平台，正式口径以导出的 Excel 为准。
- 问卷星无开放接口，"自动配置"仅限生成导入材料，别向用户承诺全自动。
