"""Campus-Safe Full-Text Paper Downloader Dashboard with Auto-Capture & Companion Reader

Features:
1. Auto-Capture from Downloads folder:
   - Watches C:/Users/<User>/Downloads for new PDF downloads.
   - Automatically intercepts new PDFs, validates the %PDF- header,
     renames them to <paper_id>.pdf, moves them to D:/new papers/papers/core/,
     and marks them as downloaded in download_list.csv.
   - Automatically advances to the next remaining paper!
2. Dedicated Companion Reader Window (window.open):
   - Opens the paper's DOI in a dedicated compact browser window.
   - Works natively with your campus network session and passes Elsevier/IEEE CAPTCHAs.
   - Automatically navigates to the next paper URL when the current one is downloaded.
3. Split-Screen Dashboard:
   - Left: Search, Filter (Remaining, Priority, Publisher), and list of papers.
   - Right: Active paper control panel, metadata, embedded frame / companion window trigger, and capture history.
"""

import csv
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request, send_file, abort

# Paths
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "download_list.csv"
DEST_DIR = BASE_DIR.parent.parent.parent / "papers" / "core"
if not DEST_DIR.exists():
    DEST_DIR = Path(r"D:\new papers\papers\core")

# Downloads directory to watch
DOWNLOADS_DIR = Path.home() / "Downloads"

csv_lock = threading.Lock()
state_lock = threading.Lock()

