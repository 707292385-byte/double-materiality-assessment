# 问卷平台操作（2026-10-23 实测口径）

## 平台选择

| 平台 | 自动化程度 | 前提 | 回收方式 |
|---|---|---|---|
| 飞书 | 全自动（建库/建表/建表单/写题/开匿名分享） | 飞书连接器已连接 + `lark-cli auth status` 正常 | 导出 CSV 或 `lark-cli base +record-list` 拉 ndjson |
| 问卷星 | 半自动（生成题面与录入参考表，人工导入） | 无连接器、无开放接口，别承诺全自动 | 后台下载答卷 Excel |

## 飞书

1. 先跑 `make_survey.py --platform feishu --dry-run` 验证命令解析，再去掉 `--dry-run` 正式执行。
2. 脚本动作：`+base-create`（建库+第一张表）→ `+table-create`（财务表）→ 每表 `+form-create` → `+form-questions-create` 每 10 题一批 → `+form-share-update` 三条命令（依次单独设 enabled → access-scope=anyone → allow-anonymous）→ `+form-share-get` 取链接。
3. **共享开关必须单字段调用（2026-10-23 实测）**：`+form-share-update` 一次只接受改一个字段，`--enabled` 与 `--access-scope` 合并在同一次调用里 enabled 会被静默忽略，问卷显示可分享但实际打不开（无法填写）。必须 `--enabled`、`--access-scope anyone`、`--allow-anonymous` 各跑一次，最后 `+form-share-get` 校验 `enabled: true`，否则脚本抛错终止。
3. **返回字段名（2026-10-23 实测）**：`+table-list` 的表在 `data.tables[]`，表 ID 字段名是 **`id`**（不是 table_id）；`+form-list` 的表单在 `data.forms[]`，ID 同样是 `id`。脚本一律按名称查找、不依赖建库返回值里的 ID。
4. **幂等重跑**：`make_survey.py --platform feishu --base-token <token>` 复用已有库续跑；表单按名称复用不重复建；写题批次返回无 `ok` 即抛错终止，不静默继续。中途失败直接重跑同一条命令即可。
5. **限流**：`+form-questions-create` 批次间必须 sleep ≥1.5 秒，报 `OpenAPICreateQuestions limited` 就等 3 秒重试该批。
6. 表单描述里的换行必须用真实 `\n`（json 参数内），不要经 shell 传 `\n` 字面量。
7. 题目顺序乱时用 `+view-set-visible-fields` 传全量字段顺序修正。
8. 改 select 题选项会把存量记录该列清空——回收开始后不要再动选项。
9. 链接没取到时：让用户在飞书表单页点「分享」复制，回写 `survey.impactUrl / survey.financeUrl`。

## 问卷星

无连接器。脚本生成三件套：
- `02_问卷题面-影响重要性.md` / `02_问卷题面-财务重要性.md`（人读，含问卷说明与逐题选项）
- `02_问卷星录入参考-*.csv`（题号/题型/题干/选项/必答/说明，按后台当时的导入模板自行调整列序）

操作：后台分别建两份问卷 → 粘贴说明 → 按题面录入（或尝试文本导入）→ 核对题型为单选、选项顺序 5→-5 → 开启回收 → 把链接回写 project.json：
`python3 scripts/dm_lib.py set --project <目录> survey.impactUrl=<链接> survey.financeUrl=<链接>`

## 回收数据文件命名

放项目目录，建议：
- `回收-影响重要性.csv` / `回收-财务重要性.csv`（或 .ndjson / .xlsx）

dm_score 按列名里的 `Q01…` 题号匹配议题，与平台无关；导出时不要重命名题目。
