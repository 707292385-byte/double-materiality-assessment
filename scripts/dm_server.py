#!/usr/bin/env python3
"""本地工作台服务：让选题页 / 审核页直接把结果写回项目目录，用户不用导文件。

用法：
  python3 dm_server.py --project <项目目录> --page topic  [--port 8765]
  python3 dm_server.py --project <项目目录> --page review [--port 8765]

启动后用 present_files 打开 http://127.0.0.1:<port>/：
  · 选题页点「确认选题」→ 直接覆盖项目目录里的 project.json
  · 审核页点「确认并写回」→ 直接落盘 Excel（三表）、矩阵 PNG、审核快照 JSON，并更新 project.json
页面检测不到服务时自动降级为「导出文件」离线模式，不影响单文件使用。
"""
from __future__ import annotations

import argparse
import base64
import json
import socket
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dm_lib import load_project, normalize_topics, save_project  # noqa: E402

STATE = {"project_dir": Path("."), "html": Path("."), "saved": []}


def safe_name(name: str) -> str:
    keep = "-_()（）. "
    cleaned = "".join(c for c in name if c.isalnum() or c in keep or "\u4e00" <= c <= "\u9fff")
    return cleaned.strip() or "output"


class Handler(BaseHTTPRequestHandler):
    server_version = "dm-workbench/1.0"

    def log_message(self, fmt, *args):  # 静默访问日志
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            data = STATE["html"].read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/ping":
            self._json(200, {"ok": True, "service": "dm-workbench", "project": str(STATE["project_dir"]),
                             "saved": STATE["saved"]})
            return
        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/save":
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self._json(400, {"ok": False, "error": f"请求体解析失败：{exc}"})
            return

        kind = payload.get("kind")
        project_dir: Path = STATE["project_dir"]
        saved = []
        try:
            project = load_project(project_dir)
            if kind == "topics":
                incoming = payload.get("project") or {}
                project["company"] = incoming.get("company") or project["company"]
                project["industry"] = incoming.get("industry") or project["industry"]
                project["platform"] = incoming.get("platform") or project["platform"]
                project["topics"] = normalize_topics(incoming.get("topics") or [])
                project["stage"] = "topics"
                saved.append(str(save_project(project, project_dir)))

            elif kind == "review":
                review = payload.get("review") or {}
                stamp = datetime.now().strftime("%Y%m%d")
                for f in payload.get("files") or []:
                    name = safe_name(f.get("name") or "output")
                    raw = base64.b64decode(f.get("data") or "")
                    target = project_dir / name
                    target.write_bytes(raw)
                    saved.append(str(target))
                review_path = project_dir / f"review-{stamp}.json"
                review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
                saved.append(str(review_path))
                project["stage"] = "reviewed"
                if review.get("thresholds"):
                    project["thresholds"] = review["thresholds"]
                saved.append(str(save_project(project, project_dir)))
            else:
                self._json(400, {"ok": False, "error": f"未知的 kind：{kind}"})
                return
        except SystemExit as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            self._json(500, {"ok": False, "error": f"写盘失败：{exc}"})
            return

        STATE["saved"] = saved
        self._json(200, {"ok": True, "saved": saved, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


def pick_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("8765-8784 端口都被占用，请用 --port 指定其他端口")


def main():
    ap = argparse.ArgumentParser(description="双重重要性评估本地工作台")
    ap.add_argument("--project", required=True)
    ap.add_argument("--page", required=True, choices=["topic", "review"], help="要打开的页面")
    ap.add_argument("--file", help="指定 HTML 文件；默认按 page 在项目目录里找")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    project_dir = Path(args.project)
    if project_dir.is_file():
        project_dir = project_dir.parent
    STATE["project_dir"] = project_dir

    if args.file:
        html = Path(args.file)
    else:
        pattern = "01_选题-*.html" if args.page == "topic" else "03_审核-*.html"
        matches = sorted(project_dir.glob(pattern))
        if not matches:
            raise SystemExit(f"项目目录里找不到 {pattern}，先生成页面")
        html = matches[-1]
    if not html.exists():
        raise SystemExit(f"页面不存在：{html}")
    STATE["html"] = html

    port = pick_port(args.port)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"READY http://127.0.0.1:{port}/")
    print(f"页面 {html.name}｜项目 {project_dir}｜Ctrl+C 结束")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
