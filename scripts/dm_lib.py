#!/usr/bin/env python3
"""双重重要性评估 skill 公共库：议题库、project.json 读写、口径计算。

所有脚本都只依赖本文件定义的 project.json 契约，换客户不用改代码。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS = SKILL_ROOT / "assets"
LIBRARY_PATH = ASSETS / "topic-library.json"

# 品牌与引流（默认开启；敏感客户项目用 --brand off 一键去掉全部元素）
BRAND_NAME = "Xiao〇 ESG社区"
BRAND_TOOL = "双重重要性评估工具"
BRAND_URL = "https://707292385-byte.github.io/aiesg-workbench-downloads/academy/community.html"
QR_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}

CATEGORY_NAMES = {"E": "环境", "S": "社会", "G": "治理"}
CONCLUSION_DOUBLE = "双重重要"
CONCLUSION_SINGLE = "单一重要"
CONCLUSION_NONE = "不重要"  # 与 GitHub Pages 版象限命名一致（2026-10-23 用户确认）

PROJECT_FILE = "project.json"


def load_library(path: Path | str | None = None) -> dict:
    p = Path(path) if path else LIBRARY_PATH
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def get_library(library_id: str, path: Path | str | None = None) -> dict:
    data = load_library(path)
    for lib in data["libraries"]:
        if lib["id"] == library_id:
            return lib
    ids = ", ".join(lib["id"] for lib in data["libraries"])
    raise SystemExit(f"议题库 {library_id} 不存在；可用：{ids}")


def brand_payload(brand: str = "on", qr: str | None = None) -> dict:
    """页面引流配置。--brand off 时 on=false，前端不渲染任何品牌元素。

    qr 为本地二维码图片路径（可选），存在则内嵌为 data URI，页面保持自包含。
    """
    on = str(brand).strip().lower() not in ("off", "0", "false", "no", "none")
    if not on:
        # 关闭时连字符串都不落进 HTML，避免客户项目里残留外部署名
        return {"on": False, "name": "", "tool": "", "url": "", "qr": "", "qrLabel": ""}
    data = {"on": True, "name": BRAND_NAME, "tool": BRAND_TOOL, "url": BRAND_URL, "qr": "", "qrLabel": ""}
    if not qr:
        return data
    p = Path(qr)
    if not p.exists():
        print(f"警告：二维码文件不存在，已忽略（{qr}）")
        return data
    mime = QR_MIME.get(p.suffix.lower(), "image/png")
    data["qr"] = f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")
    data["qrLabel"] = p.stem
    return data


def normalize_topics(topics: list[dict]) -> list[dict]:
    """重排编号 Q01..Qnn，保证问卷题号与计分匹配一致。"""
    out = []
    for i, t in enumerate(topics, start=1):
        out.append(
            {
                "code": f"Q{i:02d}",
                "id": t.get("id") or f"Q{i:02d}",
                "name": (t.get("name") or "").strip(),
                "category": (t.get("category") or "S").upper(),
                "description": (t.get("description") or "").strip(),
                "source": t.get("source") or "议题库",
            }
        )
    return out


def new_project(company: str, industry: str, library_id: str, platform: str = "feishu", year: str = "") -> dict:
    lib = get_library(library_id)
    return {
        "schema": "dm-assessment/1.0",
        "company": company,
        "industry": industry,
        "year": year,
        "libraryId": library_id,
        "libraryVersion": lib.get("version", "1.0"),
        "scoring": lib.get(
            "scoring",
            {
                "impact": {"mode": "bipolar", "min": -5, "max": 5, "outputMin": 1, "outputMax": 5},
                "financial": {"mode": "two-question", "scale": 5, "combine": "geometric"},
            },
        ),
        "thresholds": {"impact": 3.0, "financial": 3.0},
        "platform": platform,
        "survey": {
            "impactUrl": "",
            "financeUrl": "",
            "baseToken": "",
            "impactTableId": "",
            "financeTableId": "",
            "impactFormId": "",
            "financeFormId": "",
        },
        "responses": {"impact": "", "financial": ""},
        "topics": normalize_topics(lib["topics"]),
        "stage": "topics",
        "companyNameOverride": "",
    }


def load_project(path: Path | str) -> dict:
    p = Path(path)
    if p.is_dir():
        p = p / PROJECT_FILE
    if not p.exists():
        raise SystemExit(f"找不到 {p}；先用 scripts/dm_lib.py init 初始化项目")
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema") != "dm-assessment/1.0":
        raise SystemExit(f"{p} 不是本 skill 的 project.json（schema 不匹配）")
    return data


def save_project(project: dict, path: Path | str) -> Path:
    p = Path(path)
    if p.is_dir():
        p = p / PROJECT_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(project, fh, ensure_ascii=False, indent=2)
    return p


def conclusion(impact: float, finance: float, t_impact: float, t_finance: float) -> str:
    """四象限判定：双高＝双重重要，单高＝单一重要，双低＝不重要（命名与 GitHub Pages 版一致）。"""
    hi_i = impact >= t_impact
    hi_f = finance >= t_finance
    if hi_i and hi_f:
        return CONCLUSION_DOUBLE
    if hi_i or hi_f:
        return CONCLUSION_SINGLE
    return CONCLUSION_NONE


def impact_to_output(raw_mean: float, scoring: dict) -> float:
    """把问卷原始刻度折算到 1~5，便于与财务维度同尺度画矩阵。

    bipolar（−5~+5）：按影响强度（绝对值）折算，0 分＝无影响＝1.0，±5＝5.0；
    方向（正面/负面）另行记录，不进入矩阵坐标。
    unipolar（1~5）：直接线性折算。
    """
    cfg = scoring.get("impact", {})
    lo, hi = cfg.get("min", -5), cfg.get("max", 5)
    olo, ohi = cfg.get("outputMin", 1), cfg.get("outputMax", 5)
    if hi == lo:
        return float(olo)
    if cfg.get("mode", "bipolar") == "bipolar":
        span = max(abs(lo), abs(hi))
        return olo + (ohi - olo) * abs(raw_mean) / span
    return olo + (raw_mean - lo) * (ohi - olo) / (hi - lo)


def impact_direction(raw_mean: float, scoring: dict) -> str:
    cfg = scoring.get("impact", {})
    if cfg.get("mode", "bipolar") != "bipolar":
        return ""
    if raw_mean > 0.2:
        return "正面影响"
    if raw_mean < -0.2:
        return "负面影响"
    return "无影响"


def financial_score(degree: float, likelihood: float, scoring: dict) -> float:
    """财务重要性：程度与可能性先合成回 1~5 刻度，再跨样本取均值。"""
    mode = scoring.get("financial", {}).get("combine", "geometric")
    if mode == "geometric":
        return (max(degree, 0) * max(likelihood, 0)) ** 0.5
    if mode == "arithmetic":
        return (degree + likelihood) / 2
    if mode == "product":
        return degree * likelihood
    raise SystemExit(f"未知的财务合成方式：{mode}")


def round1(v):
    return None if v is None else round(float(v) + 1e-9, 1)


def cmd_init(args):
    project = new_project(args.company, args.industry, args.library, args.platform, args.year or "")
    out = save_project(project, Path(args.workdir) / PROJECT_FILE)
    print(f"已生成 {out}｜{len(project['topics'])} 个议题｜平台 {args.platform}")


def cmd_libraries(args):
    data = load_library(args.library_file)
    for lib in data["libraries"]:
        print(f"{lib['id']}\t{lib['name']}\t{len(lib['topics'])} 项")


def cmd_show(args):
    p = load_project(args.project)
    print(f"企业：{p['company']}｜行业：{p['industry']}｜平台：{p['platform']}｜阶段：{p['stage']}")
    print(f"议题：{len(p['topics'])} 项｜阈值：影响 {p['thresholds']['impact']} / 财务 {p['thresholds']['financial']}")
    print(f"问卷：影响 {p['survey']['impactUrl'] or '—'}｜财务 {p['survey']['financeUrl'] or '—'}")
    print(f"回收：影响 {p['responses']['impact'] or '—'}｜财务 {p['responses']['financial'] or '—'}")


def cmd_set(args):
    path = Path(args.project)
    p = load_project(path)
    for pair in args.set or []:
        key, _, value = pair.partition("=")
        node = p
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if value.lower() in ("true", "false"):
            node[parts[-1]] = value.lower() == "true"
        elif value.replace(".", "", 1).isdigit():
            node[parts[-1]] = float(value) if "." in value else int(value)
        else:
            node[parts[-1]] = value
    save_project(p, path)
    print("已更新：" + "、".join(args.set))


def main():
    ap = argparse.ArgumentParser(description="双重重要性评估 · 项目管理")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="初始化项目 project.json")
    p_init.add_argument("--company", required=True)
    p_init.add_argument("--industry", required=True)
    p_init.add_argument("--workdir", required=True)
    p_init.add_argument("--library", default="agri-general-2025")
    p_init.add_argument("--platform", default="feishu", choices=["feishu", "wjx"])
    p_init.add_argument("--year", default="", help="评估年度，如 2025")
    p_init.set_defaults(func=cmd_init)

    p_lib = sub.add_parser("libraries", help="列出可用议题库")
    p_lib.add_argument("--library-file")
    p_lib.set_defaults(func=cmd_libraries)

    p_show = sub.add_parser("show", help="查看项目状态")
    p_show.add_argument("--project", required=True)
    p_show.set_defaults(func=cmd_show)

    p_set = sub.add_parser("set", help="写入字段，如 platform=wjx thresholds.impact=3.5")
    p_set.add_argument("--project", required=True)
    p_set.add_argument("set", nargs="+")
    p_set.set_defaults(func=cmd_set)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
