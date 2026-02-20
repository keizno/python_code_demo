import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.font as tkfont
import yt_dlp
import time
import re

# ──────────────────────────────────────────────
#  색상 팔레트 (다크 + 네온 포인트)
# ──────────────────────────────────────────────
BG_MAIN      = "#0d0f14"
BG_PANEL     = "#13161e"
BG_CARD      = "#1a1d28"
BG_ENTRY     = "#0d0f14"
BORDER       = "#2a2d3a"
ACCENT       = "#00e5a0"       # 민트 네온
ACCENT_DIM   = "#00b87a"
RED          = "#ff4d6a"
YELLOW       = "#ffd166"
TEXT_MAIN    = "#e8eaf0"
TEXT_SUB     = "#6b7280"
TEXT_LOG     = "#9ba3b2"
BAR_TRACK    = "#1e2130"
BAR_FILL     = "#00e5a0"

FONT_TITLE   = ("Courier New", 18, "bold")
FONT_LABEL   = ("Courier New", 9, "bold")
FONT_ENTRY   = ("Consolas", 10)
FONT_BTN     = ("Courier New", 10, "bold")
FONT_LOG     = ("Consolas", 9)
FONT_STATUS  = ("Courier New", 10)
FONT_PERCENT = ("Courier New", 20, "bold")


def parse_progress(d):
    """yt-dlp progress hook 데이터에서 (percent, speed, eta) 파싱"""
    percent = 0.0
    speed   = ""
    eta     = ""
    if d.get("status") == "downloading":
        total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded = d.get("downloaded_bytes", 0)
        if total:
            percent = downloaded / total * 100
        raw_speed = d.get("speed") or 0
        if raw_speed:
            if raw_speed > 1_048_576:
                speed = f"{raw_speed/1_048_576:.1f} MB/s"
            else:
                speed = f"{raw_speed/1024:.0f} KB/s"
        raw_eta = d.get("eta") or 0
        if raw_eta:
            m, s = divmod(int(raw_eta), 60)
            eta = f"{m:02d}:{s:02d}"
    return percent, speed, eta


class GlowCanvas(tk.Canvas):
    """네온 글로우 효과용 캔버스 헬퍼"""
    def draw_glow_rect(self, x1, y1, x2, y2, color, layers=4, radius=8):
        for i in range(layers, 0, -1):
            offset = i * 2
            alpha_color = color  # tkinter는 rgba 미지원, 단순 오버레이로 대체
            self.create_rectangle(
                x1 - offset, y1 - offset, x2 + offset, y2 + offset,
                outline=color, width=1,
                stipple="gray25" if i > 2 else "gray50"
            )


class ProgressBar(tk.Canvas):
    """커스텀 진행바 위젯"""
    def __init__(self, parent, **kwargs):
        self.bar_height = kwargs.pop("bar_height", 8)
        super().__init__(parent, height=self.bar_height, bg=BG_MAIN,
                         highlightthickness=0, **kwargs)
        self._percent = 0
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, percent):
        self._percent = max(0.0, min(100.0, percent))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.bar_height
        r = h // 2

        # 트랙
        self.create_rounded_rect(0, 0, w, h, r, fill=BAR_TRACK, outline="")

        # 채워진 부분
        filled = int(w * self._percent / 100)
        if filled > r * 2:
            self.create_rounded_rect(0, 0, filled, h, r, fill=BAR_FILL, outline="")
        elif filled > 0:
            self.create_oval(0, 0, h, h, fill=BAR_FILL, outline="")

        # 글로우 레이어 (밝은 흰 하이라이트)
        if filled > r * 2:
            self.create_rounded_rect(2, 1, filled - 2, h // 2, r // 2,
                                     fill="#80ffd4", outline="", stipple="gray50")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1 + r, y1,
            x2 - r, y1,
            x2,     y1,
            x2,     y1 + r,
            x2,     y2 - r,
            x2,     y2,
            x2 - r, y2,
            x1 + r, y2,
            x1,     y2,
            x1,     y2 - r,
            x1,     y1 + r,
            x1,     y1,
        ]
        return self.create_polygon(pts, smooth=True, **kw)