# App State
state = {
    "active_paper_id": None,
    "active_timestamp": time.time(),
    "auto_capture_enabled": True,
    "downloads_dir": str(DOWNLOADS_DIR),
    "recent_events": [],
    "last_event_id": 0
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


def classify_publisher(doi: str, venue: str, oa: str) -> str:
    doi_l = (doi or "").lower()
    venue_l = (venue or "").lower()
    oa_l = (oa or "").lower()

    if "10.1016/" in doi_l or "sciencedirect" in oa_l or "comnet" in doi_l or "elsevier" in venue_l:
        return "Elsevier"
    if "10.1109/" in doi_l or "ieee" in doi_l or "ieee" in venue_l or "ielx7" in oa_l:
        return "IEEE"
    if "10.1145/" in doi_l or "acm.org" in oa_l or "acm" in venue_l:
        return "ACM"
    if "10.1007/" in doi_l or "10.1186/" in doi_l or "10.1140/" in doi_l or "springer" in oa_l or "springer" in venue_l:
        return "Springer"
    if "10.1371/" in doi_l or "plos" in venue_l or "plos" in oa_l:
        return "PLOS"
    if "10.1038/" in doi_l or "nature" in venue_l:
        return "Nature"
    if "10.3390/" in doi_l or "mdpi" in venue_l:
        return "MDPI"
    if "frontiersin" in oa_l or "10.3389/" in doi_l:
        return "Frontiers"
    if "arxiv" in oa_l or "arxiv" in doi_l:
        return "arXiv"
    if "hal.science" in oa_l:
        return "HAL"
    return "Other"


def read_csv_data():
    with csv_lock:
        if not CSV_PATH.exists():
            return []
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return list(reader)


def write_csv_data(rows):
    with csv_lock:
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        temp_path = CSV_PATH.with_suffix(".tmp")
        with open(temp_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        temp_path.replace(CSV_PATH)


def check_pdf_file(paper_id: str):
    """Check if valid PDF exists in DEST_DIR."""
    pdf_path = DEST_DIR / f"{paper_id}.pdf"
    if pdf_path.exists() and pdf_path.is_file():
        try:
            size = pdf_path.stat().st_size
            if size > 1000:
                with open(pdf_path, "rb") as f:
                    head = f.read(5)
                if head == b"%PDF-":
                    return True, size, pdf_path
        except Exception:
            pass
    return False, 0, None


def get_next_remaining_paper(current_id=None):
    rows = read_csv_data()
    rows.sort(key=lambda r: (int(r.get("priority", 9)), r.get("id", "")))
    found_current = False if current_id else True
    fallback = None

    for r in rows:
        pid = r["id"]
        is_done, _, _ = check_pdf_file(pid)
        is_done = is_done or (r.get("downloaded") or "").strip().lower() == "yes"
        if not is_done:
            if fallback is None:
                fallback = pid
            if found_current:
                return pid
        if pid == current_id:
            found_current = True

    return fallback


def sync_all_from_disk():
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_csv_data()
    updated = False
    newly_detected = 0

    for r in rows:
        pid = r["id"]
        is_pdf, size, _ = check_pdf_file(pid)
        curr_downloaded = (r.get("downloaded") or "").strip().lower() == "yes"

        if is_pdf and not curr_downloaded:
            r["downloaded"] = "yes"
            if not r.get("note"):
                r["note"] = f"detected on disk ({size // 1024} KB)"
            updated = True
            newly_detected += 1

    if updated:
        write_csv_data(rows)
    return newly_detected


def wait_for_file_ready(path: Path, timeout=12):
    """Wait until a downloading file is fully written and unlocked."""
    start = time.time()
    last_size = -1
    stable_count = 0

    while time.time() - start < timeout:
        if not path.exists():
            time.sleep(0.3)
            continue
        try:
            sz = path.stat().st_size
            if sz > 1000:
                if sz == last_size:
                    stable_count += 1
                else:
                    stable_count = 0
                last_size = sz

                if stable_count >= 2:
                    with open(path, "rb") as f:
                        head = f.read(5)
                    if head == b"%PDF-":
                        return True
        except (PermissionError, OSError):
            pass
        time.sleep(0.4)
    return False


def watch_downloads_folder():
    """Background thread watching Downloads folder for newly completed PDFs."""
    while True:
        try:
            time.sleep(0.7)
            with state_lock:
                enabled = state["auto_capture_enabled"]
                active_id = state["active_paper_id"]
                active_ts = state["active_timestamp"]
                watch_dir = Path(state["downloads_dir"])

            if not enabled or not active_id or not watch_dir.exists():
                continue

            # Check if active paper is already downloaded
            is_pdf, _, _ = check_pdf_file(active_id)
            if is_pdf:
                continue

            candidates = []
            for item in watch_dir.glob("*.pdf"):
                try:
                    mtime = item.stat().st_mtime
                    if mtime >= (active_ts - 2.5):
                        candidates.append((item, mtime))
                except Exception:
                    pass

            if not candidates:
                continue

            candidates.sort(key=lambda x: x[1], reverse=True)
            candidate, _ = candidates[0]

            if not wait_for_file_ready(candidate):
                continue

            DEST_DIR.mkdir(parents=True, exist_ok=True)
            target = DEST_DIR / f"{active_id}.pdf"
            file_size = candidate.stat().st_size
            size_kb = file_size // 1024
            orig_name = candidate.name

            shutil.move(str(candidate), str(target))

            rows = read_csv_data()
            for r in rows:
                if r["id"] == active_id:
                    r["downloaded"] = "yes"
                    r["note"] = f"auto-captured: {orig_name} ({size_kb} KB)"
                    break
            write_csv_data(rows)

            next_id = get_next_remaining_paper(active_id)
            with state_lock:
                state["last_event_id"] += 1
                ev = {
                    "event_id": state["last_event_id"],
                    "captured_id": active_id,
                    "filename": orig_name,
                    "size_kb": size_kb,
                    "target": f"{active_id}.pdf",
                    "time": time.strftime("%H:%M:%S"),
                    "next_id": next_id
                }
                state["recent_events"].insert(0, ev)
                state["recent_events"] = state["recent_events"][:15]

                if next_id and next_id != active_id:
                    state["active_paper_id"] = next_id
                    state["active_timestamp"] = time.time()

        except Exception as e:
            time.sleep(1)


watcher_thread = threading.Thread(target=watch_downloads_folder, daemon=True)
watcher_thread.start()


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/papers")
def get_papers():
    sync_all_from_disk()
    rows = read_csv_data()
    papers = []
    stats = {
        "total": len(rows),
        "downloaded": 0,
        "remaining": 0,
        "by_priority": {"1": {"total": 0, "done": 0}, "2": {"total": 0, "done": 0}, "3": {"total": 0, "done": 0}},
        "by_publisher": {}
    }

    with state_lock:
        if state["active_paper_id"] is None:
            state["active_paper_id"] = get_next_remaining_paper()
        active_id = state["active_paper_id"]
        auto_cap = state["auto_capture_enabled"]
        watch_dir = state["downloads_dir"]
        events = list(state["recent_events"])
        last_ev_id = state["last_event_id"]

    for r in rows:
        pid = r["id"]
        is_pdf, size, _ = check_pdf_file(pid)
        downloaded = (r.get("downloaded") or "").strip().lower() == "yes" or is_pdf
        prio = str(r.get("priority", "1"))
        pub = classify_publisher(r.get("doi_link", ""), r.get("venue", ""), r.get("open_access_link", ""))

        if prio not in stats["by_priority"]:
            stats["by_priority"][prio] = {"total": 0, "done": 0}
        stats["by_priority"][prio]["total"] += 1

        if pub not in stats["by_publisher"]:
            stats["by_publisher"][pub] = {"total": 0, "done": 0}
        stats["by_publisher"][pub]["total"] += 1

        if downloaded:
            stats["downloaded"] += 1
            stats["by_priority"][prio]["done"] += 1
            stats["by_publisher"][pub]["done"] += 1
        else:
            stats["remaining"] += 1

        papers.append({
            "id": pid,
            "priority": prio,
            "publisher": pub,
            "title": r.get("title", ""),
            "venue": r.get("venue", ""),
            "year": r.get("year", ""),
            "cited_by": r.get("cited_by", "0"),
            "doi_link": r.get("doi_link", ""),
            "open_access_link": r.get("open_access_link", ""),
            "recheck_flag": r.get("recheck_flag", ""),
            "downloaded": downloaded,
            "size_kb": (size // 1024) if is_pdf else 0,
            "note": r.get("note", ""),
            "filename": f"{pid}.pdf"
        })

    return jsonify({
        "stats": stats,
        "papers": papers,
        "active_paper_id": active_id,
        "auto_capture_enabled": auto_cap,
        "downloads_dir": watch_dir,
        "recent_events": events,
        "last_event_id": last_ev_id
    })


@app.route("/api/poll")
def poll_state():
    since_id = request.args.get("since", 0, type=int)
    with state_lock:
        active_id = state["active_paper_id"]
        new_events = [e for e in state["recent_events"] if e["event_id"] > since_id]
        last_ev_id = state["last_event_id"]
        auto_cap = state["auto_capture_enabled"]

    return jsonify({
        "active_paper_id": active_id,
        "new_events": new_events,
        "last_event_id": last_ev_id,
        "auto_capture_enabled": auto_cap
    })


@app.route("/api/set_active/<paper_id>", methods=["POST"])
def set_active(paper_id):
    with state_lock:
        state["active_paper_id"] = paper_id
        state["active_timestamp"] = time.time()
    return jsonify({"success": True, "active_paper_id": paper_id})


@app.route("/api/toggle_auto_capture", methods=["POST"])
def toggle_auto_capture():
    with state_lock:
        state["auto_capture_enabled"] = not state["auto_capture_enabled"]
        current = state["auto_capture_enabled"]
        state["active_timestamp"] = time.time()
    return jsonify({"success": True, "auto_capture_enabled": current})


@app.route("/api/sync", methods=["POST"])
def sync_endpoint():
    newly = sync_all_from_disk()
    return jsonify({"success": True, "newly_detected": newly})


@app.route("/api/upload/<paper_id>", methods=["POST"])
def upload_paper(paper_id):
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Empty filename"}), 400

    data = file.read()
    if not data.startswith(b"%PDF-"):
        head_sample = data[:50].decode("utf-8", errors="ignore")
        return jsonify({
            "success": False,
            "error": f"File is not a valid PDF! Starts with: {head_sample}"
        }), 400

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    target_path = DEST_DIR / f"{paper_id}.pdf"
    target_path.write_bytes(data)

    rows = read_csv_data()
    size_kb = len(data) // 1024
    for r in rows:
        if r["id"] == paper_id:
            r["downloaded"] = "yes"
            r["note"] = f"manual upload ({size_kb} KB)"
            break
    write_csv_data(rows)

    next_id = get_next_remaining_paper(paper_id)
    with state_lock:
        state["last_event_id"] += 1
        state["recent_events"].insert(0, {
            "event_id": state["last_event_id"],
            "captured_id": paper_id,
            "filename": file.filename,
            "size_kb": size_kb,
            "target": f"{paper_id}.pdf",
            "time": time.strftime("%H:%M:%S"),
            "next_id": next_id
        })
        if next_id and next_id != paper_id:
            state["active_paper_id"] = next_id
            state["active_timestamp"] = time.time()

    return jsonify({"success": True, "size_kb": size_kb, "next_id": next_id})


@app.route("/api/pdf/<paper_id>")
def view_pdf(paper_id):
    pdf_path = DEST_DIR / f"{paper_id}.pdf"
    if not pdf_path.exists():
        abort(404, description="PDF not found")
    return send_file(pdf_path, mimetype="application/pdf", as_attachment=False)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Literature Review Paper Downloader</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #131b2e;
      --card-border: #1e293b;
      --card-border-active: #38bdf8;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --primary-hover: #0284c7;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --elsevier: #ea580c;
      --ieee: #2563eb;
      --springer: #059669;
      --acm: #0891b2;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.4;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    header {
      background: #0f172a;
      border-bottom: 1px solid var(--card-border);
      padding: 10px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      z-index: 10;
    }
    .brand h1 {
      font-size: 1.15rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .brand p { font-size: 0.75rem; color: var(--text-muted); }

    .header-center {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .progress-box { width: 180px; }
    .progress-bar-bg {
      background: #1e293b;
      border-radius: 999px;
      height: 8px;
      overflow: hidden;
    }
    .progress-bar-fill {
      background: linear-gradient(90deg, #38bdf8, #10b981);
      height: 100%;
      width: 0%;
      transition: width 0.3s ease;
    }
    .progress-label {
      font-size: 0.7rem;
      display: flex;
      justify-content: space-between;
      margin-top: 3px;
      color: var(--text-muted);
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .auto-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      background: #064e3b;
      border: 1px solid #059669;
      color: #a7f3d0;
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #34d399;
      box-shadow: 0 0 8px #34d399;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 0.7; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(0.9); opacity: 0.7; }
    }

    .btn {
      background: #1e293b;
      color: #fff;
      border: 1px solid var(--card-border);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s;
      text-decoration: none;
    }
    .btn:hover { background: #334155; }
    .btn.primary { background: #0284c7; border-color: #0284c7; font-weight: 600; }
    .btn.primary:hover { background: #0369a1; }
    .btn.success { background: #059669; border-color: #059669; }
    .btn.success:hover { background: #047857; }

    .app-body {
      flex: 1;
      display: flex;
      overflow: hidden;
    }

    .list-pane {
      width: 500px;
      border-right: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      background: #0b1120;
    }
    .list-controls {
      padding: 12px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .search-input {
      width: 100%;
      padding: 7px 10px;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      background: var(--card-bg);
      color: #fff;
      font-size: 0.85rem;
      outline: none;
    }
    .filter-row {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }
    .chip {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.72rem;
      cursor: pointer;
    }
    .chip.active {
      background: var(--primary);
      color: #0f172a;
      font-weight: 600;
      border-color: var(--primary);
    }

    .papers-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .paper-item {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 10px 12px;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      flex-direction: column;
      gap: 4px;
      position: relative;
    }
    .paper-item:hover {
      border-color: #475569;
      transform: translateX(2px);
    }
    .paper-item.active {
      border-color: var(--primary);
      box-shadow: 0 0 0 1px var(--primary);
      background: #172554;
    }
    .paper-item.is-done {
      border-left: 3px solid var(--success);
      opacity: 0.85;
    }
    .paper-item.is-pending {
      border-left: 3px solid var(--warning);
    }
    .item-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .item-id {
      font-family: monospace;
      font-weight: 700;
      font-size: 0.95rem;
      color: var(--primary);
    }
    .item-title {
      font-size: 0.82rem;
      font-weight: 600;
      line-height: 1.3;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .item-meta {
      font-size: 0.72rem;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
    }

    .badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-p1 { background: #7f1d1d; color: #fca5a5; }
    .badge-p2 { background: #78350f; color: #fde68a; }
    .badge-p3 { background: #1e3a8a; color: #bfdbfe; }
    .badge-elsevier { background: #9a3412; color: #ffedd5; }
    .badge-ieee { background: #1e40af; color: #dbeafe; }
    .badge-springer { background: #065f46; color: #d1fae5; }
    .badge-acm { background: #155e75; color: #cffafe; }
    .badge-oa { background: #374151; color: #e5e7eb; }

    .detail-pane {
      flex: 1;
      display: flex;
      flex-direction: column;
      background: var(--bg);
      overflow: hidden;
    }
    .active-bar {
      background: #111827;
      border-bottom: 1px solid var(--card-border);
      padding: 12px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .active-title-group h2 {
      font-size: 1.05rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .active-title-group p {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .active-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .workspace-area {
      flex: 1;
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
    }
    .frame-banner {
      background: #1e1b4b;
      border-bottom: 1px solid #3730a3;
      padding: 8px 16px;
      font-size: 0.78rem;
      color: #c7d2fe;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .frame-container {
      flex: 1;
      position: relative;
      background: #0f172a;
    }
    iframe {
      width: 100%;
      height: 100%;
      border: none;
      background: #ffffff;
    }

    .frame-overlay {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.95);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
      text-align: center;
      gap: 16px;
      z-index: 5;
    }
    .overlay-card {
      max-width: 650px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .overlay-card h3 { font-size: 1.1rem; margin-bottom: 10px; }
    .overlay-card p { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px; }

    .capture-footer {
      height: 52px;
      background: #0f172a;
      border-top: 1px solid var(--card-border);
      padding: 8px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.78rem;
    }
    .event-ticker {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #a7f3d0;
      font-family: monospace;
    }

    #toast {
      position: fixed;
      bottom: 70px;
      right: 24px;
      background: #1e293b;
      border: 1px solid var(--primary);
      color: #fff;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 0.85rem;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      z-index: 1000;
      opacity: 0;
      transform: translateY(15px);
      transition: all 0.25s ease;
      pointer-events: none;
    }
    #toast.show { opacity: 1; transform: translateY(0); }
    #toast.success { background: #064e3b; border-color: var(--success); color: #a7f3d0; }
    #toast.error { background: #450a0a; border-color: var(--danger); color: #fecaca; }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <h1>TLS-SoK Core Paper Downloader</h1>
      <p>Watching: <code id="watchPath">Downloads</code> &rarr; Auto-saving to: <code>papers/core/&lt;id&gt;.pdf</code></p>
    </div>

    <div class="header-center">
      <div class="auto-badge" id="autoBadge" onclick="toggleAutoCapture()" title="Click to toggle auto-intercepting PDFs">
        <span class="pulse-dot"></span>
        <span>Auto-Capture Active</span>
      </div>

      <div class="progress-box">
        <div class="progress-bar-bg">
          <div id="progFill" class="progress-bar-fill"></div>
        </div>
        <div class="progress-label">
          <span id="progCount">0 / 0</span>
          <span id="progPercent">0%</span>
        </div>
      </div>
    </div>

    <div class="header-actions">
      <button class="btn" onclick="syncFolder()" title="Rescan papers/core/">&#8635; Rescan</button>
      <button class="btn primary" onclick="launchCompanionWindow()" title="Open small dedicated window for Elsevier/IEEE">
        &#8599; Companion Window
      </button>
    </div>
  </header>

  <div class="app-body">
    <div class="list-pane">
      <div class="list-controls">
        <input type="text" id="searchInput" class="search-input" placeholder="Search ID, title, venue..." oninput="renderList()">
        
        <div class="filter-row">
          <span style="font-size:0.7rem; color:var(--text-muted); align-self:center;">Status:</span>
          <button class="chip active" data-filter="status" data-val="remaining" onclick="setFilter('status', 'remaining', this)">Remaining</button>
          <button class="chip" data-filter="status" data-val="all" onclick="setFilter('status', 'all', this)">All</button>
          <button class="chip" data-filter="status" data-val="downloaded" onclick="setFilter('status', 'downloaded', this)">Saved</button>
        </div>

        <div class="filter-row">
          <span style="font-size:0.7rem; color:var(--text-muted); align-self:center;">Prio:</span>
          <button class="chip active" data-filter="priority" data-val="all" onclick="setFilter('priority', 'all', this)">All</button>
          <button class="chip" data-filter="priority" data-val="1" onclick="setFilter('priority', '1', this)">P1</button>
          <button class="chip" data-filter="priority" data-val="2" onclick="setFilter('priority', '2', this)">P2</button>
          <button class="chip" data-filter="priority" data-val="3" onclick="setFilter('priority', '3', this)">P3</button>
          
          <span style="font-size:0.7rem; color:var(--text-muted); align-self:center; margin-left:6px;">Pub:</span>
          <button class="chip active" data-filter="publisher" data-val="all" onclick="setFilter('publisher', 'all', this)">All</button>
          <button class="chip" data-filter="publisher" data-val="Elsevier" onclick="setFilter('publisher', 'Elsevier', this)">Elsevier</button>
          <button class="chip" data-filter="publisher" data-val="IEEE" onclick="setFilter('publisher', 'IEEE', this)">IEEE</button>
        </div>
      </div>

      <div class="papers-scroll" id="papersScroll">
        <div style="text-align:center; padding: 20px; color:var(--text-muted);">Loading...</div>
      </div>
    </div>

    <div class="detail-pane">
      <div class="active-bar" id="activeBar">
        <div class="active-title-group">
          <h2>
            <span id="activeIdDisplay">S0000</span>
            <span id="activePubBadge" class="badge">Publisher</span>
            <span id="activePrioBadge" class="badge">P1</span>
          </h2>
          <p id="activeVenueDisplay">Venue & Year</p>
        </div>

        <div class="active-actions">
          <button class="btn" onclick="prevPaper()" title="Previous un-downloaded paper">&larr; Prev</button>
          <button class="btn" onclick="nextPaper()" title="Next un-downloaded paper">Next &rarr;</button>
          <button class="btn primary" onclick="launchCompanionWindow()" title="Open current paper in companion window">
            &#8599; Open Companion
          </button>
        </div>
      </div>

      <div class="workspace-area">
        <div class="frame-banner">
          <span>&#9889; <strong>Auto-Capture is ON:</strong> When you click "Download PDF" on the publisher site, this dashboard intercepts it and saves it as <code>papers/core/&lt;id&gt;.pdf</code> automatically!</span>
          <button class="btn" style="padding:2px 8px; font-size:0.72rem;" onclick="copyFilename()">&#128203; Copy Name</button>
        </div>

        <div class="frame-container" id="frameContainer">
          <div class="frame-overlay" id="frameOverlay">
            <div class="overlay-card">
              <span id="cardPubBadge" class="badge badge-elsevier" style="margin-bottom:8px;">Elsevier ScienceDirect</span>
              <h3 id="cardTitleDisplay">Title</h3>
              <p id="cardAbstractDisplay">Click below to open this paper in the dedicated <strong>Companion Window</strong>. When you click Download PDF on the publisher page, the PDF is automatically captured, renamed, and saved into your directory!</p>
              
              <div style="display:flex; justify-content:center; gap:10px; flex-wrap:wrap;">
                <button class="btn primary" style="padding:10px 20px; font-size:0.95rem;" onclick="launchCompanionWindow()">
                  &#8599; Open in Companion Window (Campus Authenticated)
                </button>
                <a id="cardDirectLink" href="#" target="_blank" class="btn" style="padding:10px 16px;">
                  Open in New Tab
                </a>
                <button class="btn" id="btnTryEmbed" onclick="toggleEmbedIframe()">
                  &#128065; Try Embedded Frame
                </button>
              </div>

              <div id="dropZoneOverlay" style="margin-top:20px; border:2px dashed #475569; border-radius:8px; padding:12px; font-size:0.8rem; color:var(--text-muted); cursor:pointer;"
                   onclick="triggerManualUpload()"
                   ondragover="onDragOver(event)" ondragleave="onDragLeave(event)" ondrop="onDrop(event)">
                <input type="file" id="manualFileInput" accept=".pdf" style="display:none;" onchange="onManualFileSelected(this)">
                <span>Or Drop downloaded PDF file here manually</span>
              </div>
            </div>
          </div>

          <iframe id="readerIframe" src="about:blank" style="display:none;"></iframe>
        </div>
      </div>

      <div class="capture-footer">
        <div class="event-ticker" id="eventTicker">
          <span>&#10003; Ready. Waiting for downloads...</span>
        </div>
        <div>
          <button class="btn" id="btnViewSaved" style="display:none;" onclick="viewSavedPdf()">&#128065; View Saved PDF</button>
        </div>
      </div>
    </div>
  </div>

  <div id="toast"></div>

  <script>
    let allPapers = [];
    let activePaper = null;
    let companionWindow = null;
    let lastEventId = 0;
    let showingEmbed = false;

    let filters = {
      status: 'remaining',
      priority: 'all',
      publisher: 'all',
      query: ''
    };

    function showToast(msg, type = 'info') {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.className = 'show ' + type;
      setTimeout(() => { t.className = ''; }, 3500);
    }

    async function loadAll() {
      try {
        const res = await fetch('/api/papers');
        const data = await res.json();
        allPapers = data.papers;
        lastEventId = data.last_event_id;

        document.getElementById('watchPath').innerText = data.downloads_dir;
        updateStats(data.stats);

        if (data.active_paper_id) {
          const found = allPapers.find(p => p.id === data.active_paper_id);
          if (found) selectPaper(found, false);
        } else if (allPapers.length > 0) {
          selectPaper(allPapers[0], false);
        }

        renderList();
      } catch (e) {
        showToast('Error connecting to backend', 'error');
      }
    }

    function updateStats(stats) {
      const done = stats.downloaded;
      const total = stats.total;
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;
      document.getElementById('progFill').style.width = pct + '%';
      document.getElementById('progCount').innerText = `${done} / ${total} Saved`;
      document.getElementById('progPercent').innerText = `${pct}%`;
    }

    function selectPaper(paper, updateServer = true) {
      activePaper = paper;

      document.getElementById('activeIdDisplay').innerText = paper.id;
      document.getElementById('activeVenueDisplay').innerText = `${paper.venue} (${paper.year}) • Cited: ${paper.cited_by}`;

      const pubBadge = document.getElementById('activePubBadge');
      pubBadge.innerText = paper.publisher;
      pubBadge.className = 'badge ' + getPubClass(paper.publisher);

      const prioBadge = document.getElementById('activePrioBadge');
      prioBadge.innerText = 'P' + paper.priority;
      prioBadge.className = 'badge badge-p' + paper.priority;

      document.getElementById('cardTitleDisplay').innerText = paper.title;
      document.getElementById('cardPubBadge').innerText = paper.publisher;
      document.getElementById('cardPubBadge').className = 'badge ' + getPubClass(paper.publisher);

      const link = paper.doi_link || paper.open_access_link;
      document.getElementById('cardDirectLink').href = link || '#';

      const btnView = document.getElementById('btnViewSaved');
      if (paper.downloaded) {
        btnView.style.display = 'inline-flex';
      } else {
        btnView.style.display = 'none';
      }

      if (companionWindow && !companionWindow.closed && link) {
        companionWindow.location.href = link;
      }

      if (showingEmbed && link) {
        document.getElementById('readerIframe').src = link;
      }

      document.querySelectorAll('.paper-item').forEach(el => {
        el.classList.toggle('active', el.id === 'item-' + paper.id);
      });

      if (updateServer) {
        fetch('/api/set_active/' + paper.id, { method: 'POST' });
      }
    }

    function launchCompanionWindow() {
      if (!activePaper) return;
      const url = activePaper.doi_link || activePaper.open_access_link;
      if (!url) return;

      const w = 960;
      const h = 880;
      const left = window.screen.width - w - 20;
      const top = 40;

      companionWindow = window.open(
        url,
        'TLS_Companion_Reader',
        `width=${w},height=${h},left=${left},top=${top},resizable=yes,scrollbars=yes`
      );
      showToast(`Opened Companion Window for ${activePaper.id}`, 'info');
    }

    function toggleEmbedIframe() {
      showingEmbed = !showingEmbed;
      const iframe = document.getElementById('readerIframe');
      const overlay = document.getElementById('frameOverlay');
      const btn = document.getElementById('btnTryEmbed');

      if (showingEmbed) {
        overlay.style.display = 'none';
        iframe.style.display = 'block';
        btn.innerText = '✕ Close Frame';
        if (activePaper) {
          iframe.src = activePaper.doi_link || activePaper.open_access_link;
        }
      } else {
        overlay.style.display = 'flex';
        iframe.style.display = 'none';
        btn.innerText = '👁 Try Embedded Frame';
        iframe.src = 'about:blank';
      }
    }

    function copyFilename() {
      if (!activePaper) return;
      navigator.clipboard.writeText(activePaper.filename).then(() => {
        showToast(`Copied: ${activePaper.filename}`, 'success');
      });
    }

    function viewSavedPdf() {
      if (!activePaper) return;
      window.open('/api/pdf/' + activePaper.id, '_blank');
    }

    function nextPaper() {
      const rem = allPapers.filter(p => !p.downloaded);
      if (rem.length === 0) {
        showToast('All papers downloaded!', 'success');
        return;
      }
      const idx = rem.findIndex(p => p.id === activePaper.id);
      const next = (idx >= 0 && idx + 1 < rem.length) ? rem[idx + 1] : rem[0];
      selectPaper(next);
      scrollToActive(next.id);
    }

    function prevPaper() {
      const rem = allPapers.filter(p => !p.downloaded);
      if (rem.length === 0) return;
      const idx = rem.findIndex(p => p.id === activePaper.id);
      const prev = (idx > 0) ? rem[idx - 1] : rem[rem.length - 1];
      selectPaper(prev);
      scrollToActive(prev.id);
    }

    function scrollToActive(id) {
      const el = document.getElementById('item-' + id);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function setFilter(type, val, btn) {
      filters[type] = val;
      btn.parentElement.querySelectorAll('.chip').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderList();
    }

    function renderList() {
      const container = document.getElementById('papersScroll');
      const q = document.getElementById('searchInput').value.trim().toLowerCase();

      const filtered = allPapers.filter(p => {
        if (filters.status === 'remaining' && p.downloaded) return false;
        if (filters.status === 'downloaded' && !p.downloaded) return false;
        if (filters.priority !== 'all' && p.priority !== filters.priority) return false;
        if (filters.publisher !== 'all' && p.publisher !== filters.publisher) return false;
        if (q) {
          const m = p.id.toLowerCase().includes(q) || p.title.toLowerCase().includes(q) || p.venue.toLowerCase().includes(q);
          if (!m) return false;
        }
        return true;
      });

      if (filtered.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding: 30px; color:var(--text-muted); font-size:0.8rem;">No matching papers</div>';
        return;
      }

      container.innerHTML = filtered.map(p => {
        const isActive = activePaper && activePaper.id === p.id;
        const isDone = p.downloaded;
        return `
          <div class="paper-item ${isDone ? 'is-done' : 'is-pending'} ${isActive ? 'active' : ''}"
               id="item-${p.id}" onclick="onPaperClick('${p.id}')">
            <div class="item-header">
              <span class="item-id">${p.id}</span>
              <div style="display:flex; gap:4px;">
                <span class="badge badge-p${p.priority}">P${p.priority}</span>
                <span class="badge ${getPubClass(p.publisher)}">${p.publisher}</span>
              </div>
            </div>
            <div class="item-title">${escapeHtml(p.title)}</div>
            <div class="item-meta">
              <span>${escapeHtml(p.venue.substring(0, 32))}</span>
              <span style="font-weight:600; color:${isDone ? 'var(--success)' : 'var(--warning)'};">
                ${isDone ? `&#10003; ${p.size_kb} KB` : '&#9679; Pending'}
              </span>
            </div>
          </div>
        `;
      }).join('');
    }

    function onPaperClick(id) {
      const p = allPapers.find(x => x.id === id);
      if (p) selectPaper(p);
    }

    function getPubClass(pub) {
      if (pub === 'Elsevier') return 'badge-elsevier';
      if (pub === 'IEEE') return 'badge-ieee';
      if (pub === 'Springer') return 'badge-springer';
      if (pub === 'ACM') return 'badge-acm';
      return 'badge-oa';
    }

    function escapeHtml(t) {
      if (!t) return '';
      return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    async function toggleAutoCapture() {
      const res = await fetch('/api/toggle_auto_capture', { method: 'POST' });
      const data = await res.json();
      const badge = document.getElementById('autoBadge');
      if (data.auto_capture_enabled) {
        badge.style.background = '#064e3b';
        badge.innerHTML = '<span class="pulse-dot"></span><span>Auto-Capture Active</span>';
        showToast('Auto-capture enabled: watching Downloads', 'success');
      } else {
        badge.style.background = '#374151';
        badge.innerHTML = '<span style="color:#94a3b8;">○</span><span>Auto-Capture Paused</span>';
        showToast('Auto-capture paused', 'info');
      }
    }

    async function syncFolder() {
      showToast('Rescanning papers/core/ ...', 'info');
      const res = await fetch('/api/sync', { method: 'POST' });
      const data = await res.json();
      if (data.newly_detected > 0) {
        showToast(`Detected ${data.newly_detected} newly saved file(s)!`, 'success');
      } else {
        showToast('Sync complete', 'success');
      }
      loadAll();
    }

    function triggerManualUpload() {
      document.getElementById('manualFileInput').click();
    }
    function onDragOver(e) { e.preventDefault(); }
    function onDragLeave(e) { e.preventDefault(); }
    function onDrop(e) {
      e.preventDefault();
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        uploadFile(e.dataTransfer.files[0]);
      }
    }
    function onManualFileSelected(input) {
      if (input.files && input.files.length > 0) {
        uploadFile(input.files[0]);
      }
    }
    async function uploadFile(file) {
      if (!activePaper) return;
      const formData = new FormData();
      formData.append('file', file);
      showToast(`Saving ${file.name} for ${activePaper.id}...`, 'info');
      try {
        const res = await fetch('/api/upload/' + activePaper.id, {
          method: 'POST',
          body: formData
        });
        const result = await res.json();
        if (result.success) {
          showToast(`Saved ${activePaper.id}.pdf (${result.size_kb} KB)!`, 'success');
          loadAll();
        } else {
          showToast(result.error || 'Upload failed', 'error');
        }
      } catch (e) {
        showToast('Upload error', 'error');
      }
    }

    async function pollServer() {
      try {
        const res = await fetch('/api/poll?since=' + lastEventId);
        const data = await res.json();
        if (data.new_events && data.new_events.length > 0) {
          for (const ev of data.new_events) {
            lastEventId = Math.max(lastEventId, ev.event_id);
            showToast(`🎉 Captured ${ev.filename} &rarr; Saved as ${ev.target} (${ev.size_kb} KB)!`, 'success');
            document.getElementById('eventTicker').innerHTML = `<span>&#10003; [${ev.time}] Saved <strong>${ev.target}</strong> (${ev.size_kb} KB)</span>`;
          }
          await loadAll();
        }
      } catch (e) {}
    }

    loadAll();
    setInterval(pollServer, 1500);
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = 5050
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    print(f"================================================================")
    print(f" TLS-SoK Paper Downloader Dashboard with Auto-Capture running!")
    print(f" Open your browser to: http://localhost:{port}")
    print(f" Watching Downloads:   {DOWNLOADS_DIR}")
    print(f" Saving to:            {DEST_DIR}")
    print(f"================================================================")
    app.run(host="127.0.0.1", port=port, debug=False)
