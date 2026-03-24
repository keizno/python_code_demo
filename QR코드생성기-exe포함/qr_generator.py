# -*- coding: utf-8 -*-
"""
QR코드 생성기 - 사내 배포용 v2
- 품질 등급 GUI 선택 (L / M / Q / H + 설명)
- PPTX 슬라이드 중앙 대형 삽입용 2000px / 300 DPI PNG
- PyInstaller --onefile 패키징 대응

## 설치 모듈 및 방법
- pip install "qrcode[pil]" Pillow pyinstaller
- 설명        : 패키지용도
  qrcode[pil]: QR코드생성
  Pillow     : 이미지 처리 / PNG 저장
  pyinstallerexe : 빌드할 때만 필요
  
- 빌드 명령은? (spec 파일 만든 다음 ...아래명령어.. spec파일은 spec빌드 사용)
  pyinstaller --clean -y qrcode.spec

"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, sys

import qrcode
from qrcode import constants as QC
from PIL import Image, ImageTk

# ── PyInstaller 리소스 경로 ───────────────────────────────────
def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

# ── 상수 ─────────────────────────────────────────────────────
APP_TITLE    = "QR코드 생성기 v1.0 by sungkb04@khnp.co.kr"
APP_W        = 560
PREVIEW_SIZE = 180
OUTPUT_PX    = 2000
OUTPUT_DPI   = (300, 300)

C_BG     = "#f0f2f5"
C_HDR    = "#1a2535"
C_ACC    = "#2563eb"
C_SAVE   = "#16a34a"
C_WHITE  = "#ffffff"
C_MUTED  = "#64748b"
C_BORDER = "#cbd5e1"

EC_OPTIONS = {
    "H  —  최고  (LTE·흔들림·반사 대응, 권장)": QC.ERROR_CORRECT_H,
    "Q  —  높음  (일반 실내 스캔)":             QC.ERROR_CORRECT_Q,
    "M  —  보통  (밝은 환경, URL 짧을 때)":     QC.ERROR_CORRECT_M,
    "L  —  낮음  (최소 크기 우선)":             QC.ERROR_CORRECT_L,
}
EC_DESC = {
    "H  —  최고  (LTE·흔들림·반사 대응, 권장)":
        "→ 데이터 30%까지 손상돼도 복원. 강의실·LTE 환경 최적.",
    "Q  —  높음  (일반 실내 스캔)":
        "→ 25% 복원. 조명 양호한 실내 프레젠테이션 적합.",
    "M  —  보통  (밝은 환경, URL 짧을 때)":
        "→ 15% 복원. URL이 짧고 환경이 이상적일 때.",
    "L  —  낮음  (최소 크기 우선)":
        "→ 7% 복원. QR 크기 우선 시에만 선택. 스캔 실패 가능.",
}

FG_LABELS = ["검정 (기본)", "남색",    "진녹색",  "진빨강",  "보라"]
FG_HEX    = ["#000000",    "#003580", "#145214", "#8b0000", "#4b0082"]
BG_LABELS = ["흰색 (기본)", "연노랑",   "연파랑",   "연회색"]
BG_HEX    = ["#ffffff",    "#fffde7", "#e3f2fd", "#f5f5f5"]


class QRApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.resizable(False, False)
        self.root.configure(bg=C_BG)
        self._qr_pil: Image.Image | None = None
        self._tk_img = None
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self):
        # pack 순서가 레이아웃을 결정함
        # side="top" 요소들은 위에서 아래로,
        # side="bottom" 요소들은 아래에서 위로 쌓임
        # → bottom 요소를 먼저 pack해야 절대 밀리지 않음

        # [1] 헤더 — 최상단 고정
        self._header()

        # [2] 상태바 — 최하단 고정 (bottom 중 가장 먼저)
        self._statusbar()

        # [3] 저장 버튼 — 상태바 바로 위 고정
        self._btn_save_fixed()

        # [4] 생성 버튼 — 저장 버튼 바로 위 고정
        self._btn_gen_fixed()

        # [5] 미리보기 — 생성 버튼 바로 위 고정
        self._preview_fixed()

        # [6] 설정 입력 영역 — 헤더와 미리보기 사이 남은 공간
        body = tk.Frame(self.root, bg=C_BG, padx=28, pady=10)
        body.pack(side="top", fill="both", expand=True)
        self._sec_url(body)
        self._sec_filename(body)
        self._sec_quality(body)
        self._sec_colors(body)

    def _header(self):
        f = tk.Frame(self.root, bg=C_HDR, pady=12)
        f.pack(side="top", fill="x")
        tk.Label(f, text="🔲  QR코드 생성기",
                 font=("맑은 고딕", 17, "bold"), bg=C_HDR, fg=C_WHITE).pack()
        tk.Label(f, text="PPTX 대형 삽입용 고해상도  |  LTE 모바일 스캔 최적화",
                 font=("맑은 고딕", 8), bg=C_HDR, fg="#94a3b8").pack(pady=(2, 0))

    def _statusbar(self):
        self.status_var = tk.StringVar(value="준비 완료")
        tk.Label(self.root, textvariable=self.status_var,
                 font=("맑은 고딕", 8), bg="#dde1e7", fg=C_MUTED,
                 anchor="w", padx=14, pady=4).pack(side="bottom", fill="x")

    def _btn_save_fixed(self):
        tk.Button(self.root,
                  text=f"💾   PNG 저장  ({OUTPUT_PX}×{OUTPUT_PX}px / 300 DPI — PPTX 대형 삽입 최적)",
                  font=("맑은 고딕", 10, "bold"),
                  bg=C_SAVE, fg=C_WHITE,
                  activebackground="#15803d", activeforeground=C_WHITE,
                  bd=0, pady=9, cursor="hand2",
                  command=self._save).pack(side="bottom", fill="x")

    def _btn_gen_fixed(self):
        tk.Button(self.root, text="▶   QR코드 생성",
                  font=("맑은 고딕", 12, "bold"),
                  bg=C_ACC, fg=C_WHITE,
                  activebackground="#1d4ed8", activeforeground=C_WHITE,
                  bd=0, pady=10, cursor="hand2",
                  command=self._generate).pack(side="bottom", fill="x",
                                               padx=28, pady=(0, 6))

    def _preview_fixed(self):
        outer = tk.Frame(self.root, bg="#dde1e8")
        outer.pack(side="bottom", pady=(0, 4))
        inner = tk.Frame(outer, bg=C_WHITE)
        inner.pack(padx=1, pady=1)
        # width/height 를 픽셀 단위로 고정 (propagate 방지)
        self.preview_lbl = tk.Label(inner,
                                    text="QR코드가 여기에 표시됩니다",
                                    font=("맑은 고딕", 9), bg=C_WHITE, fg="#aab0b8",
                                    width=26, height=10)
        self.preview_lbl.pack()
        # 라벨 크기가 이미지 크기에 따라 바뀌지 않도록 고정
        inner.pack_propagate(False)
        inner.config(width=PREVIEW_SIZE + 8, height=PREVIEW_SIZE + 8)

    # ── 설정 섹션 ─────────────────────────────────────────────
    def _lbl(self, p, t):
        tk.Label(p, text=t, font=("맑은 고딕", 9, "bold"),
                 bg=C_BG, fg=C_HDR).pack(anchor="w", pady=(6, 0))

    def _make_entry(self, p) -> tk.Entry:
        wrap = tk.Frame(p, bg=C_WHITE, highlightthickness=1,
                        highlightbackground=C_BORDER, highlightcolor=C_ACC)
        wrap.pack(fill="x", pady=(3, 0))
        e = tk.Entry(wrap, font=("맑은 고딕", 11), bd=0,
                     fg=C_HDR, bg=C_WHITE, insertbackground=C_ACC)
        e.pack(fill="x", padx=10, pady=7)
        return e

    def _sec_url(self, p):
        self._lbl(p, "링크 (URL)")
        self.url_entry = self._make_entry(p)
        self.url_entry.insert(0, "https://")

    def _sec_filename(self, p):
        self._lbl(p, "저장 파일명  (.png 자동 추가)")
        self.fn_entry = self._make_entry(p)
        self.fn_entry.insert(0, "qrcode")

    def _sec_quality(self, p):
        self._lbl(p, "오류 복원 등급  (스캔 품질)")
        wrap = tk.Frame(p, bg=C_WHITE, highlightthickness=1,
                        highlightbackground=C_BORDER, highlightcolor=C_ACC)
        wrap.pack(fill="x", pady=(3, 0))
        self.ec_var = tk.StringVar(value=list(EC_OPTIONS.keys())[0])
        cb = ttk.Combobox(wrap, textvariable=self.ec_var,
                          values=list(EC_OPTIONS.keys()),
                          font=("맑은 고딕", 10), state="readonly", width=52)
        cb.pack(padx=8, pady=6)
        self.ec_desc_lbl = tk.Label(p, text="", font=("맑은 고딕", 8),
                                    bg=C_BG, fg=C_MUTED, anchor="w")
        self.ec_desc_lbl.pack(fill="x", pady=(2, 0))
        cb.bind("<<ComboboxSelected>>", self._on_ec)
        self._on_ec()

        row = tk.Frame(p, bg=C_BG)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="여백 (Border):", font=("맑은 고딕", 9),
                 bg=C_BG, fg=C_MUTED).pack(side="left")
        self.border_var = tk.IntVar(value=4)
        ttk.Spinbox(row, from_=1, to=10, textvariable=self.border_var,
                    width=4, font=("맑은 고딕", 9)).pack(side="left", padx=6)
        tk.Label(row, text="(기본 4 권장)",
                 font=("맑은 고딕", 8), bg=C_BG, fg=C_MUTED).pack(side="left")

    def _on_ec(self, *_):
        self.ec_desc_lbl.config(text=EC_DESC.get(self.ec_var.get(), ""))

    def _sec_colors(self, p):
        self._lbl(p, "색상")
        row = tk.Frame(p, bg=C_BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text="QR 색상:", font=("맑은 고딕", 9),
                 bg=C_BG, fg=C_MUTED).grid(row=0, column=0, sticky="w")
        self.fg_var = tk.StringVar(value=FG_LABELS[0])
        ttk.Combobox(row, textvariable=self.fg_var, values=FG_LABELS,
                     width=14, font=("맑은 고딕", 9), state="readonly"
                     ).grid(row=0, column=1, padx=(4, 22), sticky="w")
        tk.Label(row, text="배경 색상:", font=("맑은 고딕", 9),
                 bg=C_BG, fg=C_MUTED).grid(row=0, column=2, sticky="w")
        self.bg_var = tk.StringVar(value=BG_LABELS[0])
        ttk.Combobox(row, textvariable=self.bg_var, values=BG_LABELS,
                     width=14, font=("맑은 고딕", 9), state="readonly"
                     ).grid(row=0, column=3, padx=4, sticky="w")

    # ── 로직 ─────────────────────────────────────────────────
    def _pick_hex(self, label, labels, hexes):
        try:
            return hexes[labels.index(label)]
        except ValueError:
            return hexes[0]

    def _generate(self):
        url = self.url_entry.get().strip()
        if not url or url in ("https://", "http://"):
            messagebox.showwarning("입력 오류", "URL을 입력해주세요.")
            return

        fg = self._pick_hex(self.fg_var.get(), FG_LABELS, FG_HEX)
        bg = self._pick_hex(self.bg_var.get(), BG_LABELS, BG_HEX)
        ec = EC_OPTIONS[self.ec_var.get()]

        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=ec,
                box_size=10,
                border=self.border_var.get(),
            )
            qr.add_data(url)
            qr.make(fit=True)

            img: Image.Image = qr.make_image(
                fill_color=fg, back_color=bg
            ).convert("RGBA")

            img = img.resize((OUTPUT_PX, OUTPUT_PX), Image.LANCZOS)
            self._qr_pil = img

            # 미리보기 — 고정 크기 박스 안에서만 업데이트
            thumb = img.copy()
            thumb.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
            self._tk_img = ImageTk.PhotoImage(thumb)
            self.preview_lbl.config(image=self._tk_img, text="",
                                    width=PREVIEW_SIZE, height=PREVIEW_SIZE)

            grade = self.ec_var.get().split("—")[0].strip()
            self.status_var.set(
                f"✅  생성 완료  |  등급: {grade}  |  "
                f"{OUTPUT_PX}×{OUTPUT_PX}px  |  {url[:50]}"
            )

        except Exception as e:
            messagebox.showerror("생성 오류", f"QR코드 생성 실패:\n{e}")

    def _save(self):
        if self._qr_pil is None:
            messagebox.showwarning("저장 오류", "먼저 QR코드를 생성해주세요.")
            return

        fn = self.fn_entry.get().strip() or "qrcode"
        if not fn.lower().endswith(".png"):
            fn += ".png"

        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 이미지", "*.png")],
            initialfile=fn,
            title="QR코드 저장",
        )
        if not path:
            return

        try:
            self._qr_pil.convert("RGB").save(path, "PNG", dpi=OUTPUT_DPI)
            self.status_var.set(f"💾  저장 완료  →  {path}")
            messagebox.showinfo(
                "저장 완료",
                f"저장 위치:\n{path}\n\n"
                f"• 해상도: {OUTPUT_PX}×{OUTPUT_PX}px  /  300 DPI\n"
                f"• PPT 삽입 후 슬라이드 중앙 배치 → 자유롭게 크기 조절\n"
                f"• 8cm 이상으로 키워도 깨짐 없음"
            )
        except Exception as e:
            messagebox.showerror("저장 오류", f"저장 실패:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconbitmap(resource_path("qr_icon.ico"))
    except Exception:
        pass
    QRApp(root)
    root.mainloop()
