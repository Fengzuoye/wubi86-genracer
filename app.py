# -*- coding: utf-8 -*-
"""86 版五笔跟打器（本地运行）

功能：
  1. 自动抓取人民日报电子版（paper.people.com.cn）最近一期评论/文章；
  2. 用 86 版五笔码表（含一、二级简码）给文章逐字标注输入码；
  3. 前端提供一个输入框，用本机五笔输入法跟打，并实时统计速度/正确率。

运行：python app.py  （自动打开浏览器 http://127.0.0.1:8765）
"""

import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PAPER_BASE = "http://paper.people.com.cn"
PAPER_PATH = PAPER_BASE + "/rmrb/pc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

CODE_MAP = json.loads((DATA_DIR / "wubi86.json").read_text(encoding="utf-8"))
CODE_VERSION = 3  # 1=只有一二级简码；3=加入三级简码


# ---------------------------------------------------------------- 基础工具

def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def clean_html_fragment(frag: str) -> str:
    frag = re.sub(r"<[^>]+>", "", frag)
    frag = html.unescape(frag)
    frag = re.sub(r"[\s\u3000]+", "", frag)
    return frag.strip()


def layout_url(d: date, page_no: int) -> str:
    ymd = f"{d.year:04d}{d.month:02d}"
    return (f"{PAPER_PATH}/layout/{ymd}/{d.day:02d}/"
            f"node_{page_no:02d}.html")


def content_url(d: date, article_id: str) -> str:
    ymd = f"{d.year:04d}{d.month:02d}"
    return (f"{PAPER_PATH}/content/{ymd}/{d.day:02d}/"
            f"content_{article_id}.html")


def parse_date(s: str) -> date:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", (s or "").strip())
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    return date.today()


# ------------------------------------------------------------ 版面与文章抓取

def node_page(d: date, page_no: int):
    """抓一个版面页，返回 (页码, 版名, [文章])；404 返回 None。"""
    try:
        text = fetch(layout_url(d, page_no))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        raise
    if "news-list" not in text:
        return None
    sec_m = re.search(r"第\d+版[:：]\s*([^<\s]+)", text)
    section = clean_html_fragment(sec_m.group(1)) if sec_m else ""
    arts = []
    seen = set()
    for m in re.finditer(
            r'<a[^>]+href="([^"]*content_(\d+)\.html)"[^>]*>(.*?)</a>',
            text, re.S):
        aid = m.group(2)
        title = clean_html_fragment(m.group(3))
        if not aid or not title or aid in seen:
            continue
        if title in ("导读", "PDF下载", "版面导航", "人民日报"):
            continue
        seen.add(aid)
        arts.append({
            "id": aid,
            "title": title,
            "section": section,
            "page": page_no,
            "url": content_url(d, aid),
        })
    return page_no, section, arts


def get_edition(d: date, back_days: int = 7):
    """找最近一期（含当天）的版面清单。"""
    dates = [d - timedelta(days=offset) for offset in range(back_days + 1)]

    # 1) 先看本地是否已有这一天的版面缓存（当天内容固定不变，缓存永久有效）
    for cur in dates:
        cp = CACHE_DIR / ("edition_%s.json" % cur.isoformat())
        if cp.exists():
            try:
                return json.loads(cp.read_text(encoding="utf-8"))
            except Exception:
                pass

    # 2) 并行探测哪一天有报（最多一次发 8 个请求，取最近的一天）
    def probe(cur):
        try:
            return cur, node_page(cur, 1) is not None
        except Exception:
            return cur, False

    hits = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(probe, cur) for cur in dates]
        for fut in futures:
            cur, ok = fut.result()
            if ok:
                hits.append(cur)
    if not hits:
        raise RuntimeError("连续 %d 天都抓不到人民日报版面，请检查网络。" % back_days)
    cur = hits[0]  # dates 列表按“由近到远”排列，hits 同序
    offset = (d - cur).days

    # 3) 并行抓当天全部版面
    items = []
    pages = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(node_page, cur, page_no) for page_no in range(1, 31)]
        for fut in futures:
            try:
                page = fut.result()
            except Exception:
                page = None
            if page is None:
                continue
            pages.append(page)
            if page[1] == "广告":
                continue
            items.extend(page[2])

    # 版面中同一条目可能跨版重复，去重
    uniq, seen = [], set()
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    result = {
        "date": cur.isoformat(),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][cur.weekday()],
        "back": offset,
        "pages": [{"no": p[0], "section": p[1]} for p in pages],
        "items": uniq,
    }
    save_cache(CACHE_DIR / ("edition_%s.json" % cur.isoformat()), result)
    return result


def parse_article(d: date, article_id: str) -> dict:
    url = content_url(d, article_id)
    text = fetch(url)
    title = ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
    if m:
        title = clean_html_fragment(m.group(1))
    if not title:
        m = re.search(r"<title>(.*?)</title>", text, re.S)
        if m:
            title = clean_html_fragment(m.group(1))
    author, subtitle = "", ""
    prop = re.search(r"<!--enpproperty\s*(.*?)\s*/enpproperty-->", text, re.S)
    if prop:
        block = prop.group(1)
        am = re.search(r"<author>(.*?)</author>", block, re.S)
        sm = re.search(r"<subtitle>(.*?)</subtitle>", block, re.S)
        if am:
            author = clean_html_fragment(am.group(1))
        if sm:
            subtitle = clean_html_fragment(sm.group(1))
    body = ""
    bm = re.search(r"<!--enpcontent-->(.*?)<!--/enpcontent-->", text, re.S)
    if bm:
        body = bm.group(1)
    paras = []
    if body:
        for pm in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.S):
            t = clean_html_fragment(pm.group(1))
            if t:
                paras.append(t)
    return {
        "date": d.isoformat(),
        "id": article_id,
        "url": url,
        "title": title,
        "subtitle": subtitle,
        "author": author,
    }, paras


