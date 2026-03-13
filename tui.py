#!/usr/bin/env python3
"""Crawler Mind TUI - Textual-based Terminal User Interface"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    ProgressBar,
    RichLog,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
MCP_CLIENT_DIR = PROJECT_ROOT / "mcp-client"
MCP_SERVER_DIR = PROJECT_ROOT / "mcp-server"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
LOGS_DIR = PROJECT_ROOT / "logs"
RESULT_DIR = MCP_CLIENT_DIR / "app" / "application" / "crawler" / "result"

API_BASE = "http://127.0.0.1:8000/api"

LOG_FILES = {
    "server": LOGS_DIR / "mcp-server.log",
    "client": LOGS_DIR / "mcp-client.log",
    "frontend": LOGS_DIR / "frontend.log",
}

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = """
Screen {
    background: $surface;
}

#main-layout {
    layout: horizontal;
    height: 1fr;
}

#left-panel {
    width: 1fr;
    min-width: 54;
    border-right: tall $primary-lighten-2;
}

#right-panel {
    width: 1fr;
    min-width: 40;
}

/* ─── Right: Log Panels ─── */

#log-container {
    height: 1fr;
}

.log-section {
    height: 1fr;
    border-bottom: hkey $primary-lighten-3;
    padding: 0 1;
}

.log-section:last-child {
    border-bottom: none;
}

.log-header {
    dock: top;
    height: 1;
    background: $primary-darken-2;
    color: $text;
    padding: 0 1;
    text-style: bold;
}

.log-header.server-hdr {
    background: #2d5a27;
}

.log-header.client-hdr {
    background: #1a4a6e;
}

.log-header.frontend-hdr {
    background: #6e4a1a;
}

RichLog {
    height: 1fr;
    scrollbar-size: 1 1;
    background: $surface-darken-1;
    padding: 0 1;
}

/* ─── Left: Service Controls ─── */

#service-bar {
    dock: top;
    height: auto;
    padding: 1 2;
    background: $surface-darken-1;
    border-bottom: tall $primary-lighten-3;
}

.svc-all-row {
    height: auto;
    align: center middle;
    margin: 0 0 1 0;
}

.svc-row {
    height: 3;
    align: left middle;
}

.svc-name {
    width: 12;
    text-style: bold;
}

.svc-indicator {
    width: 10;
    color: #e74c3c;
}

.svc-indicator.running {
    color: #2ecc71;
}

.svc-btn {
    width: auto;
    min-width: 6;
    margin: 0 0 0 1;
    height: 3;
}

.svc-btn-start {
    background: $success-darken-1;
    color: $text;
}

.svc-btn-stop {
    background: $error-darken-1;
    color: $text;
}

.svc-btn-all {
    background: $primary;
    color: $text;
    min-width: 16;
    margin: 0 1;
}

/* ─── Left: Tabbed Content ─── */

#tab-content {
    height: 1fr;
    padding: 0;
}

TabbedContent {
    height: 1fr;
}

TabPane {
    padding: 1 2;
}

/* ─── Tab Panes Common ─── */

.section-title {
    text-style: bold;
    color: $accent;
    margin: 0 0 1 0;
}

.action-bar {
    height: auto;
    align: left middle;
    margin: 1 0;
}

.action-bar Button {
    margin: 0 1 0 0;
}

.option-row {
    height: auto;
    align: left middle;
    margin: 0 0 1 0;
}

.option-row Label {
    width: auto;
    margin: 0 1 0 0;
}

.option-row Switch {
    margin: 0 2 0 0;
}

.option-row Input {
    width: 20;
    margin: 0 1 0 0;
}

.progress-section {
    height: auto;
    margin: 1 0;
}

.status-text {
    height: auto;
    margin: 0 0 1 0;
    color: $text-muted;
}

ProgressBar {
    margin: 0 0 1 0;
}

/* ─── File List ─── */

.file-list-container {
    height: 1fr;
    border: tall $primary-lighten-3;
    margin: 1 0;
}

DataTable {
    height: 1fr;
}

/* ─── JSON Compare ─── */

#compare-file-selects {
    height: auto;
    margin: 1 0;
}

#compare-file-selects Label {
    width: auto;
    margin: 0 1 0 0;
}

#compare-file-selects Select {
    width: 1fr;
}

/* ─── Result Editor ─── */

.editor-select-row {
    height: auto;
    margin: 0 0 1 0;
}

.editor-select-row Select {
    width: 1fr;
    margin: 0 0 0 1;
}

TextArea {
    height: 1fr;
}

/* ─── Menu Tree ─── */

#menu-tree {
    height: 1fr;
    min-height: 10;
    border: tall $primary-lighten-3;
    background: $surface-darken-1;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#menu-log {
    height: 5;
    min-height: 3;
}

/* ─── Overall polish ─── */

Button:hover {
    opacity: 0.85;
}

Button:focus {
    text-style: bold reverse;
}

#status-bar {
    dock: bottom;
    height: 1;
    background: $primary-darken-2;
    color: $text;
    padding: 0 2;
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════

