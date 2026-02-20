#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git GUI Manager - 파이썬 Git 관리 도구 (DPI 대응 및 레이아웃 최적화 버전)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import subprocess
import os
import json
import threading
import ctypes
from datetime import datetime

# ────────────────────────────────────────────────
#  윈도우 고해상도(DPI) 대응 설정
# ────────────────────────────────────────────────
try:
    # Windows 8.1 이상에서 프로세스의 DPI 인식을 설정하여 글자/버튼 크기 왜곡 방지
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        # Windows 7 이하 대응
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ────────────────────────────────────────────────
#  설정 파일 경로
# ────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".git_gui_config.json")

# ────────────────────────────────────────────────
#  색상 / 폰트 테마
# ────────────────────────────────────────────────
COLORS = {
    "bg":          "#1E1E2E",
    "sidebar":     "#181825",
    "card":        "#313244",
    "accent":      "#CBA6F7",   # 라벤더 보라
    "accent2":     "#89B4FA",   # 파랑
    "green":       "#A6E3A1",
    "red":         "#F38BA8",
    "yellow":      "#F9E2AF",
    "text":        "#CDD6F4",
    "subtext":     "#6C7086",
    "border":      "#45475A",
    "input_bg":    "#262637",
    "btn_hover":   "#45475A",
    "log_bg":      "#11111B",
    "log_text":    "#A6E3A1",
    "log_err":     "#F38BA8",
    "log_info":    "#89B4FA",
}