def annotate_paragraphs(paras):
    """逐字标注：s=按主流输入法应打的简码/全码, f=全码, l=1/2/0(简码级/全码)。"""
    paragraphs = []
    total_chars = 0
    total_hanzi = 0
    missing = set()
    for para in paras:
        units = []
        for ch in para:
            info = CODE_MAP.get(ch)
            total_chars += 1
            if info:
                if re.match(r"[\u4e00-\u9fff]", ch):
                    total_hanzi += 1
                units.append({"ch": ch, "s": info["c"], "f": info["f"], "l": info["l"]})
            else:
                if re.match(r"[\u4e00-\u9fff]", ch):
                    missing.add(ch)
                units.append({"ch": ch, "s": None, "f": None, "l": -1})
        paragraphs.append({"units": units})
    return paragraphs, total_chars, total_hanzi, sorted(missing)


def build_lesson(d: date, article_id: str) -> dict:
    info, paras = parse_article(d, article_id)
    paragraphs, total_chars, total_hanzi, missing = annotate_paragraphs(paras)
    lesson = {
        "codeVersion": CODE_VERSION,
        "meta": {
            "title": info["title"],
            "subtitle": info["subtitle"],
            "author": info["author"],
            "date": info["date"],
            "url": info["url"],
        },
        "paragraphs": paragraphs,
        "stats": {
            "chars": total_chars,
            "hanzi": total_hanzi,
            "missing": missing,
        },
    }
    return lesson


# ------------------------------------------------------------------ 缓存

def cache_key(d: date, aid: str) -> Path:
    return CACHE_DIR / ("%s_%s.json" % (d.isoformat(), aid))


def save_cache(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def latest_cache() -> dict | None:
    files = [p for p in CACHE_DIR.glob("*.json") if not p.name.endswith(".tmp")]
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        return json.loads(newest.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------- HTTP 服务

class Handler(BaseHTTPRequestHandler):
    server_version = "Wubi86Genracer/1.0"

    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, path: Path, content_type: str):
        if not path.is_file() or ROOT not in path.resolve().parents:
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                self.serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            elif path.startswith("/static/"):
                rel = path[len("/static/"):]
                ctype = {
                    ".css": "text/css; charset=utf-8",
                    ".js": "application/javascript; charset=utf-8",
                    ".html": "text/html; charset=utf-8",
                    ".png": "image/png",
                    ".svg": "image/svg+xml",
                }.get(Path(rel).suffix.lower(), "application/octet-stream")
                self.serve_file(STATIC_DIR / rel, ctype)
            elif path == "/data/jianma.json":
                self.serve_file(DATA_DIR / "jianma.json",
                                "application/json; charset=utf-8")
            elif path == "/api/editions":
                d = parse_date((qs.get("date") or [""])[0])
                self.send_json({"ok": True, "edition": get_edition(d)})
            elif path == "/api/article":
                d = parse_date((qs.get("date") or [""])[0])
                aid = (qs.get("id") or [""])[0].strip()
                if not aid:
                    self.send_json({"ok": False, "error": "缺少文章 id"}, 400)
                    return
                key = cache_key(d, aid)
                force = (qs.get("refresh") or [""])[0] == "1"
                if not force and key.exists():
                    try:
                        lesson = json.loads(key.read_text(encoding="utf-8"))
                        if lesson.get("codeVersion") == CODE_VERSION:
                            self.send_json({"ok": True, "article": lesson, "cached": True})
                            return
                    except Exception:
                        pass
                try:
                    lesson = build_lesson(d, aid)
                    save_cache(key, lesson)
                    self.send_json({"ok": True, "article": lesson, "cached": False})
                except Exception as exc:
                    cached = None
                    if key.exists():
                        try:
                            cached = json.loads(key.read_text(encoding="utf-8"))
                            if cached.get("codeVersion") != CODE_VERSION:
                                cached = None
                        except Exception:
                            cached = None
                    if cached:
                        self.send_json({"ok": True, "article": cached, "cached": True,
                                        "warning": "在线抓取失败，已使用本地缓存。"})
                    else:
                        self.send_json({"ok": False, "error": str(exc)}, 502)
            elif path == "/api/latest":
                cached = latest_cache()
                if cached:
                    self.send_json({"ok": True, "article": cached, "cached": True})
                else:
                    self.send_json({"ok": False, "error": "暂无缓存"}, 404)
            else:
                self.send_error(404, "Not Found")
        except BrokenPipeError:
            pass
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, 500)


class Server(ThreadingHTTPServer):
    # Windows 上默认的 SO_REUSEADDR 会允许两个实例绑同一端口，
    # 造成“请求打到旧实例”之类的怪问题，这里显式关掉。
    allow_reuse_address = False
    daemon_threads = True


def start_server(port_start: int = 8765):
    port = port_start
    while port < port_start + 20:
        try:
            httpd = Server(("127.0.0.1", port), Handler)
            return httpd, port
        except OSError:
            port += 1
    raise RuntimeError("没有可用端口")


def main():
    httpd, port = start_server()
    print("86 五笔跟打器已启动: http://127.0.0.1:%d" % port, flush=True)
    print("浏览器将自动打开；若未打开请手动访问上面的网址", flush=True)
    print("按 Ctrl+C 退出", flush=True)
    threading.Timer(0.8, lambda: webbrowser.open("http://127.0.0.1:%d" % port)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
