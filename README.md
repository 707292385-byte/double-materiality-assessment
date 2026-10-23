# double-materiality-assessment

双重重要性评估（Double Materiality Assessment）全流程 skill：从议题筛选到问卷回收、计分、审核定稿，产出重要性矩阵图与议题得分 Excel。

面向 A 股《上市公司可持续发展报告指引（试行）》及《编制指南》第一号的双重重要性要求设计：影响重要性与财务重要性两维各一套问卷，分别计分后落到 1–5 分制的四象限矩阵。

## 流程

```
步骤 0 初始化      dm_lib.py init  → project.json
步骤 1 筛选议题    本地选题页（勾选/改名/增删）→ 写回 project.json
步骤 2 制作问卷    飞书多维表格（自动建库建表建表单）或 问卷星（半自动，导出题面文件人工导入）
步骤 3 等待回收    用户线下分发；回收后导出答卷
步骤 4 计算得分    dm_score.py（答卷清洗 → 双维度计分 → 阈值建议）
步骤 5 审核确认    本地审核页（拖阈值/逐项调分 → 确认即定稿，写回 PNG + Excel + 快照）
```

所有交互页通过本地服务以 `http://127.0.0.1:PORT/` 打开（只监听回环地址），确认动作直接把文件写进项目目录，不需要下载搬运。

## 快速开始

```bash
python3 scripts/dm_lib.py libraries                     # 看内置议题库
python3 scripts/dm_lib.py init --company <企业> --industry <行业> \
    --workdir <项目目录> --platform feishu

python3 scripts/build_topic_page.py --project <项目目录>   # 步骤 1 页面
python3 scripts/dm_server.py --project <项目目录> --page topic

python3 scripts/make_survey.py --project <项目目录>        # 步骤 2 问卷

python3 scripts/dm_score.py --project <项目目录> \
    --impact <影响答卷> --finance <财务答卷>                # 步骤 4 计分

python3 scripts/build_review.py --project <项目目录>       # 步骤 5 页面
python3 scripts/dm_server.py --project <项目目录> --page review
```

## 计分口径

| 维度 | 问卷问法 | 计分 |
|---|---|---|
| 影响重要性 | 每题 −5 ~ +5（负=负面影响，正=正面影响） | 取均值后按强度折算到 1–5：`1 + 0.8×|均值|`，方向单独记录不进矩阵坐标 |
| 财务重要性 | 每题问「影响程度」「发生可能性」两问 | 每份先 `√(程度×可能性)`，再跨样本取均值 |

阈值默认两维各 3.0，可在审核页拖动；双重重要占比 ≥ 60% 时会提示把阈值调到中位数附近。

象限命名：双重重要 / 单一重要 / 不重要。矩阵横轴＝财务重要性，纵轴＝影响重要性。

## 目录

```
SKILL.md                    触发条件、硬性门禁、分步操作与回归清单
README.md                   本文件
assets/materiality.css      页面样式（dm-* 设计体系）
assets/topic-library.json   内置议题库
references/scoring-spec.md      计分与阈值口径细则
references/platform-setup.md    飞书 / 问卷星对接方式
scripts/dm_lib.py           项目读写与口径计算（公共库）
scripts/build_topic_page.py 步骤 1 选题页
scripts/make_survey.py      步骤 2 问卷生成
scripts/dm_score.py         步骤 4 计分
scripts/build_review.py     步骤 5 审核页
scripts/dm_server.py        本地回环服务（页面写盘用）
```

## 品牌与引流开关

两个页面脚本都带 `--brand on|off`（默认 on）与 `--qr <图片>`。开启时页头有返回链接、页脚有署名与「进入社区」按钮，导出的矩阵 PNG 与 Excel「评估说明」表带工具来源；`--brand off` 时连品牌字符串都不写入 HTML，用于不希望出现外部署名的客户项目。社区名与链接集中在 `scripts/dm_lib.py` 顶部的 `BRAND_NAME` / `BRAND_TOOL` / `BRAND_URL`。

## 已知事项

`assets/materiality.css` 中 `.dm-topic--s.is-selected` 与 `.dm-topic--g.is-selected` 的渐变底色在线上同源版本里写反了（社会蓝调、治理橙调）。本仓库已修正为 社会 `#fdf6ec`、治理 `#f1f6fb`；若重新从上游下载该 CSS 覆盖，需再改这两条。