class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YT-DLP  ·  MP4 Downloader")
        self.root.geometry("680x660")
        self.root.configure(bg=BG_MAIN)
        self.root.resizable(False, False)

        self._downloading = False
        self._log_lines = 0
        self._blink_after = None

        self._build_ui()

    # ──────────────────────── UI 빌드 ────────────────────────

    def _build_ui(self):
        root = self.root

        # ── 상단 헤더 ──
        header = tk.Frame(root, bg=BG_MAIN)
        header.pack(fill="x", padx=30, pady=(28, 0))

        tk.Label(header, text="▶  YT-DLP DOWNLOADER",
                 font=FONT_TITLE, fg=ACCENT, bg=BG_MAIN).pack(side="left")

        self.dot = tk.Label(header, text="●", font=("Courier New", 12),
                            fg=TEXT_SUB, bg=BG_MAIN)
        self.dot.pack(side="right", padx=(0, 4))
        tk.Label(header, text="IDLE", font=FONT_LABEL,
                 fg=TEXT_SUB, bg=BG_MAIN).pack(side="right")

        # 구분선
        tk.Frame(root, height=1, bg=BORDER).pack(fill="x", padx=30, pady=(14, 0))

        # ── URL 입력 카드 ──
        url_card = tk.Frame(root, bg=BG_CARD, padx=20, pady=16)
        url_card.pack(fill="x", padx=30, pady=(18, 0))

        tk.Label(url_card, text="URL", font=FONT_LABEL,
                 fg=ACCENT, bg=BG_CARD).pack(anchor="w")

        url_row = tk.Frame(url_card, bg=BG_CARD)
        url_row.pack(fill="x", pady=(6, 0))

        self.url_entry = tk.Entry(url_row, font=FONT_ENTRY,
                                  bg=BG_ENTRY, fg=TEXT_MAIN,
                                  insertbackground=ACCENT,
                                  relief="flat", bd=0)
        self.url_entry.pack(side="left", fill="x", expand=True,
                            ipady=8, ipadx=8)
        self.url_entry.insert(0, "https://")

        self._paste_btn = self._make_btn(url_row, "PASTE",
                                         self._paste_url, small=True)
        self._paste_btn.pack(side="left", padx=(8, 0))

        # 구분선
        tk.Frame(url_card, height=1, bg=BORDER).pack(fill="x", pady=(10, 0))

        # ── 저장 경로 ──
        tk.Label(url_card, text="SAVE TO", font=FONT_LABEL,
                 fg=ACCENT, bg=BG_CARD).pack(anchor="w", pady=(10, 0))

        path_row = tk.Frame(url_card, bg=BG_CARD)
        path_row.pack(fill="x", pady=(6, 0))

        self.path_var = tk.StringVar(value=os.getcwd())
        self.path_entry = tk.Entry(path_row, textvariable=self.path_var,
                                   font=FONT_ENTRY, bg=BG_ENTRY,
                                   fg=TEXT_SUB, insertbackground=ACCENT,
                                   state="readonly", relief="flat", bd=0)
        self.path_entry.pack(side="left", fill="x", expand=True,
                             ipady=8, ipadx=8)

        self._folder_btn = self._make_btn(path_row, "BROWSE",
                                          self.select_directory, small=True)
        self._folder_btn.pack(side="left", padx=(8, 0))

        # ── 다운로드 버튼 ──
        btn_frame = tk.Frame(root, bg=BG_MAIN)
        btn_frame.pack(pady=(20, 0))

        self.download_btn = self._make_btn(
            btn_frame, "▶  START DOWNLOAD", self.start_download_thread,
            width=28, height=2)
        self.download_btn.pack()

        # ── 진행상황 카드 ──
        prog_card = tk.Frame(root, bg=BG_CARD, padx=20, pady=16)
        prog_card.pack(fill="x", padx=30, pady=(18, 0))

        prog_top = tk.Frame(prog_card, bg=BG_CARD)
        prog_top.pack(fill="x")

        self.status_lbl = tk.Label(prog_top, text="IDLE",
                                   font=FONT_STATUS, fg=TEXT_SUB, bg=BG_CARD)
        self.status_lbl.pack(side="left")

        self.percent_lbl = tk.Label(prog_top, text="0%",
                                    font=FONT_PERCENT, fg=ACCENT, bg=BG_CARD)
        self.percent_lbl.pack(side="right")

        self.progress_bar = ProgressBar(prog_card, bar_height=10)
        self.progress_bar.pack(fill="x", pady=(10, 8))
        self.progress_bar.configure(bg=BG_CARD)

        meta_row = tk.Frame(prog_card, bg=BG_CARD)
        meta_row.pack(fill="x")
        self.speed_lbl  = tk.Label(meta_row, text="", font=FONT_LABEL,
                                   fg=YELLOW, bg=BG_CARD)
        self.speed_lbl.pack(side="left")
        self.eta_lbl    = tk.Label(meta_row, text="", font=FONT_LABEL,
                                   fg=TEXT_SUB, bg=BG_CARD)
        self.eta_lbl.pack(side="right")

        # ── 로그 카드 ──
        log_card = tk.Frame(root, bg=BG_CARD, padx=20, pady=12)
        log_card.pack(fill="both", expand=True, padx=30, pady=(12, 24))

        log_header = tk.Frame(log_card, bg=BG_CARD)
        log_header.pack(fill="x")

        tk.Label(log_header, text="LOG", font=FONT_LABEL,
                 fg=ACCENT, bg=BG_CARD).pack(side="left")

        clear_btn = tk.Label(log_header, text="CLEAR", font=FONT_LABEL,
                             fg=TEXT_SUB, bg=BG_CARD, cursor="hand2")
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: self._clear_log())

        log_frame = tk.Frame(log_card, bg=BG_ENTRY)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))

        self.log_text = tk.Text(log_frame, font=FONT_LOG,
                                bg=BG_ENTRY, fg=TEXT_LOG,
                                relief="flat", bd=0,
                                insertbackground=ACCENT,
                                state="disabled",
                                wrap="word",
                                padx=8, pady=8,
                                height=8)
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview,
                                 bg=BG_CARD, troughcolor=BG_ENTRY,
                                 relief="flat", bd=0)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 로그 태그 색상
        self.log_text.tag_configure("ok",    foreground=ACCENT)
        self.log_text.tag_configure("err",   foreground=RED)
        self.log_text.tag_configure("warn",  foreground=YELLOW)
        self.log_text.tag_configure("info",  foreground=TEXT_LOG)
        self.log_text.tag_configure("ts",    foreground=TEXT_SUB)

        self._log("시스템 준비 완료. URL을 입력하고 다운로드를 시작하세요.", "ok")

    # ──────────────────────── 헬퍼 위젯 ────────────────────────

    def _make_btn(self, parent, text, cmd, small=False, width=None, height=1):
        kw = dict(
            text=text, command=cmd,
            font=FONT_BTN,
            bg=BG_CARD, fg=ACCENT,
            activebackground=ACCENT, activeforeground=BG_MAIN,
            relief="flat", bd=0,
            cursor="hand2",
            height=height,
            padx=12 if small else 20,
            pady=4  if small else 8,
        )
        if width:
            kw["width"] = width
        btn = tk.Button(parent, **kw)

        def on_enter(e):
            btn.config(bg=ACCENT, fg=BG_MAIN)
        def on_leave(e):
            btn.config(bg=BG_CARD, fg=ACCENT)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    # ──────────────────────── 액션 ────────────────────────

    def _paste_url(self):
        try:
            text = self.root.clipboard_get()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, text.strip())
            self._log(f"클립보드에서 붙여넣기: {text.strip()[:60]}...", "info")
        except Exception:
            pass

    def select_directory(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(folder)
            self._log(f"저장 경로 변경: {folder}", "info")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        self._log_lines = 0

    def _log(self, message, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"[{ts}] ", "ts")
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)
        self._log_lines += 1

    def _set_status(self, text, color=TEXT_SUB):
        self.status_lbl.config(text=text.upper(), fg=color)

    def _set_percent(self, pct):
        self.percent_lbl.config(text=f"{pct:.1f}%")
        self.progress_bar.set(pct)

    def _blink_dot(self):
        """다운로드 중 상태 표시 점 깜빡임"""
        if not self._downloading:
            self.dot.config(fg=TEXT_SUB)
            return
        current = self.dot.cget("fg")
        next_color = ACCENT if current != ACCENT else TEXT_SUB
        self.dot.config(fg=next_color)
        self._blink_after = self.root.after(600, self._blink_dot)

    def start_download_thread(self):
        url  = self.url_entry.get().strip()
        path = self.path_var.get()

        if not url or url == "https://":
            messagebox.showwarning("경고", "URL을 입력해주세요.")
            return

        self._downloading = True
        self.download_btn.config(state=tk.DISABLED, text="⏳  DOWNLOADING...")
        self._set_status("다운로드 준비 중...", YELLOW)
        self._set_percent(0)
        self.speed_lbl.config(text="")
        self.eta_lbl.config(text="")
        self._log(f"다운로드 시작: {url[:70]}", "warn")
        self._blink_dot()

        t = threading.Thread(target=self.run_download, args=(url, path), daemon=True)
        t.start()

    def run_download(self, url, path):
        def progress_hook(d):
            if d["status"] == "downloading":
                pct, speed, eta = parse_progress(d)
                self.root.after(0, self._update_progress, pct, speed, eta)
                # 로그: 1% 단위로만 출력 (너무 많아지지 않게)
                if int(pct) % 10 == 0 and pct > 0:
                    fname = d.get("filename", "")
                    self.root.after(0, self._log,
                                    f"{pct:.0f}%  {speed}  ETA {eta}  ← {os.path.basename(fname)}", "info")
            elif d["status"] == "finished":
                self.root.after(0, self._update_progress, 100, "", "")
                self.root.after(0, self._log, "병합 / 변환 중...", "warn")

        def postprocessor_hook(d):
            if d.get("status") == "started":
                pp = d.get("postprocessor", "")
                self.root.after(0, self._log, f"후처리: {pp}", "info")

        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(path, "%(title)s.%(ext)s"),
            "restrictfilenames": False,
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
            "quiet": True,
            "no_warnings": False,
            "logger": _YTLogger(self._log_safe),
        }

        success = False
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                dur   = info.get("duration_string", "?")
                self.root.after(0, self._log, f"제목: {title}", "ok")
                self.root.after(0, self._log, f"길이: {dur}", "info")
                self.root.after(0, self._set_status, "다운로드 중...", YELLOW)
                ydl.download([url])
            success = True
        except Exception as e:
            self.root.after(0, self._log, f"오류 발생: {e}", "err")

        self.root.after(0, self._on_download_done, success, path)

    def _log_safe(self, msg, tag="info"):
        """스레드에서 안전하게 로그 추가"""
        self.root.after(0, self._log, msg, tag)

    def _update_progress(self, pct, speed, eta):
        self._set_percent(pct)
        self._set_status(f"다운로드 중... {pct:.1f}%", YELLOW)
        self.speed_lbl.config(text=speed)
        self.eta_lbl.config(text=f"남은 시간  {eta}" if eta else "")

    def _on_download_done(self, success, path):
        self._downloading = False
        if self._blink_after:
            self.root.after_cancel(self._blink_after)
        self.dot.config(fg=ACCENT if success else RED)

        if success:
            self._set_status("완료!", ACCENT)
            self._set_percent(100)
            self._log("✔  다운로드 완료!", "ok")
            self._log(f"저장 위치: {path}", "info")
            messagebox.showinfo("완료", f"다운로드가 완료되었습니다.\n\n{path}")
        else:
            self._set_status("오류 발생", RED)
            self._log("✘  다운로드 실패. 위 로그를 확인하세요.", "err")
            messagebox.showerror("오류", "다운로드 중 오류가 발생했습니다.\n로그를 확인하세요.")

        self.download_btn.config(state=tk.NORMAL, text="▶  START DOWNLOAD")
        self.download_btn.configure(bg=BG_CARD, fg=ACCENT)


# ──────────────────────────────────────────────
#  yt-dlp 로거 래퍼
# ──────────────────────────────────────────────

class _YTLogger:
    def __init__(self, log_fn):
        self._log = log_fn

    def debug(self, msg):
        if msg.startswith("[debug]"):
            return
        self._log(msg, "info")

    def info(self, msg):
        self._log(msg, "info")

    def warning(self, msg):
        self._log(msg, "warn")

    def error(self, msg):
        self._log(msg, "err")


# ──────────────────────────────────────────────
#  진입점
# ──────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = DownloaderApp(root)
    root.mainloop()
