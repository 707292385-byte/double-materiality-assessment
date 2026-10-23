#!/usr/bin/env python3
"""步骤 5：生成「审核与调分」本地页面。

样式内联 assets/materiality.css（与用户 GitHub Pages 双重重要性评估页同源，v=20261023-12）：
页头内嵌四步 dm-hero-flow（本页为第 4 步）、S=橙/G=蓝 新配色、矩阵横轴财务纵轴影响、
象限命名与线上版一致（双重重要／单一重要／不重要）、区域颜色可在图例中自定义。
矩阵圆点 r=9、图例移到矩阵下方；保留 skill 特有的双阈值滑杆、逐行滑杆校准与审核写回。

按钮只保留三类：结果工具栏的导出（图片/Excel/快照）、逐项校准的恢复原始分、底部唯一的
「确认并写回项目」——确认即定稿并写回，不单设定稿按钮。

产出（确认时自动生成并写回项目目录）：矩阵 PNG、Excel（明细/审核留痕/评估说明）、审核快照 JSON。

用法：
  python3 build_review.py --project <项目目录> [--scores scores.json] [--out 03_审核.html]
                          [--brand on|off] [--qr <二维码图片>]

--brand off 关闭全部引流元素（页头返回链接、页脚署名、矩阵 PNG 署名、Excel「工具来源」行），
用于不希望出现外部署名的客户项目；--qr 可内嵌一张二维码到页脚（页面仍是自包含单文件）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dm_lib import brand_payload, load_project, save_project  # noqa: E402

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
__CSS__
/* —— 本地工作台补充样式（官方 materiality.css 未覆盖的自定义部分） —— */
.dm-result--single{background:#e5f3ed;color:#257554}
.dm-result--none{background:#f0f1ef;color:#7b817d}
.dm-log{margin:0 22px 20px;padding:10px 13px;border:1px solid #e5ece7;border-radius:10px;background:#fafcfb;font-size:9px;color:#6e8178;max-height:150px;overflow:auto}
.dm-log div{padding:3px 0;border-bottom:1px dashed #e6efe9}
.dm-reviewer-input{border:1px solid #d7e4da;border-radius:6px;padding:3px 8px;font-size:10px;width:110px}
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
<main id="review-app" aria-label="双重重要性审核"></main>
<script>
const DATA = __DATA__;
const BRAND = __BRAND__;
const KEY = 'dm-review-' + DATA.company + '-' + DATA.topics.length;
const DEFAULT_MATRIX_COLORS = { double: '#1f5b45', single: '#dceee3', none: '#ffffff' };

const state = {
  thresholds: {impact: DATA.thresholds.impact, financial: DATA.thresholds.financial},
  topics: DATA.topics.map(t => ({
    code: t.code, name: t.name, category: t.category, description: t.description,
    direction: (t.impact && t.impact.direction) || '',
    impact: t.impact.score, finance: t.finance.score,
    origImpact: t.impact.score, origFinance: t.finance.score,
    note: t.note || ''
  })),
  reviewer: '',
  edits: {},
  events: [],
  locked: false,
  lockedAt: '',
  matrixColors: Object.assign({}, DEFAULT_MATRIX_COLORS),
  order: DATA.topics.slice().sort((a, b) =>
    (b.impact.score + b.finance.score) - (a.impact.score + a.finance.score)).map(t => t.code),
  filter: 'all'
};

const CAT = {E: '环境', S: '社会', G: '治理'};

function esc(v) {
  return String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* ---- 品牌与引流（BRAND.on=false 时全部返回空串，导出物同样不带） ---- */
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
function now() {
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}
function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    if (s.thresholds) state.thresholds = s.thresholds;
    if (s.topics && s.topics.length === state.topics.length) state.topics = s.topics;
    state.reviewer = s.reviewer || '';
    state.edits = s.edits || {};
    state.events = s.events || [];
    state.locked = !!s.locked;
    state.lockedAt = s.lockedAt || '';
    if (s.matrixColors) state.matrixColors = Object.assign({}, DEFAULT_MATRIX_COLORS, s.matrixColors);
    if (s.order && s.order.length) state.order = s.order;
  } catch (e) {}
}
function save() {
  localStorage.setItem(KEY, JSON.stringify({
    thresholds: state.thresholds, topics: state.topics, reviewer: state.reviewer,
    edits: state.edits, events: state.events, locked: state.locked, lockedAt: state.lockedAt,
    matrixColors: state.matrixColors, order: state.order
  }));
}
function event(text) { state.events.push({ts: now(), text: text}); }

function verdict(t) {
  const hiI = t.impact >= state.thresholds.impact;
  const hiF = t.finance >= state.thresholds.financial;
  if (hiI && hiF) return {key: 'double', label: '双重重要'};
  if (hiI || hiF) return {key: 'single', label: '单一重要'};
  return {key: 'none', label: '不重要'};
}
function isChanged(t) {
  return Math.abs(t.impact - t.origImpact) > 0.001 || Math.abs(t.finance - t.origFinance) > 0.001;
}
function ranked() {
  return state.topics.slice().sort((a, b) => (b.impact + b.finance) - (a.impact + a.finance));
}
function counts() {
  const c = {double: 0, single: 0, none: 0};
  state.topics.forEach(t => { c[verdict(t).key] += 1; });
  return c;
}
function clamp(v) {
  if (isNaN(v)) return 3;
  return Math.min(5, Math.max(1, Math.round(v * 10) / 10));
}
function touch(t) {
  const e = state.edits[t.code] || {};
  e.ts = now();
  e.impact = t.impact; e.finance = t.finance;
  state.edits[t.code] = e;
}

/* ---- 矩阵（横轴财务，纵轴影响；区域颜色可在图例自定义；与 GitHub Pages 版一致） ---- */
function mx(score) { return 72 + ((score - 1) / 4) * 468; }
function my(score) { return 522 - ((score - 1) / 4) * 438; }
function spread(points) {
  const buckets = {};
  points.forEach(p => {
    const k = p.x.toFixed(1) + ',' + p.y.toFixed(1);
    (buckets[k] = buckets[k] || []).push(p);
  });
  Object.values(buckets).forEach(list => {
    if (list.length < 2) return;
    list.forEach((p, i) => {
      const ang = (Math.PI * 2 * i) / list.length - Math.PI / 2;
      p.x += Math.cos(ang) * 14;
      p.y += Math.sin(ang) * 14;
    });
  });
  return points;
}
function renderMatrix() {
  const ti = state.thresholds.impact, tf = state.thresholds.financial;
  const tx = mx(tf), ty = my(ti);
  const colors = state.matrixColors;
  const order = ranked();
  const idx = {};
  order.forEach((t, i) => { idx[t.code] = i + 1; });
  const pts = spread(state.topics.map(t => ({code: t.code, x: mx(t.finance), y: my(t.impact), t: t})));
  const grid = [1, 2, 3, 4, 5].map(v =>
    '<line x1="' + mx(v) + '" x2="' + mx(v) + '" y1="84" y2="522"/><line x1="72" x2="540" y1="' + my(v) + '" y2="' + my(v) + '"/>'
    + '<text x="' + mx(v) + '" y="548">' + v + '</text><text x="53" y="' + (my(v) + 4) + '">' + v + '</text>').join('');
  const points = pts.map(p => {
    const t = p.t;
    return '<g class="dm-point dm-point--' + t.category.toLowerCase() + '"><title>'
      + esc(idx[t.code] + '. ' + t.name + '｜影响 ' + t.impact.toFixed(1) + '｜财务 ' + t.finance.toFixed(1) + '｜' + verdict(t).label)
      + '</title><circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="9"></circle>'
      + '<text x="' + p.x.toFixed(1) + '" y="' + (p.y + 3).toFixed(1) + '">' + idx[t.code] + '</text></g>';
  }).join('');
  return '<svg class="dm-matrix" id="matrix" viewBox="0 0 600 590" xmlns="http://www.w3.org/2000/svg" role="img">'
    + '<title>' + esc(DATA.company) + ' 双重重要性矩阵</title>'
    + '<desc>横轴是财务重要性，纵轴是影响重要性，虚线为当前阈值。</desc>'
    + '<rect x="0" y="0" width="600" height="590" fill="#ffffff"/>'
    + '<rect class="dm-quadrant" x="72" y="84" width="' + Math.max(0, tx - 72) + '" height="' + Math.max(0, ty - 84) + '" fill="' + colors.single + '"></rect>'
    + '<rect class="dm-quadrant" x="' + tx + '" y="84" width="' + Math.max(0, 540 - tx) + '" height="' + Math.max(0, ty - 84) + '" fill="' + colors.double + '"></rect>'
    + '<rect class="dm-quadrant" x="72" y="' + ty + '" width="' + Math.max(0, tx - 72) + '" height="' + Math.max(0, 522 - ty) + '" fill="' + colors.none + '"></rect>'
    + '<rect class="dm-quadrant" x="' + tx + '" y="' + ty + '" width="' + Math.max(0, 540 - tx) + '" height="' + Math.max(0, 522 - ty) + '" fill="' + colors.single + '"></rect>'
    + '<g class="dm-grid">' + grid + '</g>'
    + '<line class="dm-threshold-line" x1="' + tx + '" x2="' + tx + '" y1="84" y2="522"></line>'
    + '<line class="dm-threshold-line" x1="72" x2="540" y1="' + ty + '" y2="' + ty + '"></line>'
    + '<line class="dm-axis" x1="72" x2="540" y1="522" y2="522"></line><line class="dm-axis" x1="72" x2="72" y1="84" y2="522"></line>'
    + '<text class="dm-axis-title" x="306" y="579">财务重要性 →</text>'
    + '<text class="dm-axis-title" x="-305" y="20" transform="rotate(-90)">影响重要性 →</text>'
    + '<g class="dm-points">' + points + '</g></svg>';
}
function renderMatrixLegend() {
  const regions = [['double', '双重重要'], ['single', '单一重要'], ['none', '不重要']];
  return '<div class="dm-matrix-legend"><div class="dm-region-colors"><b>区域颜色</b>'
    + regions.map(r => '<label><input type="color" value="' + state.matrixColors[r[0]] + '" data-matrix-color="' + r[0] + '" aria-label="修改' + r[1] + '区域颜色"><i style="background:' + state.matrixColors[r[0]] + '"></i><span>' + r[1] + '</span></label>').join('')
    + '</div><div class="dm-topic-colors"><b>议题类别</b><span><i class="e"></i>环境</span><span><i class="s"></i>社会</span><span><i class="g"></i>治理</span></div>'
    + '<small>圆点编号对应下方议题顺序</small></div>';
}

/* ---- 页面骨架 ---- */
function rowHtml(t, i) {
  const v = verdict(t);
  return '<article class="dm-score-row dm-score-row--' + t.category.toLowerCase() + '" data-row="' + t.code + '">'
    + '<div class="dm-score-topic"><span>' + i + '</span><div><small>' + CAT[t.category] + ' · ' + esc(t.code) + (t.direction ? ' · ' + esc(t.direction) : '') + '</small><strong>' + esc(t.name) + '</strong></div>'
    + '<b class="dm-result dm-result--' + v.key + '" data-result="' + t.code + '">' + v.label + '</b></div>'
    + '<label class="dm-score-control"><span>影响重要性 <output data-out="' + t.code + ':impact">' + t.impact.toFixed(1) + '</output></span>'
    + '<input type="range" min="1" max="5" step="0.1" value="' + t.impact + '" data-slider="' + t.code + ':impact"><small>对经济、环境和人产生的实际或潜在影响</small></label>'
    + '<label class="dm-score-control"><span>财务重要性 <output data-out="' + t.code + ':finance">' + t.finance.toFixed(1) + '</output></span>'
    + '<input type="range" min="1" max="5" step="0.1" value="' + t.finance + '" data-slider="' + t.code + ':finance"><small>对企业财务状况、经营成果和现金流的影响</small></label>'
    + '<details class="dm-evidence"><summary>调整理由与评分备注（改分必填）</summary>'
    + '<textarea data-note="' + t.code + '" rows="2" placeholder="记录调整理由、利益相关方反馈或管理层判断…">' + esc(t.note || '') + '</textarea></details>'
    + '</article>';
}

function shellHtml() {
  const c = counts();
  const changed = state.topics.filter(isChanged).length;
  const visible = state.order.map(code => state.topics.find(t => t.code === code))
    .filter(t => state.filter === 'all' || t.category === state.filter || (state.filter === 'edited' && isChanged(t)));
  const tabs = [['all', '全部'], ['E', '环境'], ['S', '社会'], ['G', '治理'], ['edited', '已调整 ' + changed]];
  return '<div class="dm-shell">'
    + '<header class="dm-header"><div class="dm-header-top">' + brandBack() + '<span>双重重要性评估 · 本地工作台</span><span>体验版 · 浏览器自动保存</span></div>'
    + '<div class="dm-header-main"><div><span class="dm-eyebrow">DOUBLE MATERIALITY REVIEW</span><h1>双重重要性评估</h1>'
    + '<p>矩阵按计分结果绘制：横轴财务重要性、纵轴影响重要性，虚线为阈值。拖动阈值或逐项调分会即时联动；调整理由写入留痕，确认后一键定稿并写回项目。</p></div></div>'
    + '<nav class="dm-hero-flow" aria-label="评估步骤">'
    + '<button type="button" class="is-complete"><b>01</b><span><strong>评估范围</strong><small>已完成</small></span></button>'
    + '<button type="button" class="is-complete"><b>02</b><span><strong>议题清单</strong><small>已完成</small></span></button>'
    + '<button type="button" class="is-complete"><b>03</b><span><strong>问卷收集</strong><small>影响 ' + DATA.meta.impact.kept + ' 份｜财务 ' + DATA.meta.finance.kept + ' 份</small></span></button>'
    + '<button type="button" class="is-active"><b>04</b><span><strong>评分与矩阵</strong><small>复核分数并定稿</small></span></button>'
    + '</nav></header>'
    + '<div class="dm-page">'
    + '<section class="dm-results dm-panel"><div class="dm-result-toolbar"><div><small>结果视图</small><h2>' + esc(DATA.company) + ' · 重要性矩阵</h2></div>'
    + '<div class="dm-toolbar-actions"><button type="button" data-act="png">导出矩阵图片</button><button type="button" data-act="xlsx">导出 Excel</button><button type="button" data-act="snapshot">导出审核快照</button></div></div>'
    + '<div class="dm-result-layout"><div class="dm-matrix-column"><div class="dm-matrix-wrap" data-matrix-wrap>' + renderMatrix() + '</div>' + renderMatrixLegend() + '</div>'
    + '<aside class="dm-result-side"><div class="dm-side-title"><small>结果概览</small><strong>' + state.topics.length + ' 个议题</strong></div>'
    + '<div class="dm-summary"><div><strong data-k="double">' + c.double + '</strong><span>双重重要</span></div><div><strong data-k="single">' + c.single + '</strong><span>单一重要</span></div><div><strong data-k="none">' + c.none + '</strong><span>不重要</span></div><div><strong data-k="edited">' + changed + '</strong><span>已调整</span></div></div>'
    + '<div class="dm-threshold">'
    + '<label><span>影响重要性阈值</span><input type="range" min="1" max="5" step="0.1" value="' + state.thresholds.impact + '" data-th="impact"><output data-thout="impact">' + state.thresholds.impact.toFixed(1) + '</output></label>'
    + '<label><span>财务重要性阈值</span><input type="range" min="1" max="5" step="0.1" value="' + state.thresholds.financial + '" data-th="financial"><output data-thout="financial">' + state.thresholds.financial.toFixed(1) + '</output></label>'
    + '<p>结论按阈值实时重算：两维均达标＝双重重要，单维达标＝单一重要，均未达＝不重要。</p></div>'
    + '<div class="dm-result-rule"><b>审核信息</b>'
    + '<span>影响问卷有效 <b>' + DATA.meta.impact.kept + '</b> 份（回收 ' + DATA.meta.impact.rows + ' 份）</span>'
    + '<span>财务问卷有效 <b>' + DATA.meta.finance.kept + '</b> 份（回收 ' + DATA.meta.finance.rows + ' 份）</span>'
    + '<span>审核人 <input type="text" id="reviewer" class="dm-reviewer-input" placeholder="填写姓名" value="' + esc(state.reviewer) + '"></span>'
    + '<span>状态：' + (state.locked ? '已定稿 ' + state.lockedAt : '过程稿（确认后定稿）') + '</span></div>'
    + '</aside></div></section>'
    + '<section class="dm-score-list dm-panel"><div class="dm-panel-head"><div><small>逐项校准</small><h2>调整议题分数</h2></div>'
    + '<div class="dm-toolbar-actions"><button type="button" data-act="reset">恢复原始分</button></div></div>'
    + '<div class="dm-filter-tabs" role="group">' + tabs.map(t => '<button type="button" data-tab="' + t[0] + '" class="' + (state.filter === t[0] ? 'is-active' : '') + '">' + t[1] + '</button>').join('') + '</div>'
    + '<div class="dm-score-rows">' + visible.map((t) => rowHtml(t, state.order.indexOf(t.code) + 1)).join('') + '</div>'
    + '<div class="dm-log" data-log></div>'
    + '</section>'
    + '<section class="dm-step-actions" style="border:1px solid var(--dm-line);border-radius:16px;background:rgba(255,255,255,.96);box-shadow:var(--dm-shadow)"><div><small>确认后发生什么</small>'
    + '<p data-status>点「确认并写回项目」即定稿：生成矩阵图片、Excel（议题得分明细 / 审核留痕 / 评估说明）与审核快照，直接写入项目目录，不需要逐个下载。</p></div>'
    + '<button type="button" class="dm-primary" data-act="commit">确认并写回项目（定稿） <span>→</span></button></section>'
    + '</div>'
    + '<footer class="dm-footer"><span>计分口径：影响 1+0.8×|均值|，财务 √(程度×可能性) 均值 · 步骤 4 / 4' + brandFooter() + '</span><p>页面修改自动暂存在本浏览器；导出文件与写回结果才是审核证据。</p>' + brandQr() + '</footer>'
    + '</div>';
}

function renderLog() {
  const box = document.querySelector('[data-log]');
  const items = [];
  Object.entries(state.edits).forEach(entry => {
    const t = state.topics.find(x => x.code === entry[0]);
    if (!t) return;
    const dI = Math.abs(t.impact - t.origImpact) > 0.001;
    const dF = Math.abs(t.finance - t.origFinance) > 0.001;
    const what = [dI ? '影响 ' + t.origImpact.toFixed(1) + '→' + t.impact.toFixed(1) : '',
      dF ? '财务 ' + t.origFinance.toFixed(1) + '→' + t.finance.toFixed(1) : ''].filter(Boolean).join('，');
    items.push({ts: entry[1].ts || '', text: t.code + ' ' + t.name + '：' + (what || '仅填写审核说明') + (t.note ? '｜理由：' + t.note : '')});
  });
  state.events.forEach(e => items.push(e));
  items.sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
  box.innerHTML = '<b style="color:#648173;font-weight:800">调整记录</b>' + (items.length
    ? items.slice(0, 8).map(e => '<div>' + (e.ts || '') + '　' + esc(e.text) + '</div>').join('')
    : '<div>尚无调整；拖动分数或填写理由后，这里按时间倒序记录。</div>');
}

/* 拖滑杆时只联动矩阵与统计，不重建行，保证拖动流畅 */
function updateLive() {
  const wrap = document.querySelector('[data-matrix-wrap]');
  if (wrap) wrap.innerHTML = renderMatrix();
  const c = counts();
  Object.entries(c).forEach(([k, v]) => {
    const n = document.querySelector('[data-k="' + k + '"]');
    if (n) n.textContent = v;
  });
  state.topics.forEach(t => {
    const badge = document.querySelector('[data-result="' + t.code + '"]');
    if (badge) {
      const v = verdict(t);
      badge.className = 'dm-result dm-result--' + v.key;
      badge.textContent = v.label;
    }
    [['impact', t.impact], ['finance', t.finance]].forEach(pair => {
      const out = document.querySelector('[data-out="' + t.code + ':' + pair[0] + '"]');
      if (out) out.textContent = pair[1].toFixed(1);
    });
  });
  save();
}

function bind() {
  document.querySelectorAll('[data-th]').forEach(el => {
    el.oninput = () => {
      const v = parseFloat(el.value);
      const k = el.dataset.th;
      if (Math.abs(v - state.thresholds[k]) > 0.001) event((k === 'impact' ? '影响' : '财务') + '阈值 ' + state.thresholds[k].toFixed(1) + ' → ' + v.toFixed(1));
      state.thresholds[k] = v;
      const out = document.querySelector('[data-thout="' + k + '"]');
      if (out) out.textContent = v.toFixed(1);
      updateLive();
    };
  });
  document.querySelectorAll('[data-matrix-color]').forEach(el => {
    el.oninput = () => {
      state.matrixColors[el.dataset.matrixColor] = el.value;
      const swatch = el.parentElement.querySelector('i');
      if (swatch) swatch.style.background = el.value;
      updateLive();
    };
  });
  const reviewer = document.getElementById('reviewer');
  reviewer.onchange = () => { state.reviewer = reviewer.value.trim(); save(); };
  document.querySelectorAll('[data-slider]').forEach(el => {
    const code = el.dataset.slider.split(':')[0], field = el.dataset.slider.split(':')[1];
    const t = state.topics.find(x => x.code === code);
    el.oninput = () => { t[field] = clamp(parseFloat(el.value)); updateLive(); };
    el.onchange = () => { touch(t); renderLog(); hintWarn(); save(); };
  });
  document.querySelectorAll('[data-note]').forEach(el => {
    const t = state.topics.find(x => x.code === el.dataset.note);
    el.onchange = () => { t.note = el.value.trim(); touch(t); renderLog(); hintWarn(); save(); };
  });
  document.querySelectorAll('[data-tab]').forEach(el => {
    el.onclick = () => { state.filter = el.dataset.tab; render(); };
  });
  document.querySelectorAll('[data-act]').forEach(el => {
    el.onclick = () => actions[el.dataset.act] && actions[el.dataset.act](el);
  });
}

function hintWarn() {
  const missing = state.topics.filter(t => isChanged(t) && !t.note).length;
  const p = document.querySelector('[data-status]');
  const base = '点「确认并写回项目」即定稿：生成矩阵图片、Excel（议题得分明细 / 审核留痕 / 评估说明）与审核快照，直接写入项目目录，不需要逐个下载。';
  p.textContent = missing ? base + ' 当前有 ' + missing + ' 项改分未写调整理由。' : base;
  p.style.color = missing ? '#b4442f' : '';
}

function render() {
  const app = document.getElementById('review-app');
  app.innerHTML = shellHtml();
  bind();
  renderLog();
  hintWarn();
  save();
}

/* ---- 导出与写回 ---- */
function downloadBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

function detailRows() {
  return ranked().map((t, i) => {
    const v = verdict(t);
    return [i + 1, DATA.company, DATA.industry, CAT[t.category], t.name, t.description, t.direction || '',
      +t.impact.toFixed(1), +t.finance.toFixed(1), v.label,
      +state.thresholds.impact.toFixed(1), +state.thresholds.financial.toFixed(1),
      +t.origImpact.toFixed(1), +t.origFinance.toFixed(1), t.note || ''];
  });
}
function logRows() {
  const rows = [];
  ranked().forEach(t => {
    if (!isChanged(t) && !t.note) return;
    const e = state.edits[t.code] || {};
    const ts = e.ts || now();
    if (Math.abs(t.impact - t.origImpact) > 0.001) {
      rows.push([rows.length + 1, ts, t.code, t.name, '影响重要性得分', +t.origImpact.toFixed(1), +t.impact.toFixed(1), +(t.impact - t.origImpact).toFixed(1), t.note || '']);
    }
    if (Math.abs(t.finance - t.origFinance) > 0.001) {
      rows.push([rows.length + 1, ts, t.code, t.name, '财务重要性得分', +t.origFinance.toFixed(1), +t.finance.toFixed(1), +(t.finance - t.origFinance).toFixed(1), t.note || '']);
    }
    if (!isChanged(t) && t.note) {
      rows.push([rows.length + 1, ts, t.code, t.name, '审核意见（未改分）', '', '', '', t.note]);
    }
  });
  state.events.forEach(ev => {
    rows.push([rows.length + 1, ev.ts, '', '', '阈值/流程', '', '', '', ev.text]);
  });
  return rows;
}
function baseName(p) { return p ? String(p).split(/[\\/]/).pop() : '—'; }
function summaryRows() {
  const c = counts();
  const mi = DATA.meta.impact, mf = DATA.meta.finance;
  const rows = [
    ['企业名称', DATA.company], ['所属行业', DATA.industry], ['评估年度', DATA.year || '未填写'],
    ['议题数量', state.topics.length + ' 项'],
    ['影响问卷有效份数', mi.kept + ' 份（回收 ' + mi.rows + ' 份）'],
    ['影响问卷剔除', '缺答 ' + mi.dropped['缺答'] + ' / 直线作答 ' + mi.dropped['直线作答'] + ' / 答题过快 ' + mi.dropped['答题过快']],
    ['财务问卷有效份数', mf.kept + ' 份（回收 ' + mf.rows + ' 份）'],
    ['财务问卷剔除', '缺答 ' + mf.dropped['缺答'] + ' / 直线作答 ' + mf.dropped['直线作答'] + ' / 答题过快 ' + mf.dropped['答题过快']],
    ['影响重要性阈值', state.thresholds.impact.toFixed(1)],
    ['财务重要性阈值', state.thresholds.financial.toFixed(1)],
    ['双重重要', c.double + ' 项'], ['单一重要', c.single + ' 项'],
    ['不重要', c.none + ' 项'],
    ['手工调整议题数', state.topics.filter(isChanged).length + ' 项'],
    ['审核人', state.reviewer || '未填写'],
    ['审核状态', state.locked ? '已定稿 ' + state.lockedAt : '过程稿（未定稿）'],
    ['计分口径', '影响：问卷 −5~+5 均值按强度折 1~5（1+0.8×|均值|）；财务：每份 √(影响程度×可能性) 后取均值'],
    ['数据来源', baseName(mi.source) + '；' + baseName(mf.source)],
    ['页面生成时间', '__STAMP__'], ['导出时间', now()]
  ];
  if (BRAND.on) rows.push(['工具来源', BRAND.name + ' · ' + BRAND.tool + ' · ' + BRAND.url]);
  return rows;
}

function pngBlob() {
  return new Promise((resolve, reject) => {
    const svg = document.getElementById('matrix');
    if (!svg) { reject(new Error('矩阵未渲染')); return; }
    const clone = svg.cloneNode(true);
    clone.setAttribute('width', 1440);
    clone.setAttribute('height', 1416);
    const xml = new XMLSerializer().serializeToString(clone);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = 1440; canvas.height = 1416;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 1440, 1416);
      ctx.drawImage(img, 0, 0, 1440, 1416);
      if (BRAND.on) {
        ctx.fillStyle = '#9aa8a0';
        ctx.font = '15px "PingFang SC","Microsoft YaHei",sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(BRAND.name + ' · ' + BRAND.tool + ' · ' + BRAND.url, 1400, 1402);
        ctx.textAlign = 'left';
      }
      canvas.toBlob(b => b ? resolve(b) : reject(new Error('PNG 生成失败')), 'image/png');
    };
    img.onerror = () => reject(new Error('PNG 渲染失败'));
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
  });
}

function buildSnapshot() {
  return {
    schema: 'dm-review/1.1',
    company: DATA.company, industry: DATA.industry,
    reviewer: state.reviewer,
    locked: state.locked, lockedAt: state.lockedAt,
    exportedAt: now(),
    thresholds: state.thresholds,
    matrixColors: state.matrixColors,
    topics: ranked().map(t => ({
      code: t.code, name: t.name, category: t.category,
      impact: +t.impact.toFixed(1), finance: +t.finance.toFixed(1),
      origImpact: +t.origImpact.toFixed(1), origFinance: +t.origFinance.toFixed(1),
      conclusion: verdict(t).label, note: t.note || ''
    })),
    events: state.events
  };
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) { let c = n; for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; table[n] = c >>> 0; }
  return table;
})();
function crc32(bytes) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i += 1) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
function zipStore(files) {
  const encoder = new TextEncoder();
  const parts = []; const central = [];
  let offset = 0;
  const nowD = new Date();
  const dosTime = ((nowD.getHours() << 11) | (nowD.getMinutes() << 5) | (nowD.getSeconds() / 2)) & 0xFFFF;
  const dosDate = (((nowD.getFullYear() - 1980) << 9) | ((nowD.getMonth() + 1) << 5) | nowD.getDate()) & 0xFFFF;
  files.forEach(file => {
    const nameBytes = encoder.encode(file.name);
    const data = typeof file.data === 'string' ? encoder.encode(file.data) : file.data;
    const crc = crc32(data);
    const local = new Uint8Array(30 + nameBytes.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true); lv.setUint16(4, 20, true); lv.setUint16(6, 0x0800, true);
    lv.setUint16(8, 0, true); lv.setUint16(10, dosTime, true); lv.setUint16(12, dosDate, true);
    lv.setUint32(14, crc, true); lv.setUint32(18, data.length, true); lv.setUint32(22, data.length, true);
    lv.setUint16(26, nameBytes.length, true); lv.setUint16(28, 0, true);
    local.set(nameBytes, 30);
    parts.push(local, data);
    const cen = new Uint8Array(46 + nameBytes.length);
    const cv = new DataView(cen.buffer);
    cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true); cv.setUint16(6, 20, true);
    cv.setUint16(8, 0x0800, true); cv.setUint16(10, 0, true); cv.setUint16(12, dosTime, true);
    cv.setUint16(14, dosDate, true); cv.setUint32(16, crc, true); cv.setUint32(20, data.length, true);
    cv.setUint32(24, data.length, true); cv.setUint16(28, nameBytes.length, true);
    cv.setUint32(42, offset, true);
    cen.set(nameBytes, 46);
    central.push(cen);
    offset += local.length + data.length;
  });
  const centralSize = central.reduce((sum, item) => sum + item.length, 0);
  const eocd = new Uint8Array(22);
  const ev = new DataView(eocd.buffer);
  ev.setUint32(0, 0x06054b50, true); ev.setUint16(8, files.length, true); ev.setUint16(10, files.length, true);
  ev.setUint32(12, centralSize, true); ev.setUint32(16, offset, true);
  return new Blob(parts.concat(central, [eocd]), {type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}
function sheetXml(rows, widths) {
  const cols = (widths || []).map((w, i) => '<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + w + '" customWidth="1"/>').join('');
  const escv = v => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const body = rows.map((cells, ri) => {
    const cellsXml = cells.map((value, ci) => {
      let ref = '';
      let n = ci;
      do { ref = String.fromCharCode(65 + (n % 26)) + ref; n = Math.floor(n / 26) - 1; } while (n >= 0);
      ref += (ri + 1);
      const style = ri === 0 ? ' s="1"' : '';
      if (typeof value === 'number' && isFinite(value)) return '<c r="' + ref + '"' + style + '><v>' + value + '</v></c>';
      return '<c r="' + ref + '"' + style + ' t="inlineStr"><is><t xml:space="preserve">' + escv(value) + '</t></is></c>';
    }).join('');
    return '<row r="' + (ri + 1) + '"' + (ri === 0 ? ' ht="24" customHeight="1"' : '') + '>' + cellsXml + '</row>';
  }).join('');
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    + '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
    + '<cols>' + cols + '</cols><sheetData>' + body + '</sheetData></worksheet>';
}
function xlsxBlob() {
  const sheets = [
    {
      name: '议题得分明细',
      widths: [6, 16, 10, 8, 24, 46, 10, 14, 14, 12, 14, 14, 11, 11, 30],
      rows: [['序号', '企业名称', '所属行业', '议题类别', '议题名称', '议题说明', '影响方向',
        '影响重要性得分(1-5)', '财务重要性得分(1-5)', '重要性结论', '重要性阈值(影响)', '重要性阈值(财务)',
        '原始影响分', '原始财务分', '审核说明'], ...detailRows()]
    },
    {
      name: '审核留痕',
      widths: [6, 18, 8, 24, 18, 12, 12, 10, 46],
      rows: [['序号', '时间', '编号', '议题', '调整项', '原值', '新值', '幅度', '调整理由/说明'], ...logRows()]
    },
    {
      name: '评估说明',
      widths: [22, 96],
      rows: [['项目', '内容'], ...summaryRows()]
    }
  ];
  const sheetFiles = sheets.map((s, i) => ({name: 'xl/worksheets/sheet' + (i + 1) + '.xml', data: sheetXml(s.rows, s.widths)}));
  const styles = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    + '<fonts count="2"><font><sz val="11"/><name val="宋体"/></font><font><b/><sz val="11"/><name val="宋体"/></font></fonts>'
    + '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
    + '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    + '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    + '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
    + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
  const workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    + '<sheets>' + sheets.map((s, i) => '<sheet name="' + s.name + '" sheetId="' + (i + 1) + '" r:id="rId' + (i + 1) + '"/>').join('') + '</sheets></workbook>';
  const wbRels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + sheets.map((s, i) => '<Relationship Id="rId' + (i + 1) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' + (i + 1) + '.xml"/>').join('')
    + '<Relationship Id="rId' + (sheets.length + 1) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    + '</Relationships>';
  const contentTypes = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    + '<Default Extension="xml" ContentType="application/xml"/>'
    + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    + sheets.map((s, i) => '<Override PartName="/xl/worksheets/sheet' + (i + 1) + '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>').join('')
    + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>';
  const rootRels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';
  return zipStore([
    {name: '[Content_Types].xml', data: contentTypes},
    {name: '_rels/.rels', data: rootRels},
    {name: 'xl/workbook.xml', data: workbook},
    {name: 'xl/_rels/workbook.xml.rels', data: wbRels},
    {name: 'xl/styles.xml', data: styles}
  ].concat(sheetFiles));
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
function say(text, bad) {
  const p = document.querySelector('[data-status]');
  p.textContent = text;
  p.style.color = bad ? '#b4442f' : '#4d795f';
}

const actions = {
  png: () => pngBlob().then(b => downloadBlob(b, DATA.company + '_双重重要性矩阵.png')),
  xlsx: () => downloadBlob(xlsxBlob(), DATA.company + '_议题得分明细.xlsx'),
  snapshot: () => downloadBlob(
    new Blob([JSON.stringify(buildSnapshot(), null, 2)], {type: 'application/json;charset=utf-8'}),
    DATA.company + '_审核快照.json'),
  reset: () => {
    if (!confirm('恢复到计分结果（清空所有调整与说明）？')) return;
    state.topics.forEach(t => { t.impact = t.origImpact; t.finance = t.origFinance; t.note = ''; });
    state.thresholds = {impact: DATA.thresholds.impact, financial: DATA.thresholds.financial};
    state.edits = {}; state.locked = false; state.lockedAt = '';
    event('恢复原始分');
    render();
  },
  commit: async (btn) => {
    if (!state.reviewer) {
      alert('请先在右侧「审核信息」填写审核人。');
      document.getElementById('reviewer').focus();
      return;
    }
    const missing = state.topics.filter(t => isChanged(t) && !t.note).length;
    if (missing && !confirm('还有 ' + missing + ' 项改分没写调整理由，仍要确认？')) return;
    btn.disabled = true;
    state.locked = true;
    state.lockedAt = now();
    event('定稿（审核人：' + state.reviewer + '）');
    say('正在生成文件并写回项目…');
    try {
      const xlsx = await xlsxBlob();
      const png = await pngBlob();
      const payload = {
        kind: 'review',
        review: buildSnapshot(),
        files: [
          {name: DATA.company + '_议题得分明细.xlsx', data: await blobToBase64(xlsx)},
          {name: DATA.company + '_双重重要性矩阵.png', data: await blobToBase64(png)}
        ]
      };
      const r = await fetch('/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || '写回失败');
      say('已定稿并写回 ' + j.saved.length + ' 个文件（' + j.saved.map(p => p.split('/').pop()).join('、') + '），可以回到对话继续。');
      save();
    } catch (e) {
      downloadBlob(await xlsxBlob(), DATA.company + '_议题得分明细.xlsx');
      say('未连上本地服务，已改为下载 Excel；矩阵图片请用「导出矩阵图片」。', true);
      btn.disabled = false;
    }
  }
};

(async function checkMode() {
  try {
    const r = await fetch('/api/ping');
    const j = await r.json();
    if (j.ok) return;
  } catch (e) {}
  const p = document.querySelector('[data-status]');
  if (p) { p.textContent = '当前是离线打开：确认后只能下载文件，需手动放回项目目录。用 dm_server.py 打开可免去这一步。'; }
})();

load();
render();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="生成审核与调分页面")
    ap.add_argument("--project", required=True)
    ap.add_argument("--scores", help="scores.json 路径，默认项目目录下")
    ap.add_argument("--out", help="输出 HTML 路径")
    ap.add_argument("--brand", default="on", help="品牌与引流元素：on（默认）/ off，off 时页头链接、页脚署名、矩阵图与 Excel 来源行全部不带")
    ap.add_argument("--qr", default=None, help="可选：本地二维码图片路径，内嵌到页脚（png/jpg/svg）")
    args = ap.parse_args()

    from datetime import datetime

    path = Path(args.project)
    workdir = path if path.is_dir() else path.parent
    project = load_project(path)
    scores_path = Path(args.scores) if args.scores else workdir / "scores.json"
    if not scores_path.exists():
        raise SystemExit(f"找不到 {scores_path}；先跑 dm_score.py 计分")

    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    scores["year"] = scores.get("year") or project.get("year") or ""
    ni = scores["meta"]["impact"]["kept"]
    nf = scores["meta"]["finance"]["kept"]

    css_path = Path(__file__).resolve().parent.parent / "assets" / "materiality.css"
    css = css_path.read_text(encoding="utf-8")

    html = (
        TPL.replace("__TITLE__", f"{scores['company']} · 双重重要性审核")
        .replace("__CSS__", css)
        .replace("__DATA__", json.dumps(scores, ensure_ascii=False))
        .replace("__BRAND__", json.dumps(brand_payload(args.brand, args.qr), ensure_ascii=False))
        .replace("__STAMP__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )

    out = Path(args.out) if args.out else workdir / f"03_审核-{scores['company']}.html"
    out.write_text(html, encoding="utf-8")
    project["stage"] = "reviewed"
    save_project(project, workdir)
    print(f"ok {out} {out.stat().st_size / 1024:.1f} KB｜议题 {len(scores['topics'])} 项｜影响 {ni} 份｜财务 {nf} 份")


if __name__ == "__main__":
    main()