FONT_MAIN  = ("Consolas", 10)
FONT_BOLD  = ("Consolas", 10, "bold")
FONT_TITLE = ("Consolas", 13, "bold")
FONT_SMALL = ("Consolas", 9)
FONT_LOG   = ("Consolas", 9)


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"repos": [], "last_repo": "", "global": {}}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def run_git(cmd, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        combined = "\n".join(filter(None, [out, err]))
        return result.returncode, combined
    except Exception as e:
        return -1, str(e)


class GitGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🐙  Git GUI Manager")
        self.geometry("1180x820")
        self.minsize(1000, 700)
        self.configure(bg=COLORS["bg"])
        self.config = load_config()
        self._apply_style()
        self._build_ui()
        self._refresh_repo_list()
        self._refresh_branches()

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        bg, fg, card = COLORS["bg"], COLORS["text"], COLORS["card"]
        acc = COLORS["accent"]

        style.configure("TFrame",        background=bg)
        style.configure("Card.TFrame",   background=card)
        style.configure("Sidebar.TFrame",background=COLORS["sidebar"])
        style.configure("TLabel",        background=bg, foreground=fg, font=FONT_MAIN)
        style.configure("Card.TLabel",   background=card, foreground=fg, font=FONT_MAIN)
        style.configure("Title.TLabel",  background=bg, foreground=acc, font=FONT_TITLE)
        style.configure("Sub.TLabel",    background=bg, foreground=COLORS["subtext"], font=FONT_SMALL)
        style.configure("CardSub.TLabel",background=card,foreground=COLORS["subtext"],font=FONT_SMALL)

        style.configure("Accent.TButton",
            background=acc, foreground="#1E1E2E",
            font=FONT_BOLD, relief="flat", borderwidth=0, padding=(12, 6))
        style.map("Accent.TButton",
            background=[("active", COLORS["accent2"])],
            foreground=[("active", "#1E1E2E")])

        style.configure("Action.TButton",
            background=COLORS["border"], foreground=fg,
            font=FONT_MAIN, relief="flat", borderwidth=0, padding=(8, 4))
        style.map("Action.TButton",
            background=[("active", "#585b70")])

        style.configure("Green.TButton",
            background=COLORS["green"], foreground="#1E1E2E",
            font=FONT_BOLD, relief="flat", borderwidth=0, padding=(8, 4))
        style.map("Green.TButton",
            background=[("active", "#86EFAC")])

        style.configure("Red.TButton",
            background=COLORS["red"], foreground="#1E1E2E",
            font=FONT_BOLD, relief="flat", borderwidth=0, padding=(8, 4))
        style.map("Red.TButton",
            background=[("active", "#FDA4AF")])

        style.configure("TEntry",
            fieldbackground=COLORS["input_bg"], foreground=fg,
            insertcolor=fg, borderwidth=1, relief="flat", font=FONT_MAIN)
        
        style.configure("TNotebook", background=COLORS["sidebar"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["sidebar"], foreground=COLORS["subtext"], font=FONT_MAIN, padding=(14, 8))
        style.map("TNotebook.Tab", background=[("selected", COLORS["bg"])], foreground=[("selected", acc)])

        style.configure("Treeview", background=COLORS["input_bg"], foreground=fg, fieldbackground=COLORS["input_bg"], rowheight=24, font=FONT_SMALL)
        style.configure("Treeview.Heading", background=COLORS["card"], foreground=acc, font=FONT_BOLD)

        style.configure("TRadiobutton", background=COLORS["sidebar"], foreground=fg, font=FONT_MAIN)
        style.map("TRadiobutton", background=[("active", COLORS["sidebar"])], foreground=[("active", acc)])
        style.configure("TPanedwindow", background=bg)

    def _build_ui(self):
        header = tk.Frame(self, bg=COLORS["sidebar"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🐙  Git GUI Manager", bg=COLORS["sidebar"], fg=COLORS["accent"], font=("Consolas", 14, "bold")).pack(side="left", padx=18, pady=10)
        self.status_label = tk.Label(header, text="", bg=COLORS["sidebar"], fg=COLORS["green"], font=FONT_SMALL)
        self.status_label.pack(side="right", padx=18)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=COLORS["sidebar"], width=270)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        sep = tk.Frame(body, bg=COLORS["border"], width=1)
        sep.pack(side="left", fill="y")

        main = tk.Frame(body, bg=COLORS["bg"])
        main.pack(side="left", fill="both", expand=True)
        self._build_main(main)

    def _build_sidebar(self, parent):
        tk.Label(parent, text="📁  로컬 저장소", bg=COLORS["sidebar"], fg=COLORS["accent"], font=FONT_BOLD).pack(anchor="w", padx=14, pady=(14,4))
        
        btn_row = tk.Frame(parent, bg=COLORS["sidebar"])
        btn_row.pack(fill="x", padx=10, pady=(0,6))
        ttk.Button(btn_row, text="＋", width=3, style="Green.TButton", command=self._add_repo).pack(side="left", padx=2)
        ttk.Button(btn_row, text="✕", width=3, style="Red.TButton", command=self._remove_repo).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🔄", width=3, style="Action.TButton", command=self._refresh_branches).pack(side="right", padx=2)

        self.repo_var = tk.StringVar()
        repo_canvas = tk.Canvas(parent, bg=COLORS["sidebar"], highlightthickness=0, height=180)
        repo_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=repo_canvas.yview)
        self.repo_frame = tk.Frame(repo_canvas, bg=COLORS["sidebar"])
        self.repo_frame.bind("<Configure>", lambda e: repo_canvas.configure(scrollregion=repo_canvas.bbox("all")))
        repo_canvas.create_window((0,0), window=self.repo_frame, anchor="nw")
        repo_canvas.configure(yscrollcommand=repo_scrollbar.set)
        repo_canvas.pack(fill="x", padx=4)

        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", padx=8, pady=10)
        tk.Label(parent, text="🌿  브랜치 목록", bg=COLORS["sidebar"], fg=COLORS["accent2"], font=FONT_BOLD).pack(anchor="w", padx=14, pady=(4,2))

        self.branch_listbox = tk.Listbox(parent, bg=COLORS["input_bg"], fg=COLORS["text"], selectbackground=COLORS["accent"], font=FONT_SMALL, relief="flat", borderwidth=0, height=10)
        self.branch_listbox.pack(fill="x", padx=10, pady=(0,4))
        self.branch_listbox.bind("<Double-Button-1>", self._checkout_branch_dbl)

        self.current_branch_label = tk.Label(parent, text="—", bg=COLORS["sidebar"], fg=COLORS["yellow"], font=FONT_BOLD)
        self.current_branch_label.pack(anchor="w", padx=14, pady=5)
        
        ttk.Button(parent, text="📂  폴더 열기", style="Action.TButton", command=self._open_folder).pack(fill="x", padx=10, pady=10)

    def _make_scrollable_tab(self, nb, title):
        outer = ttk.Frame(nb)
        nb.add(outer, text=title)
        
        # 캔버스 생성
        canvas = tk.Canvas(outer, bg=COLORS["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # 버튼들이 담길 실제 프레임
        content = tk.Frame(canvas, bg=COLORS["bg"])
        
        # 캔버스 안에 프레임 배치 및 ID 저장
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _on_frame_configure(event):
            # 내용물 크기에 맞춰 스크롤 영역 갱신
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            # 캔버스 너비가 변하면 내부 프레임 너비도 맞춤
            canvas.itemconfig(canvas_window, width=event.width)

        content.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        
        return content

    def _build_main(self, parent):
        # 상하 분할 (PanedWindow)
        paned = ttk.PanedWindow(parent, orient="vertical")
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        # 상단: 탭 영역 (명령어, 설정, 히스토리)
        top_frame = tk.Frame(paned, bg=COLORS["bg"])
        paned.add(top_frame, weight=1)

        nb = ttk.Notebook(top_frame)
        nb.pack(fill="both", expand=True)

        tab_cmd = self._make_scrollable_tab(nb, "  🚀  명령어  ")
        self._build_tab_commands(tab_cmd)
        tab_init = self._make_scrollable_tab(nb, "  ⚙️  설정  ")
        self._build_tab_init(tab_init)
        tab_log = self._make_scrollable_tab(nb, "  📜  히스토리  ")
        self._build_tab_log(tab_log)

        # 하단: CLI 및 로그
        bottom_frame = tk.Frame(paned, bg=COLORS["bg"])
        paned.add(bottom_frame, weight=1)

        cli_frame = tk.Frame(bottom_frame, bg=COLORS["bg"])
        cli_frame.pack(fill="x", pady=(4,6))
        
        tk.Label(cli_frame, text="💻 CLI:", bg=COLORS["bg"], fg=COLORS["accent"], font=FONT_BOLD).pack(side="left", padx=(4,8))
        self.cli_entry = ttk.Entry(cli_frame)
        self.cli_entry.pack(side="left", fill="x", expand=True)
        self.cli_entry.bind("<Return>", self._run_cli_command)
        ttk.Button(cli_frame, text="Run", style="Action.TButton", command=self._run_cli_command).pack(side="left", padx=6)

        log_frame = tk.Frame(bottom_frame, bg=COLORS["log_bg"])
        log_frame.pack(fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, bg=COLORS["log_bg"], fg=COLORS["log_text"], font=FONT_LOG, relief="flat")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_text.tag_config("err",  foreground=COLORS["log_err"])
        self.log_text.tag_config("cmd",  foreground=COLORS["yellow"])
        self.log_text.config(state="disabled")

    def _build_tab_commands(self, parent):
        # Grid 레이아웃 설정
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        # 1. Add & Commit
        add_card = self._card(parent, "📥  Add / Commit", lambda f: f.grid(row=0, column=0, sticky="nsew", padx=10, pady=10))
        
        ttk.Label(add_card, text="커밋 메시지:", style="Card.TLabel").pack(anchor="w", padx=8, pady=(4,0))
        self.commit_msg = ttk.Entry(add_card)
        self.commit_msg.pack(fill="x", padx=8, pady=4)
        
        btn_row = tk.Frame(add_card, bg=COLORS["card"])
        btn_row.pack(fill="x", padx=8, pady=4)
        ttk.Button(btn_row, text="add .", style="Action.TButton", command=lambda: self._exec("git add .")).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Commit", style="Accent.TButton", command=self._do_commit).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Add+Commit", style="Green.TButton", command=self._do_add_commit).pack(side="left", padx=2)

        # 2. Push / Pull
        pp_card = self._card(parent, "☁️  Push / Pull", lambda f: f.grid(row=0, column=1, sticky="nsew", padx=10, pady=10))
        
        for label, cmd in [("git push", "git push"), ("git pull", "git pull"), ("git fetch", "git fetch")]:
            ttk.Button(pp_card, text=label, style="Action.TButton", command=lambda c=cmd: self._exec(c)).pack(fill="x", padx=8, pady=2)

        # 3. 브랜치 관리
        br_card = self._card(parent, "🌿  브랜치 관리", lambda f: f.grid(row=1, column=0, sticky="nsew", padx=10, pady=10))
        
        self.branch_entry = ttk.Entry(br_card)
        self.branch_entry.insert(0, "test")
        self.branch_entry.pack(fill="x", padx=8, pady=4)
        
        ttk.Button(br_card, text="새 브랜치 생성 & 이동", style="Action.TButton", command=self._checkout_new_branch).pack(fill="x", padx=8, pady=2)
        ttk.Button(br_card, text="git merge (입력된 브랜치 합치기)", style="Action.TButton", command=self._do_merge).pack(fill="x", padx=8, pady=2)
        ttk.Button(br_card, text="git branch -d (삭제)", style="Action.TButton", command=self._delete_branch).pack(fill="x", padx=8, pady=2)
        ttk.Button(br_card, text="git branch -D (강제 삭제)", style="Red.TButton", command=self._force_delete_branch).pack(fill="x", padx=8, pady=2)

        # 4. 상태 및 복구
        st_card = self._card(parent, "🔍  상태 및 복구", lambda f: f.grid(row=1, column=1, sticky="nsew", padx=10, pady=10))
        
        for label, cmd in [("git status", "git status"), ("git diff", "git diff"), ("git checkout . (전체복구)", "git checkout ."), ("git reset HEAD~1", "git reset HEAD~1")]:
            ttk.Button(st_card, text=label, style="Action.TButton", command=lambda c=cmd: self._exec(c)).pack(fill="x", padx=8, pady=2)

        # 5. 기타 명령어
        etc_card = self._card(parent, "🎸  기타 명령어", lambda f: f.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10))
        ttk.Button(etc_card, text="git log --oneline", style="Action.TButton", command=lambda: self._exec("git log --oneline")).pack(fill="x", padx=8, pady=2)
        ttk.Button(etc_card, text="git status", style="Action.TButton", command=lambda: self._exec("git status")).pack(fill="x", padx=8, pady=2)

    def _build_tab_init(self, parent):
        card = self._card(parent, "🛠️  Git 초기화 / 사용자 설정", lambda f: f.pack(fill="x", padx=12, pady=12))
        
        ttk.Button(card, text="git init", style="Action.TButton", command=lambda: self._exec("git init")).pack(fill="x", padx=10, pady=2)
        
        for label, attr in [("이름:", "local_name"), ("이메일:", "local_email")]:
            row = tk.Frame(card, bg=COLORS["card"])
            row.pack(fill="x", padx=8, pady=3)
            ttk.Label(row, text=label, width=10, style="CardSub.TLabel").pack(side="left")
            e = ttk.Entry(row)
            e.pack(side="left", fill="x", expand=True, padx=4)
            setattr(self, attr, e)
        
        ttk.Button(card, text="사용자 정보 적용", style="Accent.TButton", command=self._set_local_user).pack(padx=10, pady=10)

        # 원격 저장소 설정 카드
        remote_card = self._card(parent, "🌐  원격 저장소 연결 / 초기 업로드", lambda f: f.pack(fill="x", padx=12, pady=12))
        
        ttk.Label(remote_card, text="원격 저장소 URL:", style="Card.TLabel").pack(anchor="w", padx=8, pady=(4,0))
        self.remote_url = ttk.Entry(remote_card)
        self.remote_url.pack(fill="x", padx=8, pady=4)

        ttk.Button(remote_card, text="git remote add origin (연결)", style="Action.TButton", command=self._remote_add).pack(fill="x", padx=8, pady=2)
        ttk.Button(remote_card, text="git branch -M main (브랜치명 변경)", style="Action.TButton", command=lambda: self._exec("git branch -M main")).pack(fill="x", padx=8, pady=2)
        ttk.Button(remote_card, text="git push -u origin main (초기 업로드)", style="Action.TButton", command=lambda: self._exec("git push -u origin main")).pack(fill="x", padx=8, pady=2)

        # .gitignore 관리
        ig_card = self._card(parent, "🙈  .gitignore 관리", lambda f: f.pack(fill="x", padx=12, pady=12))
        
        btn_row = tk.Frame(ig_card, bg=COLORS["card"])
        btn_row.pack(fill="x", padx=8, pady=4)
        ttk.Button(btn_row, text="불러오기", style="Action.TButton", command=self._load_gitignore).pack(side="left", padx=2)
        ttk.Button(btn_row, text="저장 (생성)", style="Accent.TButton", command=self._save_gitignore).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Python 기본값 추가", style="Action.TButton", command=self._add_python_gitignore).pack(side="right", padx=2)

        self.ignore_text = scrolledtext.ScrolledText(ig_card, height=6, bg=COLORS["input_bg"], fg=COLORS["text"], font=FONT_SMALL, relief="flat")
        self.ignore_text.pack(fill="x", padx=8, pady=(0,8))

        # Safe Directory
        safe_card = self._card(parent, "🔒  Safe Directory 설정", lambda f: f.pack(fill="x", padx=12, pady=12))
        ttk.Label(safe_card, text="소유자 권한 문제로 Git이 작동하지 않을 때 사용하세요.", style="CardSub.TLabel").pack(anchor="w", padx=8, pady=(4,4))
        ttk.Button(safe_card, text="현재 저장소 경로를 safe.directory에 추가", style="Action.TButton", command=self._add_safe_directory).pack(fill="x", padx=8, pady=2)

    def _build_tab_log(self, parent):
        header = tk.Frame(parent, bg=COLORS["bg"])
        header.pack(fill="x", padx=12, pady=10)
        ttk.Button(header, text="🔄 새로고침", style="Action.TButton", command=self._refresh_history).pack(side="right")

        cols = ("hash", "author", "date", "message")
        self.history_tree = ttk.Treeview(parent, columns=cols, show="headings", height=15)
        for col, width, label in [("hash", 80, "해시"), ("author", 100, "작성자"), ("date", 120, "날짜"), ("message", 500, "메시지")]:
            self.history_tree.heading(col, text=label)
            self.history_tree.column(col, width=width)
        self.history_tree.pack(fill="both", expand=True, padx=12)

    def _card(self, parent, title="", layout_func=None):
        outer = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)
        if layout_func:
            layout_func(outer)
        inner = tk.Frame(outer, bg=COLORS["card"])
        inner.pack(fill="both", expand=True)
        if title:
            tk.Label(inner, text=title, bg=COLORS["card"], fg=COLORS["accent2"], font=FONT_BOLD).pack(anchor="w", padx=8, pady=6)
            tk.Frame(inner, bg=COLORS["border"], height=1).pack(fill="x", padx=8, pady=(0,5))
        return inner

    def _refresh_repo_list(self):
        for w in self.repo_frame.winfo_children(): w.destroy()
        repos = self.config.get("repos", [])
        last = self.config.get("last_repo", "")
        for repo in repos:
            rb = ttk.Radiobutton(self.repo_frame, text=os.path.basename(repo), variable=self.repo_var, value=repo, style="TRadiobutton", command=self._on_repo_change)
            rb.pack(anchor="w", padx=8, pady=2)
        if last in repos: self.repo_var.set(last)

    def _on_repo_change(self):
        self.config["last_repo"] = self.repo_var.get()
        save_config(self.config)
        
        # 입력 필드 및 로그 초기화 (오작동 방지)
        self.commit_msg.delete(0, "end")
        self.branch_entry.delete(0, "end")
        self.branch_entry.insert(0, "test")
        self.remote_url.delete(0, "end")
        self.ignore_text.delete("1.0", "end")
        self.cli_entry.delete(0, "end")
        if hasattr(self, "local_name"): self.local_name.delete(0, "end")
        if hasattr(self, "local_email"): self.local_email.delete(0, "end")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        for row in self.history_tree.get_children(): self.history_tree.delete(row)

        self._refresh_branches()
        self._refresh_history()
        self._set_status(f"저장소 변경: {os.path.basename(self.repo_var.get())}")

    def _add_repo(self):
        path = filedialog.askdirectory()
        if path:
            path = os.path.normpath(path)
            repos = self.config.setdefault("repos", [])
            if path not in repos:
                repos.append(path)
                save_config(self.config)
                self._refresh_repo_list()
                self.repo_var.set(path)
                self._on_repo_change()

    def _remove_repo(self):
        sel = self.repo_var.get()
        if sel and sel in self.config.get("repos", []):
            self.config["repos"].remove(sel)
            save_config(self.config)
            self._refresh_repo_list()

    def _get_repo(self):
        repo = self.repo_var.get()
        if not repo or not os.path.isdir(repo):
            messagebox.showwarning("경고", "저장소를 선택하세요.")
            return None
        return repo

    def _refresh_branches(self):
        repo = self.repo_var.get()
        if not repo or not os.path.isdir(repo): return
        rc, out = run_git("git branch", cwd=repo)
        self.branch_listbox.delete(0, "end")
        current = "—"
        if rc == 0:
            for line in out.splitlines():
                if line.startswith("*"):
                    current = line[2:].strip()
                    self.branch_listbox.insert("end", f"★ {current}")
                else:
                    self.branch_listbox.insert("end", line.strip())
        self.current_branch_label.config(text=f"현재: {current}")

    def _checkout_branch_dbl(self, event):
        sel = self.branch_listbox.curselection()
        if sel:
            branch = self.branch_listbox.get(sel[0]).replace("★ ", "").strip()
            self._exec(f"git checkout {branch}")

    def _checkout_new_branch(self):
        b = self.branch_entry.get().strip()
        if b: self._exec(f"git checkout -b {b}")

    def _do_merge(self):
        b = self.branch_entry.get().strip()
        if b: self._exec(f"git merge {b}")

    def _delete_branch(self):
        b = self.branch_entry.get().strip()
        if b: self._exec(f"git branch -d {b}")

    def _force_delete_branch(self):
        b = self.branch_entry.get().strip()
        if b: self._exec(f"git branch -D {b}")

    def _exec(self, cmd, use_repo=True):
        repo = self._get_repo() if use_repo else None
        if use_repo and not repo: return
        self._log(f"$ {cmd}", "cmd")
        def run():
            rc, out = run_git(cmd, cwd=repo)
            self._log(out or "Done.", "err" if rc != 0 else "ok")
            self.after(0, self._refresh_branches)
        threading.Thread(target=run, daemon=True).start()

    def _do_commit(self):
        msg = self.commit_msg.get().strip()
        if msg: self._exec(f'git commit -m "{msg}"')

    def _do_add_commit(self):
        msg = self.commit_msg.get().strip()
        if msg:
            repo = self._get_repo()
            run_git("git add .", cwd=repo)
            self._exec(f'git commit -m "{msg}"')

    def _set_local_user(self):
        repo = self._get_repo()
        name = self.local_name.get().strip()
        email = self.local_email.get().strip()
        if name: run_git(f'git config user.name "{name}"', cwd=repo)
        if email: run_git(f'git config user.email "{email}"', cwd=repo)
        self._log("사용자 정보 설정 완료", "ok")

    def _remote_add(self):
        url = self.remote_url.get().strip()
        if url:
            self._exec(f"git remote add origin {url}")

    def _load_gitignore(self):
        repo = self._get_repo()
        if not repo: return
        path = os.path.join(repo, ".gitignore")
        self.ignore_text.delete("1.0", "end")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.ignore_text.insert("1.0", f.read())
                self._log(f".gitignore 불러오기 완료: {path}", "ok")
            except Exception as e:
                self._log(f"파일 읽기 오류: {e}", "err")
        else:
            self._log("현재 저장소에 .gitignore 파일이 없습니다.", "cmd")

    def _save_gitignore(self):
        repo = self._get_repo()
        if not repo: return
        content = self.ignore_text.get("1.0", "end-1c")
        path = os.path.join(repo, ".gitignore")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._log(f".gitignore 저장 완료: {path}", "ok")
        except Exception as e:
            self._log(f"파일 저장 오류: {e}", "err")

    def _add_python_gitignore(self):
        template = "\n# Python\n__pycache__/\n*.py[cod]\n*$py.class\n\n# Environments\n.env\n.venv/\nvenv/\nenv/\n\n# IDE\n.vscode/\n.idea/\n"
        self.ignore_text.insert("end", template)

    def _add_safe_directory(self):
        repo = self._get_repo()
        if not repo: return
        path = repo.replace("\\", "/")
        self._exec(f'git config --global --add safe.directory "{path}"', use_repo=False)

    def _refresh_history(self):
        repo = self._get_repo()
        if not repo: return
        rc, out = run_git('git log --oneline --format="%h||%an||%ad||%s" -n 30', cwd=repo)
        for row in self.history_tree.get_children(): self.history_tree.delete(row)
        if rc == 0:
            for line in out.splitlines():
                parts = line.split("||")
                if len(parts) == 4: self.history_tree.insert("", "end", values=tuple(parts))

    def _open_folder(self):
        repo = self._get_repo()
        if repo: os.startfile(repo) if os.name == "nt" else subprocess.Popen(["xdg-open", repo])

    def _run_cli_command(self, event=None):
        cmd = self.cli_entry.get().strip()
        if cmd:
            self._exec(cmd)
            self.cli_entry.delete(0, "end")

    def _log(self, msg, tag="ok"):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{msg}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _set_status(self, msg):
        self.status_label.config(text=msg)

if __name__ == "__main__":
    app = GitGUI()
    app.mainloop()