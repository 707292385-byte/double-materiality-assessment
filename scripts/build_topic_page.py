#!/usr/bin/env python3
"""步骤 1：生成「选题与议题清单」本地页面。

样式内联 assets/materiality.css（与用户 GitHub Pages 双重重要性评估页同源，v=20261023-12）：
深绿页头内嵌 dm-hero-flow 四步流程条、议题按 E/S/G 分组、卡片/列表视图切换。
打开后可按项目实况勾选、改名、改类别、改说明、增删议题，确认后写回 project.json。

用法：
  python3 build_topic_page.py --project <项目目录或project.json> [--out 01_选题.html] [--library <lib_id>]
                              [--brand on|off] [--qr <二维码图片>]

--brand off 关闭页头返回链接与页脚署名，用于不希望出现外部署名的客户项目。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dm_lib import brand_payload, get_library, load_project, normalize_topics  # noqa: E402

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
__CSS__
/* —— 本地工作台补充样式（官方 materiality.css 未覆盖的自定义部分） —— */
.dm-topic-desc{width:100%;margin:0;border:0;background:transparent;color:#6e8178;font-size:10px;line-height:1.55;resize:none;overflow:hidden}
.dm-topic-desc:hover,.dm-topic-desc:focus{outline:none;color:#4d6a5c}
.dm-topic-groups--list .dm-topic-desc{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* —— 品牌与引流（--brand off 时不渲染） —— */
.dm-header-top a.dm-back{display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border:1px solid rgba(255,255,255,.55);border-radius:999px;font-size:11px;color:#fff;font-weight:600;white-space:nowrap;text-decoration:none}
.dm-header-top a.dm-back:hover{background:rgba(255,255,255,.16);border-color:#fff}
.dm-brand-line{display:flex;align-items:center;gap:9px;margin-top:8px;font-size:10px;color:#6e8178;flex-wrap:wrap}
.dm-brand-line em{font-style:normal;color:#4d6a5c}
.dm-brand-cta{display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:999px;background:#1f5b45;color:#fff;font-size:11px;font-weight:600;letter-spacing:.2px;text-decoration:none;box-shadow:0 2px 7px rgba(31,91,69,.22)}
.dm-brand-cta:hover{background:#25704f}
.dm-brand-cta::after{content:'\2192';font-size:12px}
.dm-brand-qr{display:flex;align-items:center;gap:9px;flex:0 0 auto}
.dm-brand-qr img{width:64px;height:64px;border-radius:7px;border:1px solid #e2eae5;background:#fff}
.dm-brand-qr b{display:block;font-size:9px;font-weight:600;color:#5d7167;line-height:1.4}
</style>
</head>
<body>
<main id="topic-app" aria-label="双重重要性评估选题"></main>
<script>
const LIB = __LIB__;
const SEED = __SEED__;
const BRAND = __BRAND__;
const KEY = 'dm-topics-' + SEED.libraryId;
const CAT = {E:'环境', S:'社会', G:'治理'};
const CAT_NOTE = {E:'环境相关议题', S:'社会相关议题', G:'可持续发展相关治理'};

let rows = (SEED.topics && SEED.topics.length ? SEED.topics : LIB.topics).map(function (t) {
  return {checked: true, name: t.name, category: t.category, description: t.description, source: t.source || '议题库'};
});
let topicView = 'cards';

function esc(v) {
  return String(v == null ? '' : v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ---- 品牌与引流（BRAND.on=false 时全部返回空串） ---- */
function brandBack() {
  if (!BRAND.on) return '';
  return '<a class="dm-back" href="' + BRAND.url + '" target="_blank" rel="noopener">&larr; 返回项目与工具</a>';
}
function brandFooter() {
  if (!BRAND.on) return '';
  return '<span class="dm-brand-line"><em>' + esc(BRAND.name) + ' · ' + esc(BRAND.tool) + '</em>'
    + '<a class="dm-brand-cta" href="' + BRAND.url + '" target="_blank" rel="noopener">进入社区</a></span>';
}
function brandQr() {
  if (!BRAND.on || !BRAND.qr) return '';
  return '<span class="dm-brand-qr"><img src="' + BRAND.qr + '" alt="' + esc(BRAND.name) + '二维码"><b>扫码关注<br>' + esc(BRAND.name) + '</b></span>';
}

function cardHtml(r, i) {
  const cls = 'dm-topic dm-topic--' + r.category.toLowerCase() + (r.checked ? ' is-selected' : '');
  const src = r.source === '自定义' ? '<span class="dm-topic-ref"><b>企业自定义</b><i>新增议题</i></span>' : '<span class="dm-topic-ref"><b>议题库</b><i>' + esc(SEED.libraryId) + '</i></span>';
  return '<article class="' + cls + '" data-card="' + i + '">'
    + '<div class="dm-topic-select"><label><input type="checkbox" data-check="' + i + '"' + (r.checked ? ' checked' : '') + '><span aria-hidden="true"></span></label><b>' + CAT[r.category] + '</b></div>'
    + '<input class="dm-topic-name" data-name="' + i + '" value="' + esc(r.name) + '" aria-label="议题名称">'
    + '<textarea class="dm-topic-desc" data-desc="' + i + '" rows="3" placeholder="议题说明（进问卷题干）">' + esc(r.description || '') + '</textarea>'
    + '<div class="dm-topic-sources">' + src + '</div>'
    + '</article>';
}

function picked() {
  return rows.filter(function (r) { return r.checked && r.name.trim(); }).map(function (r, i) {
    return {
      code: 'Q' + String(i + 1).padStart(2, '0'),
      id: 'Q' + String(i + 1).padStart(2, '0'),
      name: r.name.trim(),
      category: r.category,
      description: (r.description || '').trim(),
      source: r.source || '议题库'
    };
  });
}

function counts() {
  const pickedRows = rows.filter(function (r) { return r.checked && r.name.trim(); });
  return {
    total: pickedRows.length,
    E: pickedRows.filter(function (r) { return r.category === 'E'; }).length,
    S: pickedRows.filter(function (r) { return r.category === 'S'; }).length,
    G: pickedRows.filter(function (r) { return r.category === 'G'; }).length
  };
}

function render() {
  const c = counts();
  const groups = ['E', 'S', 'G'].map(function (cat) {
    const idx = rows.map(function (r, i) { return {r: r, i: i}; }).filter(function (x) { return x.r.category === cat; });
    if (!idx.length) return '';
    const sel = idx.filter(function (x) { return x.r.checked && x.r.name.trim(); }).length;
    return '<section class="dm-topic-group dm-topic-group--' + cat.toLowerCase() + '"><header><div><b>' + CAT[cat] + '</b><small>' + sel + '／' + idx.length + ' 项已选</small></div><span>' + CAT_NOTE[cat] + '</span></header>'
      + '<div class="dm-topic-grid">' + idx.map(function (x) { return cardHtml(x.r, x.i); }).join('') + '</div></section>';
  }).join('');
  const app = document.getElementById('topic-app');
  app.innerHTML = '<div class="dm-shell">'
    + '<header class="dm-header"><div class="dm-header-top">' + brandBack() + '<span>双重重要性评估 · 本地工作台</span><span>体验版 · 浏览器自动保存</span></div>'
    + '<div class="dm-header-main"><div><span class="dm-eyebrow">DOUBLE MATERIALITY ASSESSMENT</span><h1>双重重要性评估</h1><p>从议题库勾选进入本次评估的议题，可修改名称、类别与说明，也可新增企业特色议题。编号按最终顺序重排为 Q01…Qnn，与问卷题号和计分匹配。</p></div></div>'
    + '<nav class="dm-hero-flow" aria-label="评估步骤">'
    + '<button type="button" class="is-active"><b>01</b><span><strong>评估范围</strong><small>企业与问卷平台</small></span></button>'
    + '<button type="button" class="is-active"><b>02</b><span><strong>议题清单</strong><small>分组筛选与校准</small></span></button>'
    + '<button type="button" disabled><b>03</b><span><strong>问卷收集</strong><small>飞书／问卷星回收</small></span></button>'
    + '<button type="button" disabled><b>04</b><span><strong>评分与矩阵</strong><small>计分、审核与定稿</small></span></button>'
    + '</nav></header>'
    + '<div class="dm-page">'
    + '<section class="dm-setup dm-panel"><div class="dm-panel-head"><div><small>企业画像</small><h2>先确定评估边界</h2></div><p>企业名称与行业进入问卷标题和后续所有产出文件；问卷平台决定下一步在哪制作问卷。</p></div>'
    + '<div class="dm-form-grid">'
    + '<label><span>企业名称</span><input type="text" id="company" maxlength="80" value="' + esc(document.getElementById('company') ? document.getElementById('company').value : SEED.project.company) + '"></label>'
    + '<label><span>所属行业</span><input type="text" id="industry" maxlength="40" value="' + esc(document.getElementById('industry') ? document.getElementById('industry').value : SEED.project.industry) + '"></label>'
    + '<label><span>问卷平台</span><select id="platform"><option value="feishu">飞书多维表格</option><option value="wjx">问卷星（半自动）</option></select></label>'
    + '</div></section>'
    + '<section class="dm-library dm-panel"><div class="dm-panel-head dm-topic-head"><div><small>候选议题库 · __LIBNAME__</small><h2>按环境、社会、治理校准议题</h2></div>'
    + '<div class="dm-topic-tools"><div class="dm-view-switch" role="group" aria-label="议题布局"><button type="button" data-view="cards" class="' + (topicView === 'cards' ? 'is-active' : '') + '">卡片</button><button type="button" data-view="list" class="' + (topicView === 'list' ? 'is-active' : '') + '">列表</button></div>'
    + '<div class="dm-selection-count"><strong>' + c.total + '</strong><span>已选议题</span></div></div></div>'
    + '<form class="dm-custom-form" id="addForm"><div><span>＋ 新增行业或企业特色议题</span><small>新增后直接加入本次评估</small></div>'
    + '<input name="topicName" maxlength="60" required placeholder="输入议题名称">'
    + '<select name="topicCategory"><option value="E">环境</option><option value="S">社会</option><option value="G">治理</option></select>'
    + '<input name="topicDescription" maxlength="160" placeholder="简要说明议题范围（可选）">'
    + '<button type="submit">添加议题</button></form>'
    + '<div class="dm-library-note"><span>名称与说明可直接修改</span><p>勾选进入本次评估；删除请勾选后点下方工具按钮。编号按最终顺序自动重排。</p></div>'
    + '<div class="dm-topic-groups dm-topic-groups--' + topicView + '">' + groups + '</div>'
    + '<footer class="dm-step-actions"><div><small>确认后发生什么</small><p>议题清单写回项目目录的 project.json，编号自动重排；下一步按所选平台生成问卷（飞书自动创建，问卷星导出导入文件）。</p></div>'
    + '<div class="dm-step-action-buttons"><button type="button" class="dm-secondary" data-act="del">删除勾选议题</button><button type="button" class="dm-secondary" data-act="reset">恢复议题库默认</button><button type="button" class="dm-primary" id="confirm"' + (c.total ? '' : ' disabled') + '>确认选题，进入问卷制作 <span>→</span></button></div></footer>'
    + '</section>'
    + '</div>'
    + '<footer class="dm-footer"><span>议题库 ' + esc(SEED.libraryId) + ' · 步骤 1-2 / 4' + brandFooter() + '</span><p>页面修改自动暂存在本浏览器；点确认后写入项目文件，以项目文件为准。</p>' + brandQr() + '</footer>'
    + '</div>';

  const platform = document.getElementById('platform');
  platform.value = SEED.project.platform === 'wjx' ? 'wjx' : 'feishu';

  app.querySelectorAll('[data-check]').forEach(function (el) {
    el.onchange = function () { rows[+el.dataset.check].checked = el.checked; render(); };
  });
  app.querySelectorAll('[data-name]').forEach(function (el) {
    el.oninput = function () { rows[+el.dataset.name].name = el.value; save(); };
  });
  app.querySelectorAll('[data-desc]').forEach(function (el) {
    el.oninput = function () { rows[+el.dataset.desc].description = el.value; save(); };
  });
  ['company', 'industry', 'platform'].forEach(function (id) {
    document.getElementById(id).onchange = function () { save(); };
  });
  document.getElementById('addForm').onsubmit = function (e) {
    e.preventDefault();
    const f = e.target;
    const name = f.topicName.value.trim();
    if (!name) return;
    rows.push({checked: true, name: name, category: f.topicCategory.value, description: f.topicDescription.value.trim(), source: '自定义'});
    f.reset();
    render();
  };
  app.querySelectorAll('[data-view]').forEach(function (el) {
    el.onclick = function () { topicView = el.dataset.view; render(); };
  });
  app.querySelectorAll('[data-act]').forEach(function (el) {
    el.onclick = function () {
      if (el.dataset.act === 'del') {
        const n = rows.filter(function (r) { return r.checked; }).length;
        if (!n) return;
        if (!confirm('删除勾选的 ' + n + ' 个议题？')) return;
        rows = rows.filter(function (r) { return !r.checked; });
        render();
      }
      if (el.dataset.act === 'reset') {
        if (!confirm('恢复为议题库默认 ' + LIB.topics.length + ' 项？当前修改会丢失。')) return;
        rows = LIB.topics.map(function (t) { return {checked: true, name: t.name, category: t.category, description: t.description, source: '议题库'}; });
        render();
      }
    };
  });
  document.getElementById('confirm').onclick = confirmTopics;
  save();
}

function save() {
  const company = document.getElementById('company');
  if (!company) return;
  localStorage.setItem(KEY, JSON.stringify({
    company: company.value,
    industry: document.getElementById('industry').value,
    platform: document.getElementById('platform').value,
    topicView: topicView,
    rows: rows
  }));
}

function restore() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    if (s.rows && s.rows.length) rows = s.rows;
    if (s.company) SEED.project.company = s.company;
    if (s.industry) SEED.project.industry = s.industry;
    if (s.platform) SEED.project.platform = s.platform;
    if (s.topicView) topicView = s.topicView;
  } catch (e) {}
}

function download(name, text) {
  const blob = new Blob([text], {type: 'application/json;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
}

function say(text, bad) {
  const foot = document.querySelector('.dm-step-actions p');
  foot.textContent = text;
  foot.style.color = bad ? '#b4442f' : '#829188';
  document.getElementById('confirm').disabled = false;
  document.getElementById('confirm').querySelector('span').textContent = '→';
}

async function confirmTopics() {
  const p = JSON.parse(JSON.stringify(SEED.project));
  p.company = document.getElementById('company').value.trim() || '未命名企业';
  p.industry = document.getElementById('industry').value.trim() || '未填写';
  p.platform = document.getElementById('platform').value;
  p.topics = picked();
  p.stage = 'topics';
  if (!p.topics.length) { say('至少保留一个议题', true); return; }
  const btn = document.getElementById('confirm');
  btn.disabled = true;
  btn.querySelector('span').textContent = '正在写回…';
  try {
    const r = await fetch('/api/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({kind: 'topics', project: p})
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || '写回失败');
    say('已写回 ' + j.saved[0] + '（' + p.topics.length + ' 个议题），回到对话继续。');
  } catch (e) {
    download('project.json', JSON.stringify(p, null, 2));
    say('未连上本地服务，已下载 project.json，请放回项目目录后告诉我。', true);
    btn.disabled = false;
    btn.querySelector('span').textContent = '→';
  }
}

restore();
render();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="生成步骤 1 选题页面")
    ap.add_argument("--project", required=True, help="项目目录或 project.json 路径")
    ap.add_argument("--out", help="输出 HTML 路径，默认放项目目录")
    ap.add_argument("--library", default=None, help="强制指定议题库 id")
    ap.add_argument("--brand", default="on", help="品牌与引流元素：on（默认）/ off，off 时页头链接、页脚署名全部不渲染")
    ap.add_argument("--qr", default=None, help="可选：本地二维码图片路径，内嵌到页脚（png/jpg/svg）")
    args = ap.parse_args()

    project = load_project(args.project)
    lib_id = args.library or project.get("libraryId") or "agri-general-2025"
    lib = get_library(lib_id)

    seed_topics = project.get("topics") or []
    if not seed_topics:
        seed_topics = normalize_topics(lib["topics"])

    css_path = Path(__file__).resolve().parent.parent / "assets" / "materiality.css"
    css = css_path.read_text(encoding="utf-8")

    title = f"{project['company']} · 双重重要性评估选题"
    html = (
        TPL.replace("__TITLE__", title)
        .replace("__CSS__", css)
        .replace("__LIBNAME__", lib["name"])
        .replace("__BRAND__", json.dumps(brand_payload(args.brand, args.qr), ensure_ascii=False))
        .replace("__LIB__", json.dumps(lib["topics"], ensure_ascii=False))
        .replace("__SEED__", json.dumps({
            "libraryId": lib_id,
            "topics": seed_topics,
            "project": project,
        }, ensure_ascii=False))
    )

    out = Path(args.out) if args.out else Path(args.project) / f"01_选题-{project['company']}.html"
    if Path(args.project).is_file():
        out = Path(args.out) if args.out else Path(args.project).parent / f"01_选题-{project['company']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"ok {out} {out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
