#!/usr/bin/env python3
"""步骤 2：按项目议题生成问卷。

--platform feishu  用 lark-cli 建多维表格 + 表单 + 题目 + 匿名分享（自动），并回写 project.json
--platform wjx     问卷星无开放接口/连接器，生成题面与批量录入参考表（半自动，人工导入后台）

用法：
  python3 make_survey.py --project <项目目录> --platform feishu [--dry-run]
  python3 make_survey.py --project <项目目录> --platform wjx
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dm_lib import load_project, save_project  # noqa: E402

SCORE_OPTS = (
    [{"name": str(v), "hue": "Green"} for v in (5, 4, 3, 2, 1)]
    + [{"name": "0", "hue": "Gray"}]
    + [{"name": str(v), "hue": "Red"} for v in (-1, -2, -3, -4, -5)]
)
IMPACT_OPTS = [
    {"name": "基本无影响", "hue": "Gray"},
    {"name": "影响较少", "hue": "Blue"},
    {"name": "中等影响", "hue": "Blue"},
    {"name": "较大影响", "hue": "Orange"},
    {"name": "影响显著", "hue": "Red"},
]
LIKELY_OPTS = [
    {"name": "很低", "hue": "Gray"},
    {"name": "低", "hue": "Blue"},
    {"name": "中等", "hue": "Blue"},
    {"name": "高", "hue": "Orange"},
    {"name": "很高", "hue": "Red"},
]

STAKEHOLDERS_IMPACT = [
    "公司高层管理人员",
    "公司员工",
    "政府与监管机构",
    "股东与投资者",
    "客户",
    "供应商",
    "合作农户",
    "社区",
    "债权人",
    "其他",
]
STAKEHOLDERS_FIN = ["公司高层管理人员", "公司财务人员", "股东与投资者", "债权人", "其他"]


def run(args: list[str], dry: bool = False) -> dict:
    cmd = ["lark-cli"] + args + (["--dry-run"] if dry else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"raw": (p.stdout or "")[:800], "stderr": (p.stderr or "")[-800:]}


def dig(obj, keys: tuple[str, ...]):
    """从 lark-cli 返回的嵌套结构里捞字段。"""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k]:
                return obj[k]
        for v in obj.values():
            found = dig(v, keys)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = dig(v, keys)
            if found:
                return found
    return None


def question_sets(project: dict) -> tuple[list[dict], list[dict]]:
    company = project["company"]
    n = len(project["topics"])
    impact, fin = [], []

    impact.append(
        {
            "type": "select",
            "title": "您所属的利益相关方群体",
            "required": True,
            "multiple": False,
            "options": [{"name": s} for s in STAKEHOLDERS_IMPACT],
        }
    )
    fin.append(
        {
            "type": "select",
            "title": "您所属的利益相关方群体",
            "required": True,
            "multiple": False,
            "options": [{"name": s} for s in STAKEHOLDERS_FIN],
        }
    )

    for t in project["topics"]:
        impact.append(
            {
                "type": "select",
                "title": f"{t['code']} {t['name']}",
                "description": f"{'环境' if t['category'] == 'E' else '社会' if t['category'] == 'S' else '治理'}议题｜{t['description']}",
                "required": True,
                "multiple": False,
                "option_display_mode": 2,
                "options": SCORE_OPTS,
            }
        )
        fin.append(
            {
                "type": "select",
                "title": f"{t['code']} {t['name']}｜影响程度",
                "description": f"该议题对{company}财务状况、经营成果、现金流的影响程度",
                "required": True,
                "multiple": False,
                "options": IMPACT_OPTS,
            }
        )
        fin.append(
            {
                "type": "select",
                "title": f"{t['code']} {t['name']}｜可能性",
                "description": f"该影响在中期内发生的可能性",
                "required": True,
                "multiple": False,
                "options": LIKELY_OPTS,
            }
        )

    impact.append(
        {
            "type": "text",
            "title": f"您对{company}在可持续发展管理、实践、信息披露等方面有何建议？（选填）",
            "required": False,
        }
    )
    fin.append(
        {
            "type": "text",
            "title": f"您对{company}在可持续发展管理、实践、信息披露等方面有何建议？（选填）",
            "required": False,
        }
    )
    return impact, fin


def form_description(project: dict, kind: str) -> str:
    company = project["company"]
    n = len(project["topics"])
    if kind == "impact":
        body = (
            f"本问卷共 {n} 个议题，填写约需 5-8 分钟，采用匿名方式，全部题目必答，不涉及个人敏感信息，"
            "所填信息无对错之分，我们将对您的信息保密。\n\n"
            f"请依据个人直观判断，评估{company}在以下议题上的表现会对经济、社会和环境产生实际或潜在的重大影响。"
            "这是对议题重要性的判断，不是评价公司在议题上的表现好坏。\n\n"
            "评分范围 -5 至 5：5 表示积极影响极其重大，0 表示无影响，-5 表示消极影响极其重大。\n\n"
            "为便于识别关键议题，请避免所有议题打分趋同：打最高分（5）和最低分（-5）的议题合计尽量不超过 "
            f"{max(3, n // 3)} 个，打“无影响”（0）的议题尽量不超过 {max(2, n // 4)} 个。"
        )
    else:
        body = (
            f"本问卷共 {n} 个议题，每个议题分“影响程度”和“可能性”两问，填写约需 8-10 分钟，"
            "采用匿名方式，全部题目必答。\n\n"
            f"请从财务视角判断：{company}在以下议题上的表现，会对公司财务状况、经营成果、现金流"
            "（收入、成本、资产、负债、融资能力等）产生多大程度的影响，以及这种影响在中期内发生的可能性。\n\n"
            "影响程度分五档：基本无影响、影响较少、中等影响、较大影响、影响显著；"
            "可能性分五档：很低、低、中等、高、很高。两问相乘构成该议题的财务重要性。"
        )
    return body


def find_form(base_token: str, table_id: str, name: str) -> str:
    """form-list 返回 data.forms[].id；按名称幂等查找，重跑不重复建表单。"""
    r = run(["base", "+form-list", "--base-token", base_token, "--table-id", table_id, "--as", "user"])
    forms = (r.get("data") or {}).get("forms") if isinstance(r, dict) else None
    for f in forms or []:
        if isinstance(f, dict) and f.get("name") == name:
            return f.get("id") or ""
    return ""


def find_table(base_token: str, name: str) -> str:
    """table-list 返回 data.tables[].id（实测字段名就是 id）。"""
    r = run(["base", "+table-list", "--base-token", base_token, "--as", "user"])
    tables = (r.get("data") or {}).get("tables") if isinstance(r, dict) else None
    tables = tables or (r if isinstance(r, list) else [])
    for t in tables:
        if isinstance(t, dict) and t.get("name") == name:
            return t.get("id") or t.get("table_id") or t.get("tableId") or ""
    return ""


def survey_feishu(project: dict, workdir: Path, dry: bool) -> None:
    company = project["company"]
    base_name = f"{company} 双重重要性评估调研"

    if dry:
        r = run(["base", "+base-create", "--name", base_name, "--table-name", "影响重要性问卷",
                 "--fields", json.dumps([{"name": "填报标识", "type": "text"}], ensure_ascii=False), "--as", "user"], dry=True)
        ok = r.get("ok") or r.get("dry_run")
        print(f"dry-run ①建库命令解析：{'正常' if ok else '异常：' + json.dumps(r, ensure_ascii=False)[:600]}")
        print("dry-run 完成：请求能被 lark-cli 正确解析；正式运行去掉 --dry-run。")
        return

    reuse = (project.get("survey") or {}).get("baseToken")
    if reuse:
        base_token = reuse
        impact_table = find_table(base_token, "影响重要性问卷")
        fin_table = find_table(base_token, "财务重要性问卷")
        if not (impact_table and fin_table):
            raise SystemExit(f"库 {base_token} 里找不到两张问卷表，请核对表名")
        survey = project.setdefault("survey", {})
        survey["baseToken"] = base_token
        survey["impactTableId"] = impact_table
        survey["financeTableId"] = fin_table
        print(f"① 复用已有库 {base_token}（影响 {impact_table} / 财务 {fin_table}），跳到建表单")
        run_forms(project, base_token, impact_table, fin_table, dry, workdir)
        return

    print("① 建多维表格 …")
    r = run(
        [
            "base",
            "+base-create",
            "--name",
            base_name,
            "--table-name",
            "影响重要性问卷",
            "--fields",
            json.dumps([{"name": "填报标识", "type": "text"}], ensure_ascii=False),
            "--as",
            "user",
        ],
        dry,
    )
    base_token = dig(r, ("base_token", "baseToken", "app_token"))
    impact_table = dig(r, ("table_id", "tableId"))
    if not base_token:
        print(json.dumps(r, ensure_ascii=False)[:1200])
        raise SystemExit("建库失败，检查 lark-cli 登录状态（lark-cli auth status）")
    if not impact_table:
        impact_table = find_table(base_token, "影响重要性问卷")
    print(f"   base_token={base_token} table={impact_table}")

    print("② 建第二张表（财务重要性）…")
    r = run(
        [
            "base",
            "+table-create",
            "--base-token",
            base_token,
            "--name",
            "财务重要性问卷",
            "--fields",
            json.dumps([{"name": "填报标识", "type": "text"}], ensure_ascii=False),
            "--as",
            "user",
        ],
        dry,
    )
    fin_table = dig(r, ("table_id", "tableId")) or find_table(base_token, "财务重要性问卷")
    print(f"   table={fin_table}")

    run_forms(project, base_token, impact_table, fin_table, dry, workdir)


def run_forms(project: dict, base_token: str, impact_table: str, fin_table: str, dry: bool, workdir: Path) -> None:
    company = project["company"]
    impact_qs, fin_qs = question_sets(project)
    plan = [
        ("impact", "影响重要性问卷", impact_table, impact_qs),
        ("finance", "财务重要性问卷", fin_table, fin_qs),
    ]
    survey = project.setdefault("survey", {})

    for kind, table_name, table_id, questions in plan:
        if not table_id:
            print(f"   ! {table_name} 表 id 缺失，跳过")
            continue
        form_name = f"{company} 2025 年可持续发展报告重要性议题调研（{'影响' if kind == 'impact' else '财务'}重要性）"
        form_id = "" if dry else find_form(base_token, table_id, form_name)
        if form_id:
            print(f"③ 表单已存在，复用 {form_name} → {form_id}")
        else:
            print(f"③ 建表单：{table_name} …")
            r = run(
                [
                    "base",
                    "+form-create",
                    "--base-token",
                    base_token,
                    "--table-id",
                    table_id,
                    "--name",
                    form_name,
                    "--description",
                    form_description(project, kind),
                    "--as",
                    "user",
                ],
                dry,
            )
            form_id = dig(r, ("form_id", "formId"))
            if not form_id and not dry:
                form_id = find_form(base_token, table_id, form_name)
            if not form_id and not dry:
                raise SystemExit(f"建表单失败，返回：{json.dumps(r, ensure_ascii=False)[:400]}")
            print(f"   form_id={form_id}")

        print(f"④ 写入题目（{len(questions)} 题，每批 10 题）…")
        for b in range(0, len(questions), 10):
            batch = questions[b : b + 10]
            rr = run(
                [
                    "base",
                    "+form-questions-create",
                    "--base-token",
                    base_token,
                    "--table-id",
                    table_id,
                    "--form-id",
                    form_id or "",
                    "--questions",
                    json.dumps(batch, ensure_ascii=False),
                    "--as",
                    "user",
                ],
                dry,
            )
            if not dry and not rr.get("ok"):
                raise SystemExit(f"写题失败（批 {b // 10 + 1}）：{json.dumps(rr, ensure_ascii=False)[:400]}")
            print(f"   批 {b // 10 + 1}: {'ok' if rr.get('ok') or dry else '??'}")
            if not dry:
                time.sleep(1.5)  # 接口限流，批次间必须留间隔

        print("⑤ 开启匿名分享 …")
        # 接口一次只接受改一个字段：--enabled 必须单独一次调用，
        # 与 --access-scope 合并在同一次调用里会被静默忽略（2026-10-23 实测）。
        run(
            [
                "base",
                "+form-share-update",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--form-id",
                form_id or "",
                "--enabled",
                "--as",
                "user",
            ],
            dry,
        )
        run(
            [
                "base",
                "+form-share-update",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--form-id",
                form_id or "",
                "--access-scope",
                "anyone",
                "--as",
                "user",
            ],
            dry,
        )
        run(
            [
                "base",
                "+form-share-update",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--form-id",
                form_id or "",
                "--allow-anonymous",
                "--as",
                "user",
            ],
            dry,
        )
        if not dry:
            time.sleep(1.5)  # 限流间隔
        share = run(
            [
                "base",
                "+form-share-get",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--form-id",
                form_id or "",
                "--as",
                "user",
            ],
            dry,
        )
        url = dig(share, ("share_url", "url", "shared_url", "link")) or ""
        if not dry and dig(share, ("enabled",)) is not True:
            raise SystemExit(
                f"共享开关未生效（enabled != true），问卷将无法填写。"
                f"请单独执行 +form-share-update --enabled 后重试。share 状态：{json.dumps(share, ensure_ascii=False)[:300]}"
            )
        if kind == "impact":
            survey["impactTableId"] = table_id
            survey["impactFormId"] = form_id or ""
            survey["impactUrl"] = url
        else:
            survey["financeTableId"] = table_id
            survey["financeFormId"] = form_id or ""
            survey["financeUrl"] = url
        print(f"   链接：{url or '（未返回，可在飞书表单页点分享获取）'}")

    project["platform"] = "feishu"
    project["stage"] = "survey"
    path = save_project(project, workdir)
    print(f"\n已回写 {path}")
    if dry:
        print("（--dry-run 模式，未真正创建资源）")



def survey_wjx(project: dict, workdir: Path) -> None:
    company = project["company"]
    topics = project["topics"]
    outdir = workdir if workdir.is_dir() else workdir.parent
    outdir.mkdir(parents=True, exist_ok=True)

    impact_md = [
        f"# {company} 2025 年可持续发展报告重要性议题调研（影响重要性）",
        "",
        "> 问卷星无开放接口，本文件用于后台「创建问卷 → 文本导入 / 逐题录入」。导入后请核对题型是否为「单选」、选项顺序是否为 5→-5。",
        "",
        "## 问卷说明（粘到问卷描述）",
        "",
        form_description(project, "impact"),
        "",
        "## 题目",
        "",
        "**Q0 您所属的利益相关方群体**（单选，必答）",
        "",
    ]
    for s in STAKEHOLDERS_IMPACT:
        impact_md.append(f"- {s}")
    impact_md.append("")
    for t in topics:
        impact_md += [
            f"**{t['code']} {t['name']}**（单选，必答）",
            "",
            f"题目说明：{t['description']}",
            "",
            "选项：" + "、".join(["5", "4", "3", "2", "1", "0", "-1", "-2", "-3", "-4", "-5"]),
            "",
        ]
    impact_md += ["**建议题**（多行文本，选填）", "", f"您对{company}在可持续发展管理、实践、信息披露等方面有何建议？", ""]
    (outdir / "02_问卷题面-影响重要性.md").write_text("\n".join(impact_md), encoding="utf-8")

    fin_md = [
        f"# {company} 2025 年可持续发展报告重要性议题调研（财务重要性）",
        "",
        "> 每个议题两问：影响程度、可能性。两问相乘构成该议题的财务重要性。",
        "",
        "## 问卷说明（粘到问卷描述）",
        "",
        form_description(project, "finance"),
        "",
        "## 题目",
        "",
        "**Q0 您所属的利益相关方群体**（单选，必答）",
        "",
    ]
    for s in STAKEHOLDERS_FIN:
        fin_md.append(f"- {s}")
    fin_md.append("")
    for t in topics:
        fin_md += [
            f"**{t['code']} {t['name']}｜影响程度**（单选，必答）：" + "、".join(o["name"] for o in IMPACT_OPTS),
            "",
            f"**{t['code']} {t['name']}｜可能性**（单选，必答）：" + "、".join(o["name"] for o in LIKELY_OPTS),
            "",
        ]
    fin_md += ["**建议题**（多行文本，选填）", "", f"您对{company}在可持续发展管理、实践、信息披露等方面有何建议？", ""]
    (outdir / "02_问卷题面-财务重要性.md").write_text("\n".join(fin_md), encoding="utf-8")

    for kind, fname in (("impact", "02_问卷星录入参考-影响重要性.csv"), ("finance", "02_问卷星录入参考-财务重要性.csv")):
        with open(outdir / fname, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["题号", "题型", "题干", "选项（｜分隔）", "是否必答", "题目说明"])
            w.writerow(["Q0", "单选", "您所属的利益相关方群体", "｜".join(STAKEHOLDERS_IMPACT if kind == "impact" else STAKEHOLDERS_FIN), "是", ""])
            for t in topics:
                if kind == "impact":
                    w.writerow([t["code"], "单选", f"{t['code']} {t['name']}", "｜".join(str(v) for v in (5, 4, 3, 2, 1, 0, -1, -2, -3, -4, -5)), "是", t["description"]])
                else:
                    w.writerow([t["code"] + "a", "单选", f"{t['code']} {t['name']}｜影响程度", "｜".join(o["name"] for o in IMPACT_OPTS), "是", ""])
                    w.writerow([t["code"] + "b", "单选", f"{t['code']} {t['name']}｜可能性", "｜".join(o["name"] for o in LIKELY_OPTS), "是", ""])
            w.writerow(["Q99", "多行文本", f"您对{company}在可持续发展管理、实践、信息披露等方面有何建议？", "", "否", ""])

    project["platform"] = "wjx"
    project["stage"] = "survey"
    save_project(project, workdir)
    print("已生成：02_问卷题面-影响重要性.md、02_问卷题面-财务重要性.md、02_问卷星录入参考-*.csv")
    print("下一步：问卷星后台建两份问卷（影响 / 财务），把分享链接写入 project.json：")
    print("  python3 dm_lib.py set --project <项目目录> survey.impactUrl=<链接> survey.financeUrl=<链接>")


def main():
    ap = argparse.ArgumentParser(description="生成双重重要性调研问卷")
    ap.add_argument("--project", required=True, help="项目目录或 project.json")
    ap.add_argument("--platform", choices=["feishu", "wjx"], required=True)
    ap.add_argument("--dry-run", action="store_true", help="飞书：只预览请求，不创建资源")
    ap.add_argument("--base-token", help="飞书：复用已有库（断点续跑，不再新建）")
    args = ap.parse_args()

    path = Path(args.project)
    workdir = path if path.is_dir() else path.parent
    project = load_project(path)
    if not project["topics"]:
        raise SystemExit("项目还没有议题，先跑步骤 1 选题页并导回 project.json")
    if args.base_token:
        project.setdefault("survey", {})["baseToken"] = args.base_token

    print(f"{project['company']}｜{len(project['topics'])} 个议题｜平台 {args.platform}")
    if args.platform == "feishu":
        survey_feishu(project, workdir, args.dry_run)
    else:
        survey_wjx(project, workdir)


if __name__ == "__main__":
    main()