class CrawlerMindApp(App):
    """Crawler Mind TUI"""

    TITLE = "Crawler Mind"
    SUB_TITLE = "MCP Crawling Management Console"
    CSS = CSS

    BINDINGS = [
        Binding("q", "quit", "종료"),
        Binding("ctrl+s", "start_all", "전체 시작"),
        Binding("ctrl+x", "stop_all", "전체 중지"),
        Binding("ctrl+l", "clear_logs", "로그 초기화"),
        Binding("f5", "refresh", "새로고침"),
    ]

    server_running: reactive[bool] = reactive(False)
    client_running: reactive[bool] = reactive(False)
    frontend_running: reactive[bool] = reactive(False)

    _processes: dict[str, subprocess.Popen] = {}
    _log_tasks: dict[str, asyncio.Task] = {}
    _progress_timers: dict[str, Timer] = {}
    _menu_extracting: bool = False
    _menu_node_map: dict = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main-layout"):
            # ── Left Panel ──
            with Vertical(id="left-panel"):
                yield from self._compose_service_bar()
                with Container(id="tab-content"):
                    with TabbedContent(initial="daily"):
                        with TabPane("데일리 추출", id="daily"):
                            yield from self._compose_daily_tab()
                        with TabPane("메뉴 추출", id="menu"):
                            yield from self._compose_menu_tab()
                        with TabPane("JSON 비교", id="compare"):
                            yield from self._compose_compare_tab()
                        with TabPane("결과 편집", id="editor"):
                            yield from self._compose_editor_tab()
                        with TabPane("검증", id="verify"):
                            yield from self._compose_verify_tab()

            # ── Right Panel ──
            with Vertical(id="right-panel"):
                with Vertical(id="log-container"):
                    with Vertical(classes="log-section"):
                        yield Static("  MCP Server", classes="log-header server-hdr")
                        yield RichLog(id="log-server", wrap=True, markup=True)
                    with Vertical(classes="log-section"):
                        yield Static("  MCP Client", classes="log-header client-hdr")
                        yield RichLog(id="log-client", wrap=True, markup=True)
                    with Vertical(classes="log-section"):
                        yield Static("  Frontend", classes="log-header frontend-hdr")
                        yield RichLog(id="log-frontend", wrap=True, markup=True)

        yield Static("", id="status-bar")
        yield Footer()

    # ───────────────────────────────────────────────────────────────────
    # Compose: Service Bar (Fix #2 - 정렬)
    # ───────────────────────────────────────────────────────────────────

    def _compose_service_bar(self):
        with Vertical(id="service-bar"):
            with Horizontal(classes="svc-all-row"):
                yield Button("▶  전체 시작", id="btn-start-all", classes="svc-btn svc-btn-all svc-btn-start")
                yield Button("■  전체 중지", id="btn-stop-all", classes="svc-btn svc-btn-all svc-btn-stop")

            with Horizontal(classes="svc-row"):
                yield Static("MCP Server", classes="svc-name")
                yield Static("● STOP", id="status-server", classes="svc-indicator")
                yield Button("▶", id="btn-start-server", classes="svc-btn svc-btn-start")
                yield Button("■", id="btn-stop-server", classes="svc-btn svc-btn-stop")

            with Horizontal(classes="svc-row"):
                yield Static("MCP Client", classes="svc-name")
                yield Static("● STOP", id="status-client", classes="svc-indicator")
                yield Button("▶", id="btn-start-client", classes="svc-btn svc-btn-start")
                yield Button("■", id="btn-stop-client", classes="svc-btn svc-btn-stop")

            with Horizontal(classes="svc-row"):
                yield Static("Frontend  ", classes="svc-name")
                yield Static("● STOP", id="status-frontend", classes="svc-indicator")
                yield Button("▶", id="btn-start-frontend", classes="svc-btn svc-btn-start")
                yield Button("■", id="btn-stop-frontend", classes="svc-btn svc-btn-stop")

    # ───────────────────────────────────────────────────────────────────
    # Compose: Tab Panes
    # ───────────────────────────────────────────────────────────────────

    def _compose_daily_tab(self):
        yield Static("데일리 크롤링", classes="section-title")

        with Horizontal(classes="option-row"):
            yield Label("강제 재크롤링")
            yield Switch(value=True, id="daily-force")
            yield Label("DB 업데이트")
            yield Switch(value=True, id="daily-db-update")

        with Horizontal(classes="option-row"):
            yield Label("동시성")
            yield Input(value="3", id="daily-concurrency", type="integer")
            yield Label("제한수")
            yield Input(placeholder="전체", id="daily-limit", type="integer")

        with Horizontal(classes="action-bar"):
            yield Button("크롤링 시작", id="btn-daily-start", variant="success")
            yield Button("통계 조회", id="btn-daily-stats", variant="primary")
            yield Button("작업 목록", id="btn-daily-tasks", variant="default")

        with Vertical(classes="progress-section"):
            yield Static("대기 중", id="daily-status", classes="status-text")
            yield ProgressBar(id="daily-progress", total=100, show_eta=False)

        yield RichLog(id="daily-log", wrap=True, markup=True)

    def _compose_menu_tab(self):
        yield Static("GNB 메뉴 추출", classes="section-title")
        yield Static(
            "KT 홈페이지의 GNB(Global Navigation Bar) 메뉴 구조를 자동으로 추출하여 DB에 저장합니다.",
            classes="status-text",
        )

        with Horizontal(classes="option-row"):
            yield Label("DB 저장")
            yield Switch(value=True, id="menu-save-db")
            yield Label("지연(초)")
            yield Input(value="1.0", id="menu-delay")

        with Horizontal(classes="action-bar"):
            yield Button("메뉴 추출 시작", id="btn-menu-extract", variant="success")
            yield Button("DB 메뉴 조회", id="btn-menu-list", variant="primary")
            yield Button("DB 통계", id="btn-menu-stats", variant="default")

        with Vertical(classes="progress-section"):
            yield Static("대기 중", id="menu-status", classes="status-text")
            yield ProgressBar(id="menu-progress", total=100, show_eta=False)

        yield Tree("🌐 kt.com", id="menu-tree")
        yield RichLog(id="menu-log", wrap=True, markup=True)

    def _compose_compare_tab(self):
        yield Static("JSON 비교", classes="section-title")
        yield Static(
            "크롤링 결과(data_*.json) 두 파일을 비교하여 변경사항 리포트(PDF)를 생성합니다.",
            classes="status-text",
        )

        with Vertical(id="compare-file-selects"):
            with Horizontal(classes="option-row"):
                yield Label("파일 1 (이전)")
                yield Select([], id="compare-file1", prompt="파일을 선택하세요")
            with Horizontal(classes="option-row"):
                yield Label("파일 2 (최신)")
                yield Select([], id="compare-file2", prompt="파일을 선택하세요")

        with Horizontal(classes="action-bar"):
            yield Button("파일 목록 갱신", id="btn-compare-refresh", variant="default")
            yield Button("비교 실행", id="btn-compare-run", variant="success")

        with Vertical(classes="progress-section"):
            yield Static("대기 중", id="compare-status", classes="status-text")
            yield ProgressBar(id="compare-progress", total=100, show_eta=False)

        yield RichLog(id="compare-log", wrap=True, markup=True)

    def _compose_verify_tab(self):
        yield Static("데이터 검증", classes="section-title")
        yield Static(
            "크롤링 결과 JSON 파일의 docId 중복 여부 등을 검사합니다.",
            classes="status-text",
        )

        with Horizontal(classes="editor-select-row"):
            yield Button("파일 갱신", id="btn-verify-refresh", variant="default")
            yield Select([], id="verify-file-select", prompt="JSON 파일 선택")

        with Horizontal(classes="action-bar"):
            yield Button("docId 중복 검사", id="btn-verify-docid", variant="success")

        with Vertical(classes="progress-section"):
            yield Static("대기 중", id="verify-status", classes="status-text")
            yield ProgressBar(id="verify-progress", total=100, show_eta=False)

        yield RichLog(id="verify-log", wrap=True, markup=True)

    def _compose_editor_tab(self):
        yield Static("결과 편집기", classes="section-title")

        with Horizontal(classes="editor-select-row"):
            yield Button("파일 갱신", id="btn-editor-refresh", variant="default")
            yield Select([], id="editor-file-select", prompt="JSON 파일 선택")

        with Horizontal(classes="option-row"):
            yield Label("검색")
            yield Input(placeholder="docId / title / text 검색", id="editor-search")
            yield Button("검색", id="btn-editor-search", variant="primary")

        with Vertical(classes="file-list-container"):
            yield DataTable(id="editor-table")

        yield Static("문서 상세", classes="section-title")
        yield Static("문서를 선택하면 여기에 정보가 표시됩니다.", id="editor-doc-title", classes="status-text")
        yield TextArea(id="editor-textarea", language="markdown")
        with Horizontal(classes="action-bar"):
            yield Button("저장", id="btn-editor-save", variant="success")

    # ───────────────────────────────────────────────────────────────────
    # Lifecycle (Fix #1 - 자동 로딩)
    # ───────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        for log_file in LOG_FILES.values():
            log_file.touch(exist_ok=True)

        self._start_log_watchers()
        self._update_status_bar("시스템 준비 완료")

        editor_table = self.query_one("#editor-table", DataTable)
        editor_table.add_columns("docId", "title", "url", "길이")
        editor_table.cursor_type = "row"

        self._load_all_file_lists()

    def action_quit(self) -> None:
        self._stop_all_services()
        for task in self._log_tasks.values():
            task.cancel()
        self.exit()

    def on_unmount(self) -> None:
        self._stop_all_services()
        for task in self._log_tasks.values():
            task.cancel()

    @work(thread=False)
    async def _load_all_file_lists(self) -> None:
        """앱 시작 시 모든 파일 목록 로드"""
        files = self._get_result_json_files()
        options = [(f"{f.name}  ({f.stat().st_size // 1024}KB)", f.name) for f in files]

        for sel_id in ("#compare-file1", "#compare-file2", "#editor-file-select", "#verify-file-select"):
            try:
                self.query_one(sel_id, Select).set_options(options)
            except NoMatches:
                pass

        count = len(files)
        self._update_status_bar(f"준비 완료 — result 폴더: {count}개 JSON 파일 로드됨")

    # ───────────────────────────────────────────────────────────────────
    # Status Bar
    # ───────────────────────────────────────────────────────────────────

    def _update_status_bar(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            self.query_one("#status-bar", Static).update(f"  [{ts}] {msg}")
        except NoMatches:
            pass

    # ───────────────────────────────────────────────────────────────────
    # Progress Helpers (Fix #3)
    # ───────────────────────────────────────────────────────────────────

    def _reset_progress(self, bar_id: str) -> ProgressBar:
        bar = self.query_one(f"#{bar_id}", ProgressBar)
        bar.update(total=100, progress=0)
        return bar

    def _start_indeterminate_progress(self, bar_id: str, interval: float = 0.3) -> None:
        """비동기 API 호출 중 서서히 진행되는 프로그레스 시뮬레이션"""
        bar = self.query_one(f"#{bar_id}", ProgressBar)
        self._stop_indeterminate_progress(bar_id)

        def _tick() -> None:
            current = bar.progress or 0
            if current < 85:
                remaining = 85 - current
                step = max(0.5, remaining * 0.08)
                bar.advance(step)

        timer = self.set_interval(interval, _tick)
        self._progress_timers[bar_id] = timer

    def _stop_indeterminate_progress(self, bar_id: str) -> None:
        timer = self._progress_timers.pop(bar_id, None)
        if timer:
            timer.stop()

    def _finish_progress(self, bar_id: str, success: bool = True) -> None:
        self._stop_indeterminate_progress(bar_id)
        bar = self.query_one(f"#{bar_id}", ProgressBar)
        bar.update(total=100, progress=100 if success else bar.progress)

    # ───────────────────────────────────────────────────────────────────
    # Service Management
    # ───────────────────────────────────────────────────────────────────

    def _start_service(self, name: str) -> None:
        if name in self._processes and self._processes[name].poll() is None:
            self._update_status_bar(f"{name} 이미 실행 중")
            return

        log_file = LOG_FILES.get(name)
        env = os.environ.copy()

        if name == "server":
            cmd = ["python", "server.py"]
            cwd = str(MCP_SERVER_DIR)
        elif name == "client":
            cmd = ["python", "main.py"]
            cwd = str(MCP_CLIENT_DIR)
        elif name == "frontend":
            cmd = ["npm", "run", "dev"]
            cwd = str(FRONTEND_DIR)
        else:
            return

        try:
            lf = open(log_file, "a")
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                env=env,
                preexec_fn=os.setsid,
            )
            self._processes[name] = proc
            self._set_service_status(name, True)
            self._update_status_bar(f"{name} 시작됨 (PID: {proc.pid})")
        except Exception as e:
            self._update_status_bar(f"{name} 시작 실패: {e}")

    def _stop_service(self, name: str) -> None:
        proc = self._processes.get(name)
        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
            self._update_status_bar(f"{name} 중지됨")
        self._set_service_status(name, False)
        self._processes.pop(name, None)

    def _stop_all_services(self) -> None:
        for name in list(self._processes.keys()):
            self._stop_service(name)

    def _set_service_status(self, name: str, running: bool) -> None:
        try:
            widget = self.query_one(f"#status-{name}", Static)
            if running:
                widget.update("● RUN ")
                widget.add_class("running")
            else:
                widget.update("● STOP")
                widget.remove_class("running")
        except NoMatches:
            pass

        if name == "server":
            self.server_running = running
        elif name == "client":
            self.client_running = running
        elif name == "frontend":
            self.frontend_running = running

    # ───────────────────────────────────────────────────────────────────
    # Log Watchers
    # ───────────────────────────────────────────────────────────────────

    def _start_log_watchers(self) -> None:
        for name, log_file in LOG_FILES.items():
            task = asyncio.create_task(self._watch_log(name, log_file))
            self._log_tasks[name] = task

    async def _watch_log(self, name: str, log_file: Path) -> None:
        widget_id = f"log-{name}"
        try:
            log_widget = self.query_one(f"#{widget_id}", RichLog)
        except NoMatches:
            return

        last_pos = 0
        if log_file.exists():
            last_pos = log_file.stat().st_size

        while True:
            try:
                await asyncio.sleep(0.5)
                if not log_file.exists():
                    continue
                size = log_file.stat().st_size
                if size < last_pos:
                    last_pos = 0
                if size > last_pos:
                    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        new_data = f.read()
                        last_pos = f.tell()
                    for line in new_data.splitlines():
                        if line.strip():
                            log_widget.write(line)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)

    # ───────────────────────────────────────────────────────────────────
    # Button Handlers
    # ───────────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-start-all")
    def on_start_all(self) -> None:
        self.action_start_all()

    @on(Button.Pressed, "#btn-stop-all")
    def on_stop_all(self) -> None:
        self.action_stop_all()

    @on(Button.Pressed, "#btn-start-server")
    def on_start_server(self) -> None:
        self._start_service("server")

    @on(Button.Pressed, "#btn-stop-server")
    def on_stop_server(self) -> None:
        self._stop_service("server")

    @on(Button.Pressed, "#btn-start-client")
    def on_start_client(self) -> None:
        self._start_service("client")

    @on(Button.Pressed, "#btn-stop-client")
    def on_stop_client(self) -> None:
        self._stop_service("client")

    @on(Button.Pressed, "#btn-start-frontend")
    def on_start_frontend(self) -> None:
        self._start_service("frontend")

    @on(Button.Pressed, "#btn-stop-frontend")
    def on_stop_frontend(self) -> None:
        self._stop_service("frontend")

    # ── Daily Crawling ──

    @on(Button.Pressed, "#btn-daily-start")
    def on_daily_start(self) -> None:
        self._run_daily_crawling()

    @on(Button.Pressed, "#btn-daily-stats")
    def on_daily_stats(self) -> None:
        self._fetch_daily_stats()

    @on(Button.Pressed, "#btn-daily-tasks")
    def on_daily_tasks(self) -> None:
        self._fetch_daily_tasks()

    # ── Menu Extraction ──

    @on(Button.Pressed, "#btn-menu-extract")
    def on_menu_extract(self) -> None:
        self._run_menu_extraction()

    @on(Button.Pressed, "#btn-menu-list")
    def on_menu_list(self) -> None:
        self._fetch_menu_list()

    @on(Button.Pressed, "#btn-menu-stats")
    def on_menu_stats(self) -> None:
        self._fetch_menu_stats()

    # ── JSON Compare ──

    @on(Button.Pressed, "#btn-compare-refresh")
    def on_compare_refresh(self) -> None:
        self._refresh_compare_files()

    @on(Button.Pressed, "#btn-compare-run")
    def on_compare_run(self) -> None:
        self._run_json_compare()

    # ── Verify ──

    @on(Button.Pressed, "#btn-verify-refresh")
    def on_verify_refresh(self) -> None:
        self._refresh_verify_files()

    @on(Button.Pressed, "#btn-verify-docid")
    def on_verify_docid(self) -> None:
        self._run_docid_check()

    # ── Result Editor ──

    @on(Button.Pressed, "#btn-editor-refresh")
    def on_editor_refresh(self) -> None:
        self._refresh_editor_files()

    @on(Button.Pressed, "#btn-editor-search")
    def on_editor_search(self) -> None:
        self._search_editor_docs()

    @on(Button.Pressed, "#btn-editor-save")
    def on_editor_save(self) -> None:
        self._save_editor_doc()

    @on(DataTable.RowSelected, "#editor-table")
    def on_editor_row_selected(self, event: DataTable.RowSelected) -> None:
        self._load_editor_doc(event.row_key)

    # ───────────────────────────────────────────────────────────────────
    # Actions
    # ───────────────────────────────────────────────────────────────────

    def action_start_all(self) -> None:
        for svc in ("server", "client", "frontend"):
            self._start_service(svc)
        self._update_status_bar("전체 서비스 시작됨")

    def action_stop_all(self) -> None:
        self._stop_all_services()
        self.action_clear_logs()
        self._update_status_bar("전체 서비스 중지됨, 로그 초기화됨")

    def action_clear_logs(self) -> None:
        for name in ("server", "client", "frontend"):
            try:
                self.query_one(f"#log-{name}", RichLog).clear()
                log_file = LOG_FILES[name]
                log_file.write_text("")
            except NoMatches:
                pass
        self._update_status_bar("로그 초기화됨")

    def action_refresh(self) -> None:
        self._load_all_file_lists()
        self._update_status_bar("새로고침 완료")

    # ═══════════════════════════════════════════════════════════════════
    # Workers: Daily Crawling (Fix #3 프로그레스 + Fix #4 상세 오류)
    # ═══════════════════════════════════════════════════════════════════

    @work(thread=False)
    async def _run_daily_crawling(self) -> None:
        log = self.query_one("#daily-log", RichLog)
        status = self.query_one("#daily-status", Static)
        log.clear()
        self._reset_progress("daily-progress")

        force = self.query_one("#daily-force", Switch).value
        db_update = self.query_one("#daily-db-update", Switch).value

        concurrency_input = self.query_one("#daily-concurrency", Input).value
        concurrency = int(concurrency_input) if concurrency_input else 3

        limit_input = self.query_one("#daily-limit", Input).value
        limit = int(limit_input) if limit_input else None

        body: dict = {
            "force_recrawl": force,
            "update_menu_links": db_update,
            "mode": "parallel",
            "concurrency": concurrency,
        }
        if limit:
            body["limit"] = limit

        status.update("크롤링 작업 생성 중...")
        log.write("[bold cyan]▶ Daily Crawling 시작[/]")
        log.write(f"  옵션: 강제={force}, DB업데이트={db_update}, 동시성={concurrency}, 제한={limit or '없음'}")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{API_BASE}/daily-crawling", json=body)
                resp.raise_for_status()
                data = resp.json()

            task_id = data.get("task_id", "")
            total = data.get("total_urls", 0)

            if not task_id:
                status.update("크롤링 대상 URL 없음")
                log.write("[yellow]크롤링 대상 URL이 없습니다[/]")
                return

            log.write(f"  Task ID: [bold]{task_id}[/]")
            log.write(f"  대상 URL: [bold]{total}[/]개")
            log.write("")
            status.update(f"크롤링 중... (0/{total})")

            await self._poll_daily_task(task_id, total, log, status)

        except httpx.ConnectError:
            status.update("연결 실패 — MCP Client가 실행 중인지 확인하세요")
            log.write("[bold red]연결 실패: MCP Client (localhost:8000) 에 연결할 수 없습니다[/]")
            log.write("[dim]  → 좌측 상단에서 MCP Client를 먼저 시작하세요[/]")
        except httpx.HTTPStatusError as e:
            status.update(f"HTTP 오류: {e.response.status_code}")
            log.write(f"[bold red]HTTP {e.response.status_code} 오류[/]")
            self._log_http_error_detail(log, e)
        except Exception as e:
            status.update(f"오류: {e}")
            log.write(f"[bold red]오류: {type(e).__name__}: {e}[/]")

    async def _poll_daily_task(
        self, task_id: str, total: int,
        log: RichLog, status: Static,
    ) -> None:
        bar = self.query_one("#daily-progress", ProgressBar)
        last_processed = 0
        error_urls: list[dict] = []

        while True:
            await asyncio.sleep(2)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(f"{API_BASE}/daily-crawling/{task_id}")
                    resp.raise_for_status()
                    data = resp.json()

                task_status = data.get("status", "unknown")
                result = data.get("result") or {}

                if isinstance(result, dict):
                    processed = result.get("processed_urls", result.get("processed", 0))
                    success_count = result.get("success_count", 0)
                    fail_count = result.get("fail_count", result.get("error_count", 0))

                    if isinstance(processed, int) and total > 0:
                        pct = min(95, int(processed / total * 100))
                        bar.update(total=100, progress=pct)

                        if processed > last_processed:
                            delta = processed - last_processed
                            status.update(
                                f"크롤링 중... ({processed}/{total}) "
                                f"성공:{success_count} 실패:{fail_count}"
                            )
                            last_processed = processed

                    errors = result.get("errors", result.get("failed_urls", []))
                    if isinstance(errors, list):
                        for err in errors[len(error_urls):]:
                            error_urls.append(err)
                            self._log_crawl_error(log, err)

                if task_status in ("completed", "failed", "error"):
                    if task_status == "completed":
                        bar.update(total=100, progress=100)
                        log.write("")
                        log.write("[bold green]━━━ 크롤링 완료 ━━━[/]")

                        if isinstance(result, dict):
                            sc = result.get("success_count", "?")
                            fc = result.get("fail_count", result.get("error_count", "?"))
                            fp = result.get("file_path", "")
                            log.write(f"  성공: [green]{sc}[/]  실패: [red]{fc}[/]")
                            if fp:
                                log.write(f"  결과 파일: {fp}")

                        if error_urls:
                            log.write(f"\n[bold yellow]⚠ 실패 URL 요약 ({len(error_urls)}건)[/]")
                            for i, err in enumerate(error_urls[:10], 1):
                                url = err.get("url", err) if isinstance(err, dict) else str(err)
                                log.write(f"  {i}. {url}")
                            if len(error_urls) > 10:
                                log.write(f"  ... 외 {len(error_urls) - 10}건")

                        status.update(f"크롤링 완료 (성공:{sc} 실패:{fc})")
                    else:
                        err_msg = data.get("error", "알 수 없는 오류")
                        log.write(f"\n[bold red]━━━ 크롤링 실패 ━━━[/]")
                        log.write(f"  오류: {err_msg}")
                        status.update(f"실패: {err_msg}")
                    break

            except Exception as e:
                log.write(f"[dim yellow]  폴링 재시도... ({type(e).__name__})[/]")

    @work(thread=False)
    async def _fetch_daily_stats(self) -> None:
        log = self.query_one("#daily-log", RichLog)
        log.clear()
        log.write("[bold cyan]통계 조회 중...[/]")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{API_BASE}/daily-crawling/stats")
                resp.raise_for_status()
                data = resp.json()

            STAT_LABELS = {
                "total_urls": "전체 URL 수",
                "active_urls": "활성 URL 수",
                "last_crawled_count": "마지막 크롤링 수",
                "never_crawled_count": "미크롤링 URL 수",
                "last_crawled_at": "마지막 크롤링 일시",
                "success_rate": "성공률",
            }

            log.write("[bold green]━━━ Daily Crawling 통계 ━━━[/]")
            for key, val in data.items():
                label = STAT_LABELS.get(key, key)
                log.write(f"  {label}: [bold]{val}[/]")

        except httpx.ConnectError:
            log.write("[bold red]연결 실패: MCP Client가 실행 중인지 확인하세요[/]")
        except Exception as e:
            log.write(f"[bold red]오류: {type(e).__name__}: {e}[/]")

    @work(thread=False)
    async def _fetch_daily_tasks(self) -> None:
        log = self.query_one("#daily-log", RichLog)
        log.clear()
        log.write("[bold cyan]작업 목록 조회 중...[/]")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{API_BASE}/daily-crawling/tasks?limit=10")
                resp.raise_for_status()
                tasks = resp.json()

            log.write(f"[bold green]━━━ 최근 작업 ({len(tasks)}건) ━━━[/]")

            STATUS_COLORS = {
                "completed": "green",
                "running": "cyan",
                "pending": "yellow",
                "failed": "red",
                "error": "red",
            }

            for t in tasks:
                tid = t.get("taskId", "?")[:12]
                st = t.get("status", "?")
                ca = t.get("createdAt", "?")
                color = STATUS_COLORS.get(st, "white")
                log.write(f"  [{color}]{st:10}[/] {tid}  ({ca})")

                result = t.get("result") or {}
                if isinstance(result, dict) and result:
                    sc = result.get("success_count", "?")
                    fc = result.get("fail_count", result.get("error_count", "?"))
                    log.write(f"             성공:{sc} 실패:{fc}")

        except httpx.ConnectError:
            log.write("[bold red]연결 실패: MCP Client가 실행 중인지 확인하세요[/]")
        except Exception as e:
            log.write(f"[bold red]오류: {type(e).__name__}: {e}[/]")

    # ═══════════════════════════════════════════════════════════════════
    # Workers: Menu Extraction (Fix #3 프로그레스 + Fix #5 의미)
    # ═══════════════════════════════════════════════════════════════════

    @work(thread=False)
    async def _run_menu_extraction(self) -> None:
        tree = self.query_one("#menu-tree", Tree)
        log = self.query_one("#menu-log", RichLog)
        status = self.query_one("#menu-status", Static)

        tree.clear()
        tree.root.set_label("🌐 kt.com")
        tree.root.expand()
        log.clear()
        self._reset_progress("menu-progress")
        self._menu_node_map = {}

        save_db = self.query_one("#menu-save-db", Switch).value
        delay_input = self.query_one("#menu-delay", Input).value
        delay = float(delay_input) if delay_input else 1.0
        body = {"save_to_db": save_db, "delay": delay}

        status.update("메뉴 추출 태스크 생성 중...")
        log.write(f"[bold cyan]▶ GNB 메뉴 추출 시작[/] (DB저장: {'ON' if save_db else 'OFF'}, 지연: {delay}초)")

        self._menu_extracting = True
        watcher_task = asyncio.create_task(
            self._watch_extraction_log(tree, status)
        )

        try:
            # 1) 태스크 생성 (즉시 반환)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{API_BASE}/gnb/extract_menus", json=body)
                resp.raise_for_status()
                data = resp.json()

            task_id = data.get("task_id", "")
            if not task_id:
                log.write("[bold red]태스크 생성 실패[/]")
                return

            log.write(f"  Task ID: [bold]{task_id}[/]")
            self._start_indeterminate_progress("menu-progress")

            # 2) 폴링으로 진행 상황 추적
            await self._poll_menu_extraction_task(task_id, tree, log, status)

        except httpx.ConnectError:
            self._finish_progress("menu-progress", success=False)
            status.update("연결 실패")
            log.write("[bold red]연결 실패: MCP Client가 실행 중인지 확인하세요[/]")
        except httpx.HTTPStatusError as e:
            self._finish_progress("menu-progress", success=False)
            status.update(f"HTTP 오류: {e.response.status_code}")
            log.write(f"[bold red]HTTP {e.response.status_code} 오류[/]")
            self._log_http_error_detail(log, e)
        except Exception as e:
            self._finish_progress("menu-progress", success=False)
            status.update(f"오류: {e}")
            log.write(f"[bold red]오류: {type(e).__name__}: {e}[/]")
        finally:
            self._menu_extracting = False
            await watcher_task

    async def _poll_menu_extraction_task(
        self, task_id: str, tree: Tree, log: RichLog, status: Static,
    ) -> None:
        """GNB 추출 태스크를 폴링하여 진행 상황 업데이트"""
        bar = self.query_one("#menu-progress", ProgressBar)
        last_step = ""

        STEP_LABELS = {
            "dom_extraction": "📡 Step 1: KT 메인 페이지 DOM 추출 중...",
            "gnb_parsing": "🔍 Step 2: GNB 메뉴 트리 파싱 중...",
            "submenu_extraction": "🌳 Step 3: 서브메뉴 추출 중...",
            "saving": "💾 DB 저장 중...",
            "done": "✅ 완료",
        }

        while True:
            await asyncio.sleep(2)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(f"{API_BASE}/gnb/extract_menus/{task_id}")
                    resp.raise_for_status()
                    data = resp.json()

                task_status = data.get("status", "unknown")
                step = data.get("step", "")
                progress = data.get("progress") or {}
                current_menu = progress.get("current_menu", "")

                if step != last_step:
                    label = STEP_LABELS.get(step, step)
                    log.write(f"[cyan]{label}[/]")
                    last_step = step

                if step == "submenu_extraction":
                    current = progress.get("current", 0)
                    total = progress.get("total", 0)
                    if total > 0:
                        pct = min(95, int(current / total * 100))
                        bar.update(total=100, progress=pct)
                    msg = progress.get("message", "")
                    if current_menu:
                        status.update(f"🌳 {msg} — {current_menu}")
                    else:
                        status.update(f"🌳 {msg}")

                if task_status == "completed":
                    result = data.get("result") or {}
                    total_menus = result.get("total_menus", 0)
                    saved_count = result.get("saved_count", 0)
                    elapsed = result.get("elapsed", "?")

                    self._finish_progress("menu-progress")
                    tree.root.set_label(f"🌐 kt.com — {total_menus}개 메뉴, {saved_count}개 DB 저장")
                    status.update(f"✅ 완료: {total_menus}개 추출, {saved_count}개 DB 저장 ({elapsed})")
                    log.write(f"[bold green]✅ 추출 완료: {total_menus}개 메뉴, {saved_count}개 DB 저장 ({elapsed})[/]")
                    break

                elif task_status == "failed":
                    err = data.get("error", "알 수 없는 오류")
                    self._finish_progress("menu-progress", success=False)
                    status.update(f"실패: {err}")
                    log.write(f"[bold red]❌ 추출 실패: {err}[/]")
                    break

            except Exception as e:
                log.write(f"[dim yellow]  폴링 재시도... ({type(e).__name__})[/]")

    async def _watch_extraction_log(self, tree: Tree, status: Static) -> None:
        """MCP 클라이언트 로그를 실시간 파싱하여 메뉴 트리를 업데이트한다."""
        log_file = LOG_FILES["client"]
        last_pos = log_file.stat().st_size if log_file.exists() else 0
        current_path: list[str] = []

        while self._menu_extracting:
            try:
                await asyncio.sleep(0.3)
                if not log_file.exists():
                    continue

                size = log_file.stat().st_size
                if size < last_pos:
                    last_pos = 0
                if size <= last_pos:
                    continue

                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_pos)
                    new_data = f.read()
                    last_pos = f.tell()

                last_node = None
                for line in new_data.splitlines():
                    if not line.strip():
                        continue

                    msg_match = re.search(
                        r" - (?:INFO|WARNING|ERROR|DEBUG) - (.+)$", line
                    )
                    msg = msg_match.group(1) if msg_match else line

                    if "[Step 1]" in msg and "시작" in msg:
                        status.update("📡 Step 1: KT 메인 페이지 DOM 추출 중...")
                        continue
                    if "[Step 2]" in msg and "시작" in msg:
                        status.update("🔍 Step 2: GNB 메뉴 트리 파싱 중...")
                        continue
                    if "[Step 3]" in msg and "시작" in msg:
                        status.update("🌳 Step 3: 서브메뉴 추출 중...")
                        continue
                    if "[Step" in msg and "완료" in msg:
                        continue

                    top_match = re.search(r"\[(\d+)/(\d+)\]\s+(.+)$", msg)
                    if top_match:
                        idx, total, name = top_match.groups()
                        name = name.strip()
                        key = name
                        if key not in self._menu_node_map:
                            node = tree.root.add(f"📂 {name}", expand=True)
                            self._menu_node_map[key] = node
                            last_node = node
                        status.update(f"🌳 [{idx}/{total}] {name} 서브메뉴 추출 중...")
                        continue

                    depth_match = re.search(r"🔍\s*\[(\d+)depth\]\s+(.+)", msg)
                    if depth_match:
                        _depth_str, path_str = depth_match.groups()
                        parts = [p.strip() for p in path_str.split(" > ")]
                        current_path = parts

                        parent = tree.root
                        for i, part in enumerate(parts):
                            key = "^".join(parts[: i + 1])
                            if key not in self._menu_node_map:
                                is_leaf = i == len(parts) - 1
                                label = f"⏳ {part}" if is_leaf else f"📂 {part}"
                                node = parent.add(label, expand=True)
                                self._menu_node_map[key] = node
                                last_node = node
                            parent = self._menu_node_map[key]
                        continue

                    if ("✅ 완료" in msg or "✅ 구조화된" in msg) and current_path:
                        key = "^".join(current_path)
                        node = self._menu_node_map.get(key)
                        if node:
                            count_match = re.search(r"\((\d+)개", msg)
                            count = count_match.group(1) if count_match else "0"
                            node.set_label(f"✅ {current_path[-1]} ({count})")
                            last_node = node
                        continue

                    if "⚠️ 추출 결과 없음" in msg and current_path:
                        key = "^".join(current_path)
                        node = self._menu_node_map.get(key)
                        if node:
                            node.set_label(f"⚠️ {current_path[-1]} (0)")
                        continue

                    if "⏭️ 스킵됨" in msg and current_path:
                        key = "^".join(current_path)
                        node = self._menu_node_map.get(key)
                        if node:
                            node.set_label(f"⏭️ {current_path[-1]}")
                        continue

                    if "❌ 실패" in msg and current_path:
                        key = "^".join(current_path)
                        node = self._menu_node_map.get(key)
                        if node:
                            node.set_label(f"❌ {current_path[-1]}")
                        continue

                if last_node is not None:
                    try:
                        tree.scroll_end(animate=False)
                    except Exception:
                        pass

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    def _build_tree_from_menus(self, tree: Tree, menus: list) -> None:
        """평탄화된 메뉴 리스트(menu_path: A^B^C)로 트리 위젯을 구성한다."""
        node_map: dict = {}

        for m in menus:
            path = m.get("menu_path", "")
            active = m.get("is_active", True)
            parts = [p.strip() for p in path.split("^") if p.strip()]
            if not parts:
                continue

            parent = tree.root
            for i, part in enumerate(parts):
                key = "^".join(parts[: i + 1])
                if key not in node_map:
                    is_leaf = i == len(parts) - 1
                    if is_leaf:
                        mark = "●" if active else "○"
                        label = f"{mark} {part}"
                    else:
                        label = f"📂 {part}"
                    node = parent.add(label)
                    node_map[key] = node
                parent = node_map[key]

        tree.root.expand()
        for child in tree.root.children:
            child.expand()

    @work(thread=False)
    async def _fetch_menu_list(self) -> None:
        """DB에 저장된 GNB 메뉴 목록을 트리 형태로 시각화한다."""
        tree = self.query_one("#menu-tree", Tree)
        log = self.query_one("#menu-log", RichLog)

        tree.clear()
        tree.root.set_label("🌐 kt.com")
        log.clear()
        log.write("[bold cyan]DB에 저장된 메뉴 조회 중...[/]")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{API_BASE}/gnb/menus?limit=2000")
                resp.raise_for_status()
                menus = resp.json()

            self._build_tree_from_menus(tree, menus)
            log.write(f"[bold green]✅ 총 {len(menus)}개 메뉴 로드 완료[/]")
            self._update_status_bar(f"DB 메뉴: {len(menus)}개 로드됨")

        except httpx.ConnectError:
            log.write("[bold red]연결 실패: MCP Client가 실행 중인지 확인하세요[/]")
        except Exception as e:
            log.write(f"[bold red]오류: {type(e).__name__}: {e}[/]")

    @work(thread=False)
    async def _fetch_menu_stats(self) -> None:
        """DB에 저장된 GNB 메뉴 통계를 조회한다."""
        log = self.query_one("#menu-log", RichLog)
        status = self.query_one("#menu-status", Static)
        log.clear()
        log.write("[bold cyan]DB 메뉴 통계 조회 중...[/]")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{API_BASE}/gnb/stats")
                resp.raise_for_status()
                data = resp.json()

            total = data.get("total", 0)
            active = data.get("active", 0)
            with_mobile = data.get("with_mobile_url", 0)
            mobile_pct = int(with_mobile / total * 100) if total > 0 else 0
            active_pct = int(active / total * 100) if total > 0 else 0

            status.update(
                f"통계: 전체 {total} | 활성 {active}({active_pct}%) | 모바일 {with_mobile}({mobile_pct}%)"
            )
            log.write(
                f"[bold green]전체:[/] {total}  "
                f"[bold green]활성:[/] {active} ({active_pct}%)  "
                f"[bold cyan]모바일:[/] {with_mobile} ({mobile_pct}%)"
            )

        except httpx.ConnectError:
            log.write("[bold red]연결 실패: MCP Client가 실행 중인지 확인하세요[/]")
        except Exception as e:
            log.write(f"[bold red]오류: {type(e).__name__}: {e}[/]")

    # ═══════════════════════════════════════════════════════════════════
    # Workers: Verify
    # ═══════════════════════════════════════════════════════════════════

    @work(thread=False)
    async def _refresh_verify_files(self) -> None:
        files = self._get_result_json_files()
        options = [(f"{f.name}  ({f.stat().st_size // 1024}KB)", f.name) for f in files]
        try:
            self.query_one("#verify-file-select", Select).set_options(options)
        except NoMatches:
            pass
        self._update_status_bar(f"검증 파일 목록 갱신: {len(files)}개")

    @work(thread=True)
    async def _run_docid_check(self) -> None:
        log = self.query_one("#verify-log", RichLog)
        status = self.query_one("#verify-status", Static)

        file_sel = self.query_one("#verify-file-select", Select)
        if file_sel.value is Select.BLANK:
            self.call_from_thread(log.clear)
            self.call_from_thread(log.write, "[bold red]파일을 먼저 선택하세요[/]")
            return

        filename = str(file_sel.value)
        file_path = RESULT_DIR / filename

        self.call_from_thread(log.clear)
        self.call_from_thread(status.update, f"docId 중복 검사 중... ({filename})")
        self.call_from_thread(self._reset_progress, "verify-progress")
        self.call_from_thread(self._start_indeterminate_progress, "verify-progress")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                self.call_from_thread(log.write, "[bold red]잘못된 파일 형식 (JSON 배열이 아닙니다)[/]")
                return

            doc_ids = [item.get("docId", "") for item in data]
            counter = Counter(doc_ids)
            duplicates = {k: v for k, v in counter.items() if v > 1}

            total = len(data)
            unique = len(set(doc_ids))
            dup_extra = sum(v - 1 for v in duplicates.values())

            self.call_from_thread(log.write, f"[bold cyan]━━━ docId 중복 검사 결과 ━━━[/]")
            self.call_from_thread(log.write, f"  파일: [bold]{filename}[/]")
            self.call_from_thread(log.write, f"  총 문서 수: [bold]{total}[/]")
            self.call_from_thread(log.write, f"  고유 docId 수: [bold]{unique}[/]")
            self.call_from_thread(log.write, f"  중복 docId 수: [bold]{len(duplicates)}[/]")
            self.call_from_thread(log.write, f"  중복으로 인한 추가 문서: [bold]{dup_extra}[/]")
            self.call_from_thread(log.write, "")

            if not duplicates:
                self.call_from_thread(log.write, "[bold green]✅ 중복된 docId 없음! 모든 docId가 고유합니다.[/]")
                self.call_from_thread(status.update, f"✅ 검사 완료 — 중복 없음 (총 {total}건)")
            else:
                self.call_from_thread(log.write, f"[bold yellow]⚠ 중복 docId {len(duplicates)}건 발견[/]")
                self.call_from_thread(log.write, "")

                for doc_id, count in sorted(duplicates.items(), key=lambda x: -x[1]):
                    self.call_from_thread(log.write, f"  [bold red]{doc_id}[/]: {count}회")
                    items = [item for item in data if item.get("docId") == doc_id]
                    for i, item in enumerate(items):
                        title = (item.get("title") or "N/A")[:60]
                        url = item.get("url", "N/A")
                        self.call_from_thread(log.write, f"    #{i+1} title: {title}")
                        self.call_from_thread(log.write, f"       url:   {url}")
                    self.call_from_thread(log.write, "")

                self.call_from_thread(
                    status.update,
                    f"⚠ 검사 완료 — 중복 {len(duplicates)}건 발견 (총 {total}건)",
                )

            self.call_from_thread(self._finish_progress, "verify-progress", not duplicates)

        except FileNotFoundError:
            self.call_from_thread(log.write, f"[bold red]파일을 찾을 수 없습니다: {filename}[/]")
            self.call_from_thread(self._finish_progress, "verify-progress", False)
        except json.JSONDecodeError as e:
            self.call_from_thread(log.write, f"[bold red]JSON 파싱 오류: {e}[/]")
            self.call_from_thread(self._finish_progress, "verify-progress", False)
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]오류: {type(e).__name__}: {e}[/]")
            self.call_from_thread(self._finish_progress, "verify-progress", False)

    # ═══════════════════════════════════════════════════════════════════
    # Workers: JSON Compare (Fix #1 파일목록 + Fix #3 프로그레스)
    # ═══════════════════════════════════════════════════════════════════

    @work(thread=False)
    async def _refresh_compare_files(self) -> None:
        files = self._get_result_json_files()
        options = [(f"{f.name}  ({f.stat().st_size // 1024}KB)", f.name) for f in files]

        for sel_id in ("#compare-file1", "#compare-file2"):
            try:
                self.query_one(sel_id, Select).set_options(options)
            except NoMatches:
                pass

        self._update_status_bar(f"비교 파일 목록 갱신: {len(files)}개")

    @work(thread=False)
    async def _run_json_compare(self) -> None:
        log = self.query_one("#compare-log", RichLog)
        status = self.query_one("#compare-status", Static)
        log.clear()
        self._reset_progress("compare-progress")

        file1_sel = self.query_one("#compare-file1", Select)
        file2_sel = self.query_one("#compare-file2", Select)

        file1 = file1_sel.value
        file2 = file2_sel.value

        if file1 is Select.BLANK or file2 is Select.BLANK:
            log.write("[bold red]두 파일을 모두 선택하세요[/]")
            return

        if file1 == file2:
            log.write("[bold yellow]서로 다른 파일을 선택하세요[/]")
            return

        status.update("JSON 파일 로딩 중...")
        log.write("[bold cyan]▶ JSON 비교 시작[/]")
        log.write(f"  파일 1 (이전): {file1}")
        log.write(f"  파일 2 (최신): {file2}")
        log.write("")

        self._start_indeterminate_progress("compare-progress")

        try:
            f1_path = RESULT_DIR / str(file1)
            f2_path = RESULT_DIR / str(file2)

            content1 = f1_path.read_text(encoding="utf-8")
            content2 = f2_path.read_text(encoding="utf-8")

            body = {
                "file1_name": str(file1),
                "file2_name": str(file2),
                "file1_content": content1,
                "file2_content": content2,
            }

            status.update("API로 비교 요청 중...")

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{API_BASE}/json-compare/compare", json=body)
                resp.raise_for_status()
                data = resp.json()

            task_id = data.get("task_id", "")
            status.update(f"비교 처리 중... (task: {task_id})")

            await self._poll_compare_task(task_id, log, status)

        except httpx.ConnectError:
            self._finish_progress("compare-progress", success=False)
            status.update("연결 실패")
            log.write("[bold red]연결 실패: MCP Client가 실행 중인지 확인하세요[/]")
        except FileNotFoundError as e:
            self._finish_progress("compare-progress", success=False)
            status.update("파일 없음")
            log.write(f"[bold red]파일을 찾을 수 없습니다: {e}[/]")
        except Exception as e:
            self._finish_progress("compare-progress", success=False)
            status.update(f"오류: {e}")
            log.write(f"[bold red]오류: {type(e).__name__}: {e}[/]")

    async def _poll_compare_task(
        self, task_id: str,
        log: RichLog, status: Static,
    ) -> None:
        while True:
            await asyncio.sleep(2)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(f"{API_BASE}/json-compare/task/{task_id}")
                    resp.raise_for_status()
                    data = resp.json()

                task_status = data.get("status", "unknown")

                if task_status == "completed":
                    result = data.get("result", {})
                    log.write("[bold green]━━━ 비교 완료 ━━━[/]")

                    summary = result.get("summary", {})
                    SUMMARY_LABELS = {
                        "total_file1": "파일1 문서 수",
                        "total_file2": "파일2 문서 수",
                        "added_count": "추가된 문서",
                        "removed_count": "삭제된 문서",
                        "modified_count": "변경된 문서",
                        "unchanged_count": "변경 없는 문서",
                    }
                    for key, val in summary.items():
                        label = SUMMARY_LABELS.get(key, key)
                        log.write(f"  {label}: [bold]{val}[/]")

                    await self._download_compare_pdf(task_id, log, status)
                    break

                elif task_status in ("failed", "error"):
                    self._finish_progress("compare-progress", success=False)
                    err = data.get("error_message", "알 수 없는 오류")
                    log.write(f"[bold red]━━━ 비교 실패 ━━━[/]")
                    log.write(f"  오류: {err}")
                    status.update(f"실패: {err}")
                    break

            except Exception as e:
                log.write(f"[dim yellow]  폴링 재시도... ({type(e).__name__})[/]")

    async def _download_compare_pdf(
        self, task_id: str,
        log: RichLog, status: Static,
    ) -> None:
        log.write("\n[cyan]PDF 리포트 다운로드 중...[/]")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{API_BASE}/json-compare/task/{task_id}/download")
                resp.raise_for_status()

            desktop = Path.home() / "Desktop"
            desktop.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H%M")
            pdf_path = desktop / f"report_{ts}.pdf"
            pdf_path.write_bytes(resp.content)

            self._finish_progress("compare-progress")
            status.update(f"완료 — PDF: ~/Desktop/{pdf_path.name}")
            log.write(f"[bold green]  PDF 저장 완료: {pdf_path}[/]")

        except Exception as e:
            self._finish_progress("compare-progress")
            status.update("비교 완료 (PDF 다운로드 실패)")
            log.write(f"[yellow]  PDF 다운로드 실패: {e}[/]")

    # ═══════════════════════════════════════════════════════════════════
    # Workers: Result Editor (Fix #1 파일목록)
    # ═══════════════════════════════════════════════════════════════════

    _editor_docs: list[dict] = []
    _editor_current_filename: str = ""
    _editor_current_doc_id: str = ""

    @work(thread=False)
    async def _refresh_editor_files(self) -> None:
        files = self._get_result_json_files()
        options = [(f"{f.name}  ({f.stat().st_size // 1024}KB)", f.name) for f in files]
        try:
            self.query_one("#editor-file-select", Select).set_options(options)
        except NoMatches:
            pass
        self._update_status_bar(f"에디터 파일 목록 갱신: {len(files)}개")

    @on(Select.Changed, "#editor-file-select")
    def on_editor_file_changed(self, event: Select.Changed) -> None:
        if event.value is not Select.BLANK:
            self._editor_current_filename = str(event.value)
            self._load_editor_file_docs(str(event.value))

    @work(thread=False)
    async def _load_editor_file_docs(self, filename: str) -> None:
        table = self.query_one("#editor-table", DataTable)
        table.clear()

        try:
            file_path = RESULT_DIR / filename
            if not file_path.exists():
                self._update_status_bar(f"파일을 찾을 수 없습니다: {filename}")
                return

            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                self._update_status_bar(f"잘못된 파일 형식: {filename}")
                return

            self._editor_docs = data

            for doc in data:
                doc_id = doc.get("docId", "")
                title = doc.get("title", "")[:40]
                url = doc.get("url", "")[:40]
                text_len = len(doc.get("text", ""))
                table.add_row(doc_id, title, url, str(text_len), key=doc_id)

            self._update_status_bar(f"{filename}: {len(data)}개 문서 로드")

        except Exception as e:
            self._update_status_bar(f"파일 로딩 오류: {e}")

    @work(thread=False)
    async def _search_editor_docs(self) -> None:
        query = self.query_one("#editor-search", Input).value.lower()
        filename = self._editor_current_filename

        if not filename:
            self._update_status_bar("파일을 먼저 선택하세요")
            return

        table = self.query_one("#editor-table", DataTable)
        table.clear()

        results = []
        for doc in self._editor_docs:
            doc_id = doc.get("docId", "")
            title = doc.get("title", "")
            text = doc.get("text", "")
            url = doc.get("url", "")

            if not query or (
                query in doc_id.lower()
                or query in title.lower()
                or query in text.lower()
                or query in url.lower()
            ):
                results.append(doc)
                table.add_row(
                    doc_id,
                    title[:40],
                    url[:40],
                    str(len(text)),
                    key=doc_id,
                )

        self._update_status_bar(f"검색 결과: {len(results)}건 ('{query}')")

    @work(thread=False)
    async def _load_editor_doc(self, row_key) -> None:
        doc_id = str(row_key)
        filename = self._editor_current_filename

        if not filename or not doc_id:
            return

        self._editor_current_doc_id = doc_id

        doc = next((d for d in self._editor_docs if d.get("docId") == doc_id), None)
        if not doc:
            self._update_status_bar(f"문서를 찾을 수 없습니다: {doc_id}")
            return

        title = doc.get("title", "")
        text = doc.get("text", "")
        url = doc.get("url", "")
        hierarchy = doc.get("hierarchy", [])

        try:
            title_label = self.query_one("#editor-doc-title", Static)
            hier_str = " > ".join(hierarchy) if hierarchy else ""
            info_parts = [f"[bold][{doc_id}][/] {title}"]
            if hier_str:
                info_parts.append(f"  경로: {hier_str}")
            info_parts.append(f"  URL: {url}")
            title_label.update("\n".join(info_parts))
        except NoMatches:
            pass

        try:
            textarea = self.query_one("#editor-textarea", TextArea)
            display_text = text.replace("\\n", "\n")
            textarea.load_text(display_text)
        except NoMatches:
            pass

        self._update_status_bar(f"문서 로딩: {doc_id}")

    @work(thread=False)
    async def _save_editor_doc(self) -> None:
        filename = self._editor_current_filename
        doc_id = self._editor_current_doc_id

        if not filename or not doc_id:
            self._update_status_bar("저장할 문서가 선택되지 않았습니다")
            return

        try:
            textarea = self.query_one("#editor-textarea", TextArea)
            new_text = textarea.text.replace("\n", "\\n")
        except NoMatches:
            return

        file_path = RESULT_DIR / filename
        if not file_path.exists():
            self._update_status_bar(f"파일을 찾을 수 없습니다: {filename}")
            return

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            doc_found = False
            for doc in data:
                if doc.get("docId") == doc_id:
                    doc["text"] = new_text
                    doc_found = True
                    break

            if not doc_found:
                self._update_status_bar(f"docId '{doc_id}'를 찾을 수 없습니다")
                return

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.stem}.bak_{ts}{file_path.suffix}"
            backup_path = file_path.parent / backup_name
            shutil.copy2(file_path, backup_path)

            file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            for d in self._editor_docs:
                if d.get("docId") == doc_id:
                    d["text"] = new_text
                    break

            self._update_status_bar(f"저장 완료: {doc_id} (백업: {backup_name})")

        except Exception as e:
            self._update_status_bar(f"저장 오류: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Utilities (Fix #4 - 오류 상세)
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _get_result_json_files() -> list[Path]:
        if not RESULT_DIR.exists():
            return []
        return sorted(RESULT_DIR.glob("data_*.json"), reverse=True)

    @staticmethod
    def _log_crawl_error(log: RichLog, err) -> None:
        """크롤링 실패 URL의 상세 오류를 로그에 출력"""
        if isinstance(err, dict):
            url = err.get("url", "?")
            error_type = err.get("error_type", err.get("type", ""))
            error_msg = err.get("error", err.get("message", err.get("detail", "알 수 없는 오류")))
            handler = err.get("handler", "")

            parts = [f"[red]  ✗ {url}[/]"]
            if error_type:
                parts.append(f"    유형: {error_type}")
            parts.append(f"    오류: {error_msg}")
            if handler:
                parts.append(f"    핸들러: {handler}")

            for p in parts:
                log.write(p)
        else:
            log.write(f"[red]  ✗ {err}[/]")

    @staticmethod
    def _log_http_error_detail(log: RichLog, exc: httpx.HTTPStatusError) -> None:
        """HTTP 에러 응답의 상세 내용을 로그에 출력"""
        try:
            body = exc.response.json()
            detail = body.get("detail", body)
            log.write(f"  상세: {detail}")
        except Exception:
            text = exc.response.text[:300]
            if text:
                log.write(f"  응답: {text}")


# ═══════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = CrawlerMindApp()
    app.run()
