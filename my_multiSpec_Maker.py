# -*- coding: utf-8 -*-
"""
PyInstaller Multi-Spec Maker v4.0
- Enhanced module detection with AST parsing
- Flexible build options (collect_all, console, one-file)
- Smart package management with pip install helper
- Support for individual icons per executable
"""

import os
import sys
import ast
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
import re
import subprocess
import threading
import json
from pathlib import Path

class PyInstallerSpecMerger:
    def __init__(self, master):
        self.master = master
        master.title("PyInstaller Multi-Spec/EXE Maker v4.0 - Enhanced by sungkb04@khnp.co.kr")
        
        self.current_dir = os.getcwd()
        # 환경설정 파일을 Windows 사용자 홈폴더에 저장
        home_dir = os.path.expanduser('~')
        self.config_file = os.path.join(home_dir, '.spec_maker_config.json')
        
        # 창 크기 및 위치 설정 (저장된 크기 또는 기본값)
        window_width, window_height, pos_x, pos_y = self._load_window_config()
        master.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
        
        # 창이 화면 밖으로 나가지 않도록 조정
        master.update_idletasks()  # 창 크기를 실제로 반영
        self._ensure_window_on_screen(master)
        
        # 앱 아이콘 설정 (build.ico) - exe 변환 후에도 인식 가능
        icon_path = self._get_resource_path('build.ico')
        if icon_path and os.path.isfile(icon_path):
            try:
                master.iconbitmap(icon_path)
                self._icon_path = icon_path
            except Exception as e:
                print(f"⚠️  Warning: Failed to set icon: {e}")
                self._icon_path = None
        else:
            self._icon_path = None
        
        # 창 크기 변경 및 종료 시 저장
        master.bind('<Configure>', self._save_window_size_on_change)
        
        # 다른 데이터 구조
        self.selected_files = []  # [(py_path, icon_path), ...]
        self.data_files = []  # [(src, dst), ...]
        self.hiddenimports = set()  # 자동 탐지된 모듈
        self.manual_hiddenimports = []  # 수동 추가 모듈
        self.file_imports = {}  # ← 파일별 모듈 저장용 {py_path: {"ast": set(), "dynamic": set()}}
        self.spec_path = tk.StringVar(value=os.path.join(self.current_dir, 'merged.spec'))
        
        # 빌드 옵션
        self.use_collect_all = tk.BooleanVar(value=True)
        self.console_mode = tk.BooleanVar(value=False)
        self.onefile_mode = tk.BooleanVar(value=False)
        self.optimize_size = tk.BooleanVar(value=False)  # 용량 최적화 옵션
        self.exclude_tests = tk.BooleanVar(value=True)   # 테스트 파일 제외
        
        # 패키지 이름 매핑
        self.package_mapping = {
            'PIL': 'Pillow',
            'cv2': 'opencv-python',
            'sklearn': 'scikit-learn',
            'yaml': 'PyYAML',
            'dateutil': 'python-dateutil',
            'serial': 'pyserial',
            'psutil': 'psutil',
            'win32com': 'pywin32',
            'win32api': 'pywin32',
            'win32con': 'pywin32',
            'pywintypes': 'pywin32',
            'pythoncom': 'pywin32',
            'xlrd': 'xlrd',
            'xlwt': 'xlwt',
            'openpyxl': 'openpyxl',
            'docx': 'python-docx',
            'pptx': 'python-pptx',
            'bs4': 'beautifulsoup4',
            'telegram': 'python-telegram-bot',
        }
        
        # collect_all이 필요한 복잡한 패키지들
        self.collect_all_packages = {
            'scipy', 'numpy', 'pandas', 'matplotlib', 'sklearn', 
            'torch', 'tensorflow', 'keras', 'cv2', 'PIL'
        }

        self._build_ui()

    def _build_ui(self):
        # ========== Python 파일 섹션 ==========
        tk.Label(self.master, text="Selected Python Files:", font=("Arial", 10, "bold")).pack(pady=(5, 0), anchor="w", padx=10)
        self.files_frame = tk.Frame(self.master)
        self.files_frame.pack(padx=10, pady=2, fill=tk.X)
        
        file_btns = tk.Frame(self.files_frame)
        file_btns.pack(side=tk.RIGHT)
        
        files_sb = tk.Scrollbar(self.files_frame)
        files_sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.files_listbox = tk.Listbox(self.files_frame, width=70, height=3, yscrollcommand=files_sb.set)
        self.files_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        files_sb.config(command=self.files_listbox.yview)
        
        tk.Button(file_btns, text="Add Files", command=self.add_files, width=12).pack(fill=tk.X, pady=1)
        tk.Button(file_btns, text="Remove Selected", command=self.remove_selected, width=12).pack(fill=tk.X, pady=1)
        tk.Button(file_btns, text="Set Icon", command=self.set_icon_for_selected, width=12).pack(fill=tk.X, pady=1)
        tk.Button(file_btns, text="Scan Modules", command=self.scan_all_modules, 
                 bg="#4CAF50", fg="white", width=12).pack(fill=tk.X, pady=1)

        # ========== 데이터 파일 섹션 ==========
        tk.Label(self.master, text="Data Files:", font=("Arial", 10, "bold")).pack(pady=(5, 0), anchor="w", padx=10)
        self.data_files_frame = tk.Frame(self.master)
        self.data_files_frame.pack(padx=10, pady=2, fill=tk.X)
        
        data_btns = tk.Frame(self.data_files_frame)
        data_btns.pack(side=tk.RIGHT)
        
        data_sb = tk.Scrollbar(self.data_files_frame)
        data_sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.data_files_listbox = tk.Listbox(self.data_files_frame, width=70, height=3, yscrollcommand=data_sb.set)
        self.data_files_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        data_sb.config(command=self.data_files_listbox.yview)
        
        tk.Button(data_btns, text="Add Data Files", command=self.add_data_files, width=12).pack(fill=tk.X, pady=1)
        tk.Button(data_btns, text="Add Data Folder", command=self.add_data_folder, width=12).pack(fill=tk.X, pady=1)
        tk.Button(data_btns, text="Remove Selected", command=self.remove_selected_data, width=12).pack(fill=tk.X, pady=1)

        # ========== Hidden Imports 섹션 ==========
        tk.Label(self.master, text="Hidden Imports (Auto-detected + Manual):", 
                font=("Arial", 10, "bold")).pack(pady=(5, 0), anchor="w", padx=10)
        self.hiddenimports_frame = tk.Frame(self.master)
        self.hiddenimports_frame.pack(padx=10, pady=2, fill=tk.X)
        
        hidden_btns = tk.Frame(self.hiddenimports_frame)
        hidden_btns.pack(side=tk.RIGHT)
        
        hidden_sb = tk.Scrollbar(self.hiddenimports_frame)
        hidden_sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.hiddenimports_listbox = tk.Listbox(self.hiddenimports_frame, width=70, height=3, yscrollcommand=hidden_sb.set)
        self.hiddenimports_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        hidden_sb.config(command=self.hiddenimports_listbox.yview)
        
        tk.Button(hidden_btns, text="Add Manual", command=self.add_manual_hiddenimport, width=12).pack(fill=tk.X, pady=1)
        tk.Button(hidden_btns, text="Remove", command=self.remove_hiddenimport, width=12).pack(fill=tk.X, pady=1)
        tk.Button(hidden_btns, text="Clear All", command=self.clear_hiddenimports, width=12).pack(fill=tk.X, pady=1)

        # ========== 빌드 옵션 섹션 ==========
        options_frame = tk.LabelFrame(self.master, text="Build Options", 
                                     font=("Arial", 10, "bold"), padx=10, pady=5)
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Frame for columns
        opt_container = tk.Frame(options_frame)
        opt_container.pack(fill=tk.X)
        
        # Left Column
        left_col = tk.Frame(opt_container)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Checkbutton(left_col, 
                      text="✓ Use collect_all (safer, larger)", 
                      variable=self.use_collect_all,
                      font=("Arial", 9)).pack(anchor=tk.W)
        tk.Checkbutton(left_col, 
                      text="✓ Console mode (debug)", 
                      variable=self.console_mode,
                      font=("Arial", 9)).pack(anchor=tk.W)
        tk.Checkbutton(left_col, 
                      text="✓ One-file mode (single .exe)", 
                      variable=self.onefile_mode,
                      font=("Arial", 9)).pack(anchor=tk.W)
        
        # Right Column
        right_col = tk.Frame(opt_container)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0))
        
        tk.Label(right_col, text="Size Optimization:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        tk.Checkbutton(right_col, 
                      text="⚡ Exclude tests (recommended)", 
                      variable=self.exclude_tests,
                      font=("Arial", 9)).pack(anchor=tk.W)
        tk.Checkbutton(right_col, 
                      text="⚡ Aggressive optimization", 
                      variable=self.optimize_size,
                      font=("Arial", 9)).pack(anchor=tk.W)

        # ========== Spec 파일 경로 ==========
        tk.Label(self.master, text="Spec File Path:", font=("Arial", 10, "bold")).pack(pady=(5, 0), anchor="w", padx=10)
        spec_frame = tk.Frame(self.master)
        spec_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Entry(spec_frame, textvariable=self.spec_path, width=60).pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(spec_frame, text="Browse...", command=self.select_spec_path).pack(side=tk.LEFT, padx=5)

        # ========== 로그 섹션 ==========
        tk.Label(self.master, text="Log:", font=("Arial", 10, "bold")).pack(pady=(5, 0), anchor="w", padx=10)
        self.log_area = scrolledtext.ScrolledText(self.master, wrap=tk.WORD, width=70, height=8)
        self.log_area.pack(padx=10, pady=2, fill=tk.BOTH, expand=True)

        # ========== 액션 버튼들 (한 줄) ==========
        button_section = tk.Frame(self.master)
        button_section.pack(pady=10, fill=tk.X, padx=10)
        
        # Load/Append
        tk.Button(button_section, text="📂 Load Spec", command=self.load_existing_spec, 
                 font=("Arial", 9), width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(button_section, text="➕ Append", command=self.append_spec,
                 font=("Arial", 9), width=10).pack(side=tk.LEFT, padx=2)
        
        # Divider
        tk.Label(button_section, text=" | ").pack(side=tk.LEFT, padx=5)
        
        # Build Actions
        tk.Button(button_section, text="📝 Generate Spec", command=self.generate_merged_spec, 
                 bg="#2196F3", fg="white", font=("Arial", 9, "bold"), width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(button_section, text="📦 Install Cmds", command=self.show_install_commands, 
                 bg="#FF9800", fg="white", font=("Arial", 9, "bold"), width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(button_section, text="🔨 Build EXE", command=self.build_exe_from_spec, 
                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), width=15).pack(side=tk.LEFT, padx=2)

        # 시작 메시지
        self.log("🚀 PyInstaller Multi-Spec Maker v4.0 Ready!")
        self.log("📌 Step 1: Add Python files")
        self.log("📌 Step 2: Click 'Scan Modules' to detect dependencies")
        self.log("   ℹ️  (auto) = 파일에서 감지된 모듈")
        self.log("   ℹ️  (manual) = 파일에서 안 보여도 필요할 수 있는 모듈")
        self.log("       (동적 import, 간접 의존성, 플러그인 등)")
        self.log("📌 Step 3: Click 'Install Commands' to see pip requirements")
        self.log("📌 Step 4: Configure build options and generate spec file")

    def _get_resource_path(self, filename):
        """
        상대경로 함수: 현재 스크립트와 같은 폴더의 리소스 파일을 찾습니다.
        - py 파일: __file__ 기반으로 경로 계산
        - exe 파일: sys.executable 기반으로 경로 계산
        """
        try:
            # PyInstaller로 exe 변환된 경우
            if getattr(sys, 'frozen', False):
                # exe 파일의 디렉토리
                base_path = os.path.dirname(sys.executable)
            else:
                # py 파일로 실행되는 경우
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            resource_path = os.path.join(base_path, filename)
            return resource_path
        except Exception as e:
            print(f"Error in _get_resource_path: {e}")
            return None

    def _load_window_config(self):
        """저장된 창 위치와 크기 로드 (또는 기본값 반환 - 중앙 배치)"""
        try:
            if os.path.isfile(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    width = config.get('window_width', 950)
                    height = config.get('window_height', 700)
                    pos_x = config.get('window_x', None)
                    pos_y = config.get('window_y', None)
                    # 모니터 해상도 범위 내에서
                    screen_width = self.master.winfo_screenwidth()
                    screen_height = self.master.winfo_screenheight()
                    width = min(width, int(screen_width * 0.98))
                    height = min(height, int(screen_height * 0.95))
                    # 최소 크기 보장
                    width = max(width, 800)
                    height = max(height, 600)  # 버튼들이 보이도록 최소 높이
                    
                    # 저장된 위치가 없으면 중앙에 배치
                    if pos_x is None or pos_y is None:
                        pos_x = (screen_width - width) // 2
                        pos_y = (screen_height - height) // 2
                    
                    return width, height, pos_x, pos_y
        except Exception as e:
            pass
        
        # 기본값: 버튼들이 보이도록 높이 설정, 중앙에 배치
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        width, height = 950, 700
        pos_x = (screen_width - width) // 2
        pos_y = (screen_height - height) // 2
        return width, height, pos_x, pos_y

    def _load_window_size(self):
        """저장된 창 크기 로드 (또는 기본값 반환)"""
        try:
            if os.path.isfile(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    width = config.get('window_width', 950)
                    height = config.get('window_height', 900)
                    # 모니터 해상도 범위 내에서
                    screen_width = self.master.winfo_screenwidth()
                    screen_height = self.master.winfo_screenheight()
                    width = min(width, int(screen_width * 0.98))
                    height = min(height, int(screen_height * 0.95))
                    # 최소 크기 보장
                    width = max(width, 800)
                    height = max(height, 600)  # 버튼들이 보이도록 최소 높이
                    return width, height
        except Exception as e:
            pass
        
        # 기본값: 버튼들이 보이도록 높이 설정
        return 950, 700
    
    def _save_window_size_on_change(self, event=None):
        """창 크기 및 위치 변경 시 저장 (일부 이벤트에서만)"""
        # 너무 자주 저장되지 않도록 함수 호출 제한
        if not hasattr(self, '_last_save_time'):
            self._last_save_time = 0
        
        import time
        current_time = time.time()
        
        # 2초 이상 차이가 날 때만 저장
        if current_time - self._last_save_time > 2:
            try:
                geometry = self.master.geometry()
                # geometry 형식: "widthxheight+x+y"
                parts = geometry.replace('x', '+').split('+')
                width = int(parts[0])
                height = int(parts[1])
                pos_x = int(parts[2])
                pos_y = int(parts[3])
                
                config = {
                    'window_width': width,
                    'window_height': height,
                    'window_x': pos_x,
                    'window_y': pos_y
                }
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
                
                self._last_save_time = current_time
            except Exception as e:
                pass

    def _ensure_window_on_screen(self, window):
        """창이 화면 범위 내에 있도록 조정"""
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        window_x = window.winfo_x()
        window_y = window.winfo_y()
        
        # 창이 화면을 벗어났는지 확인 및 조정
        if window_x + window_width > screen_width:
            window_x = max(0, screen_width - window_width)
        if window_y + window_height > screen_height:
            window_y = max(0, screen_height - window_height)
        
        if window_x < 0:
            window_x = 0
        if window_y < 0:
            window_y = 0
        
        window.geometry(f"+{window_x}+{window_y}")

    def log(self, message):
        """로그 메시지 출력"""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.master.update_idletasks()

    # ========== Python 파일 관리 ==========
    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Select Python files",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        for file in files:
            if not any(file == f[0] for f in self.selected_files):
                self.selected_files.append((file, ""))
                self.files_listbox.insert(tk.END, file)
        if files:
            self.log(f"✅ Added {len(files)} Python file(s)")

    def remove_selected(self):
        indices = self.files_listbox.curselection()
        if not indices:
            return
        for i in reversed(indices):
            removed = self.selected_files[i]
            del self.selected_files[i]
            self.files_listbox.delete(i)
            self.log(f"🗑️ Removed: {os.path.basename(removed[0])}")

    def set_icon_for_selected(self):
        selected = self.files_listbox.curselection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a Python file first")
            return
        
        icon = filedialog.askopenfilename(
            title="Select icon file",
            filetypes=[("Icon Files", "*.ico"), ("All Files", "*.*")]
        )
        if not icon:
            return
        
        index = selected[0]
        py_path, _ = self.selected_files[index]
        self.selected_files[index] = (py_path, icon)
        self.log(f"📌 Icon set for {os.path.basename(py_path)}: {os.path.basename(icon)}")

    # ========== 데이터 파일 관리 ==========
    def add_data_files(self):
        files = filedialog.askopenfilenames(title="Select data files")
        if not files:
            return
        
        dest = simpledialog.askstring(
            "Destination Folder", 
            "Enter destination folder inside the bundle:\n(e.g., '.' for root, 'assets' for assets folder)",
            initialvalue="."
        )
        if dest is None:
            return
        
        for file in files:
            pair = (file, dest)
            if pair not in self.data_files:
                self.data_files.append(pair)
                self.data_files_listbox.insert(tk.END, f"{file} -> {dest}")
        
        self.log(f"✅ Added {len(files)} data file(s) -> {dest}")

    def add_data_folder(self):
        folder = filedialog.askdirectory(title="Select folder to include")
        if not folder:
            return
        
        dest = simpledialog.askstring(
            "Destination Folder",
            f"Enter destination folder inside the bundle:\n(e.g., 'data' to create a data subfolder)",
            initialvalue=os.path.basename(folder)
        )
        if dest is None:
            return
        
        pair = (folder, dest)
        if pair not in self.data_files:
            self.data_files.append(pair)
            self.data_files_listbox.insert(tk.END, f"{folder} -> {dest}")
            self.log(f"✅ Added folder: {os.path.basename(folder)} -> {dest}")

    def remove_selected_data(self):
        indices = self.data_files_listbox.curselection()
        if not indices:
            return
        for i in reversed(indices):
            item = self.data_files[i]
            del self.data_files[i]
            self.data_files_listbox.delete(i)
            self.log(f"🗑️ Removed data: {os.path.basename(item[0])}")

    # ========== Hidden Imports 관리 ==========
    def add_manual_hiddenimport(self):
        module = simpledialog.askstring(
            "Add Hidden Import", 
            "Enter module name:\n(e.g., 'requests', 'PIL.Image', 'win32com.client')"
        )
        if module and module.strip():
            mod = module.strip()
            if mod not in self.manual_hiddenimports:
                self.manual_hiddenimports.append(mod)
                self.update_hiddenimports_display()
                self.log(f"➕ Manually added: {mod}")

    def remove_hiddenimport(self):
        selected = self.hiddenimports_listbox.curselection()
        if not selected:
            return
        
        item = self.hiddenimports_listbox.get(selected[0])
        module = item.split(" ")[0]
        
        removed = False
        if module in self.manual_hiddenimports:
            self.manual_hiddenimports.remove(module)
            removed = True
        if module in self.hiddenimports:
            self.hiddenimports.remove(module)
            removed = True
        
        if removed:
            self.update_hiddenimports_display()
            self.log(f"🗑️ Removed: {module}")

    def clear_hiddenimports(self):
        count = len(self.hiddenimports) + len(self.manual_hiddenimports)
        self.hiddenimports.clear()
        self.manual_hiddenimports.clear()
        self.update_hiddenimports_display()
        self.log(f"🗑️ Cleared {count} hidden import(s)")

    def update_hiddenimports_display(self):
        """Hidden imports 리스트박스 업데이트
        
        (auto)  = Scan Modules에서 파일 분석하여 감지된 모듈
        (manual) = 사용자가 수동 추가하거나 Spec에서 로드한 모듈
                  (파일에서 직접 import 안 되지만 필요할 수 있음:
                   - 동적 import (__import__, importlib)
                   - 간접 의존성 (다른 모듈이 내부적으로 사용)
                   - 플러그인/런타임 로드)
        """
        self.hiddenimports_listbox.delete(0, tk.END)
        all_imports = sorted(self.hiddenimports | set(self.manual_hiddenimports))
        for imp in all_imports:
            tag = " (manual)" if imp in self.manual_hiddenimports else " (auto)"
            self.hiddenimports_listbox.insert(tk.END, f"{imp}{tag}")

    # ========== 모듈 스캔 ==========
    def scan_all_modules(self):
        """선택된 모든 Python 파일에서 import 구문 스캔 (파일별 상세 + 전체 요약 + 인코딩 codec 감지)"""
        if not self.selected_files:
            messagebox.showwarning("Warning", "Please add Python files first")
            return

        self.log("\n🔍 Scanning modules...")
        # 전체 hiddenimports / per-file 정보 초기화
        self.hiddenimports.clear()
        self.file_imports = {}

        total_ast = 0
        total_dynamic = 0
        total_codec = 0
        all_codecs = set()

        for py_path, _ in self.selected_files:
            self.log(f"  📄 Analyzing: {os.path.basename(py_path)}")

            ast_modules, dynamic_modules, codec_modules = self.detect_imports(py_path)

            # per-file 저장
            self.file_imports[py_path] = {
                "ast": set(ast_modules),
                "dynamic": set(dynamic_modules),
                "codec": set(codec_modules),
            }

            # 로그에 파일별 상세 표시
            ast_list = ", ".join(sorted(ast_modules)) if ast_modules else "-"
            dyn_list = ", ".join(sorted(dynamic_modules)) if dynamic_modules else "-"
            codec_list = ", ".join(sorted(codec_modules)) if codec_modules else "-"

            self.log(f"    • AST imports    ({len(ast_modules)}): {ast_list}")
            self.log(f"    • Dynamic imports({len(dynamic_modules)}): {dyn_list}")
            if codec_modules:
                self.log(f"    • 🆕 Codec imports  ({len(codec_modules)}): {codec_list}")
                # cp949 특별 표시
                if 'cp949' in codec_modules or 'euc-kr' in codec_modules:
                    self.log(f"      ✅ Korean encoding detected!")

            # 전체 hiddenimports 집합에 반영
            self.hiddenimports.update(ast_modules)
            self.hiddenimports.update(dynamic_modules)
            self.hiddenimports.update(codec_modules)
            all_codecs.update(codec_modules)

            total_ast += len(ast_modules)
            total_dynamic += len(dynamic_modules)
            total_codec += len(codec_modules)

        # UI 리스트 갱신
        self.update_hiddenimports_display()

        # 공통 / 개별 모듈 요약 (선택 파일이 2개 이상일 때만)
        all_sets = []
        for py_path, _ in self.selected_files:
            info = self.file_imports.get(py_path, {})
            s = set(info.get("ast", set())) | set(info.get("dynamic", set())) | set(info.get("codec", set()))
            all_sets.append(s)

        common_modules = set.intersection(*all_sets) if len(all_sets) >= 2 else set()

        self.log("\n✅ Scan complete!")
        self.log(f"   • AST imports (total count): {total_ast}")
        self.log(f"   • Dynamic imports (total count): {total_dynamic}")
        if total_codec > 0:
            self.log(f"   • 🆕 Codec/Encoding imports (total count): {total_codec}")
            if all_codecs:
                self.log(f"     -> Detected codecs: {', '.join(sorted(all_codecs))}")
        self.log(f"   • Total unique modules: {len(self.hiddenimports)}")

        if len(all_sets) >= 2:
            self.log(f"   • Common modules across all files: {len(common_modules)}")
            if common_modules:
                self.log(f"     -> {', '.join(sorted(common_modules))}")
        else:
            # 파일이 1개만 선택된 경우, 그 파일의 전체 모듈을 한 번 더 정리해서 보여주기
            only_path, _ = self.selected_files[0]
            s = all_sets[0] if all_sets else set()
            self.log(f"   • Modules for {os.path.basename(only_path)}: {len(s)}")
            if s:
                self.log(f"     -> {', '.join(sorted(s))}")

        if self.manual_hiddenimports:
            self.log(f"   • Manual additions: {len(self.manual_hiddenimports)}")

    def detect_imports(self, py_file):
        """Python 파일에서 import 구문 분석 (AST + 정규식 + 인코딩 감지)"""
        ast_imports = set()
        dynamic_imports = set()
        codec_imports = set()
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Method 1: AST 파싱 (가장 정확)
            try:
                tree = ast.parse(content, filename=py_file)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            ast_imports.add(alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            ast_imports.add(node.module.split('.')[0])
            except SyntaxError as e:
                self.log(f"    ⚠️ Syntax error in {os.path.basename(py_file)}: {e}")
            
            # Method 2: 정규식으로 동적 import 패턴 탐지
            # __import__ 패턴
            matches = re.findall(r'__import__\([\'"]([^\'"]+)[\'"]', content)
            dynamic_imports.update([imp.split('.')[0] for imp in matches])
            
            # importlib.import_module 패턴
            matches = re.findall(r'import_module\([\'"]([^\'"]+)[\'"]', content)
            dynamic_imports.update([imp.split('.')[0] for imp in matches])
            
            # Method 3: 인코딩/Codec 관련 패턴 감지 🔥 NEW
            # 문자열 인코딩/디코딩 패턴 (cp949, euc-kr, utf-8, gbk 등)
            encoding_patterns = [
                r"['\"]([a-z0-9\-]+)['\"]\.(?:encode|decode)\(",  # "cp949".encode() 패턴
                r"\.encode\(['\"]([a-z0-9\-]+)['\"]",              # .encode("cp949") 패턴
                r"\.decode\(['\"]([a-z0-9\-]+)['\"]",              # .decode("cp949") 패턴
                r"encoding\s*=\s*['\"]([a-z0-9\-]+)['\"]",         # encoding="cp949" 패턴
                r"codec\.lookup\(['\"]([a-z0-9\-]+)['\"]",         # codec.lookup("cp949") 패턴
                r"codecs\.open\([^,]+,\s*encoding\s*=\s*['\"]([a-z0-9\-]+)['\"]",  # codecs.open(..., encoding="cp949")
                r"open\([^,]+,\s*encoding\s*=\s*['\"]([a-z0-9\-]+)['\"]",          # open(..., encoding="cp949")
            ]
            
            for pattern in encoding_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    codec_name = match.lower()
                    # 코덱 정규화 (cp949, cp-949 -> cp949 형식)
                    codec_normalized = self._normalize_codec_name(codec_name)
                    if codec_normalized:
                        codec_imports.add(codec_normalized)
            
            # 만약 파일에서 open(), encode(), decode() 등을 사용하지만 encoding이 명시되지 않은 경우
            # 기본적으로 'encodings' 모듈은 추가 (Python의 모든 codec이 이를 통해 로드됨)
            if re.search(r'\bopen\s*\(', content) or re.search(r'\.encode\(|\.decode\(', content):
                codec_imports.add('encodings')
        
        except Exception as e:
            self.log(f"    ❌ Error reading {os.path.basename(py_file)}: {e}")
        
        # 표준 라이브러리 제외
        stdlib = self._get_stdlib_modules()
        ast_imports = {imp for imp in ast_imports if imp not in stdlib and imp}
        dynamic_imports = {imp for imp in dynamic_imports if imp not in stdlib and imp}
        # codec_imports는 표준 라이브러리이지만 PyInstaller가 감지 못 할 수 있으므로 유지
        codec_imports = {imp for imp in codec_imports if imp}
        
        return ast_imports, dynamic_imports, codec_imports

    def _normalize_codec_name(self, codec_str):
        """코덱 이름 정규화 (cp-949 -> cp949, euc_kr -> euc-kr 등)"""
        if not codec_str:
            return None
        
        # 공백 제거
        codec_str = codec_str.strip().lower()
        
        # 표준 코덱 이름 매핑
        codec_map = {
            'cp949': 'cp949',           # Korean
            'cp-949': 'cp949',
            'ms949': 'cp949',
            'euc-kr': 'euc-kr',         # Korean
            'euc_kr': 'euc-kr',
            'eucjp': 'eucjp',           # Japanese
            'euc-jp': 'eucjp',
            'euc_jp': 'eucjp',
            'sjis': 'sjis',             # Japanese
            'shiftjis': 'sjis',
            'shift-jis': 'sjis',
            'shift_jis': 'sjis',
            'gbk': 'gbk',               # Chinese
            'gb2312': 'gb2312',
            'big5': 'big5',             # Traditional Chinese
            'iso2022jp': 'iso2022jp',
            'iso-2022-jp': 'iso2022jp',
            'cp1252': 'cp1252',         # Western European
            'latin-1': 'latin-1',
            'latin1': 'latin-1',
            'iso-8859-1': 'latin-1',
            'utf-8': 'utf-8',
            'utf8': 'utf-8',
            'utf-16': 'utf-16',
            'utf16': 'utf-16',
        }
        
        # 정규화된 이름이 있으면 반환
        if codec_str in codec_map:
            return codec_map[codec_str]
        
        # 매핑 없으면 그대로 반환 (유효한 코덱일 수 있음)
        if re.match(r'^[a-z0-9\-_]+$', codec_str):
            return codec_str
        
        return None

    def _get_stdlib_modules(self):
        """Python 표준 라이브러리 모듈 목록"""
        stdlib = set(sys.builtin_module_names)
        stdlib.update([
            'os', 'sys', 're', 'json', 'datetime', 'collections', 
            'itertools', 'functools', 'pathlib', 'typing', 'math',
            'random', 'time', 'string', 'copy', 'io', 'pickle',
            'glob', 'shutil', 'tempfile', 'zipfile', 'tarfile',
            'urllib', 'http', 'ftplib', 'smtplib', 'socket', 'webbrowser',
            'subprocess', 'threading', 'multiprocessing', 'queue',
            'encodings', 'codecs', 'locale', 'array', 'heapq', 'bisect',
            'weakref', 'platform', 'ctypes', 'struct', 'mmap',
            'tkinter', 'turtle', 'argparse', 'configparser', 'logging',
            'unittest', 'doctest', 'pprint', 'textwrap', 'difflib',
            'csv', 'xml', 'html', 'email', 'base64', 'hashlib',
            'hmac', 'secrets', 'uuid', 'inspect', 'traceback',
            'warnings', 'contextlib', 'abc', 'asyncio', 'concurrent',
            'enum', 'dataclasses', 'importlib'
        ])
        return stdlib

    # ========== Spec 파일 경로 ==========
    def select_spec_path(self):
        path = filedialog.asksaveasfilename(
            title="Save spec file as",
            defaultextension=".spec",
            filetypes=[("Spec Files", "*.spec"), ("All Files", "*.*")],
            initialfile=os.path.basename(self.spec_path.get())
        )
        if path:
            self.spec_path.set(path)
            self.log(f"💾 Spec path set to: {path}")

    def backup_spec_file(self, spec_path):
        """기존 spec 파일을 안전하게 백업"""
        if not spec_path or not os.path.isfile(spec_path):
            return None

        base, ext = os.path.splitext(spec_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{base}_{timestamp}_backup{ext or '.spec'}"

        try:
            shutil.copy2(spec_path, backup_path)
            self.log(f"📦 Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            self.log(f"⚠️ Failed to create backup: {e}")
            return None

    # ========== pip 설치 명령어 표시 ==========
    def show_install_commands(self):
        """pip 설치 명령어를 팝업 창으로 표시"""
        all_modules = sorted(self.hiddenimports | set(self.manual_hiddenimports))
        
        if not all_modules:
            messagebox.showinfo(
                "No Modules Detected", 
                "No modules detected yet.\n\nPlease click 'Scan Modules' first!"
            )
            return
        
        # 패키지 이름 변환 및 표준 라이브러리 필터링
        pip_packages = []
        converted_count = 0
        stdlib_filtered_count = 0
        
        stdlib = self._get_stdlib_modules()
        
        for mod in all_modules:
            base_mod = mod.split('.')[0]
            if base_mod in stdlib or mod in stdlib:
                stdlib_filtered_count += 1
                continue
                
            if mod in self.package_mapping:
                pip_packages.append(self.package_mapping[mod])
                converted_count += 1
            else:
                pip_packages.append(base_mod)
        
        pip_packages = sorted(set(pip_packages))
        
        if not pip_packages:
            messagebox.showinfo(
                "No External Packages", 
                f"All {len(all_modules)} detected modules are from the standard library!\n\n"
                f"No pip installation needed. 🎉"
            )
            self.log(f"ℹ️ All modules are standard library (filtered {stdlib_filtered_count})")
            return
        
        # 팝업 창 생성
        popup = tk.Toplevel(self.master)
        popup.title("📦 Required Package Installation Commands")
        popup.geometry("750x600")
        popup.transient(self.master)
        
        # 상단 정보
        info_frame = tk.Frame(popup, bg="#E3F2FD", relief=tk.RIDGE, bd=2)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        info_text = f"💡 Copy and paste these commands to install required packages\n"
        info_text += f"✅ {len(pip_packages)} packages need to be installed"
        if stdlib_filtered_count > 0:
            info_text += f" ({stdlib_filtered_count} stdlib filtered)"
        if converted_count > 0:
            info_text += f" ({converted_count} auto-converted)"
        
        tk.Label(info_frame, text=info_text, bg="#E3F2FD", fg="#0D47A1", 
                font=("Arial", 9, "bold"), justify=tk.LEFT, padx=10, pady=8).pack()
        
        # 탭 생성
        notebook = ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 탭 1: 개별 설치
        tab1 = tk.Frame(notebook)
        notebook.add(tab1, text="Individual Install")
        tk.Label(tab1, text="Install packages one by one:", 
                font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        text1 = tk.Text(tab1, wrap=tk.WORD, height=18, font=("Consolas", 10))
        text1.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        individual_commands = "\n".join([f"pip install {pkg}" for pkg in pip_packages])
        text1.insert("1.0", individual_commands)
        
        # 탭 2: 일괄 설치
        tab2 = tk.Frame(notebook)
        notebook.add(tab2, text="Batch Install (Recommended)")
        tk.Label(tab2, text="Install all packages at once:", 
                font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        text2 = tk.Text(tab2, wrap=tk.WORD, height=18, font=("Consolas", 10))
        text2.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        batch_command = f"pip install {' '.join(pip_packages)}"
        text2.insert("1.0", batch_command)
        
        # 탭 3: requirements.txt
        tab3 = tk.Frame(notebook)
        notebook.add(tab3, text="requirements.txt")
        tk.Label(tab3, text="Save as requirements.txt and run: pip install -r requirements.txt", 
                font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        text3 = tk.Text(tab3, wrap=tk.WORD, height=18, font=("Consolas", 10))
        text3.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        requirements_text = "\n".join(pip_packages)
        text3.insert("1.0", requirements_text)
        
        # 하단 버튼
        btn_frame = tk.Frame(popup)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def copy_current_tab():
            try:
                current_tab = notebook.nametowidget(notebook.select())
                text_widget = current_tab.winfo_children()[1]
                content = text_widget.get("1.0", tk.END).strip()
                popup.clipboard_clear()
                popup.clipboard_append(content)
                popup.update()
                messagebox.showinfo("Copied!", "Commands copied to clipboard!", parent=popup)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy: {e}", parent=popup)
        
        def save_requirements():
            try:
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                    initialfile="requirements.txt",
                    parent=popup
                )
                if file_path:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(requirements_text)
                    messagebox.showinfo("Saved!", f"Saved to:\n{file_path}", parent=popup)
                    self.log(f"💾 Saved requirements.txt: {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}", parent=popup)
        
        tk.Button(btn_frame, text="📋 Copy Current Tab", command=copy_current_tab,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="💾 Save requirements.txt", command=save_requirements,
                 bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Close", command=popup.destroy,
                 font=("Arial", 10)).pack(side=tk.RIGHT, padx=5)
        
        self.log(f"📦 {len(pip_packages)} packages to install (filtered {stdlib_filtered_count} stdlib)")

    # ========== Spec 파일 생성 ==========
    def generate_merged_spec(self):
        """final7.1: per-exe hiddenimports, core libs shared only when used"""
        if not self.selected_files:
            messagebox.showerror("Error", "Please add Python files first")
            return

        try:
            # 1) 프로그램 이름 입력
            name = simpledialog.askstring(
                "Program Name",
                "Enter the output folder/executable name:",
                initialvalue="My_Multi_Apps"
            )
            if name is None:
                self.log("⚠️ Spec generation canceled by user.")
                return

            name = name.strip() or "My_Multi_Apps"

            # 2) 파일별 import 정보 준비
            auto_hidden = set(getattr(self, "hiddenimports", []))
            manual_hidden = set(getattr(self, "manual_hiddenimports", []))

            stdlib = self._get_stdlib_modules()

            modules_by_file = {}
            per_file_bases = {}

            if getattr(self, "file_imports", None):
                # Scan Modules 결과 사용 (파일별 ast/dynamic import)
                for py_path, _ in self.selected_files:
                    info = self.file_imports.get(py_path, {})
                    mods = set(info.get("ast", set())) | set(info.get("dynamic", set()))
                    modules_by_file[py_path] = mods
                    per_file_bases[py_path] = {m.split('.')[0] for m in mods if m}
                    auto_hidden |= mods
            else:
                # Scan Modules 안 했으면: 기존 hiddenimports + manual 을 모든 파일에 동일 적용
                fallback = auto_hidden | manual_hidden
                for py_path, _ in self.selected_files:
                    modules_by_file[py_path] = set(fallback)
                    per_file_bases[py_path] = {m.split('.')[0] for m in fallback if m}

            all_hidden_union = sorted(
                m for m in (auto_hidden | manual_hidden)
                if m and m.split('.')[0] not in stdlib
            )

            lines = ["# -*- mode: python ; coding: utf-8 -*-", ""]
            lines.append("# Generated by PyInstaller Multi-Spec Maker v4.0 (final7.1 per-exe hiddenimports)")
            lines.append(
                f"# Build mode: {'collect_all (safer, larger)' if self.use_collect_all.get() else 'minimal (smaller, manual)'}"
            )
            lines.append(f"# Console: {self.console_mode.get()}, One-file: {self.onefile_mode.get()}")
            lines.append(
                f"# Size optimization: exclude_tests={self.exclude_tests.get()}, aggressive={self.optimize_size.get()}"
            )
            lines.append("")

            # 3) excludes 목록
            excludes_list = []
            if self.exclude_tests.get():
                excludes_list.extend([
#                    'pytest', 'unittest', 'test', 'tests',
                    'pytest','test', 'tests',                    
                    'nose', 'coverage', 'hypothesis',
#                    '_pytest', 'py.test', 'doctest',
                    '_pytest', 'py.test',
                ])
            if self.optimize_size.get():
                excludes_list.extend([
                    'IPython', 'jupyter', 'notebook',
                    'matplotlib.tests', 'numpy.tests', 'pandas.tests',
                    'scipy.tests', 'sklearn.tests',
                    'tkinter.test', 'lib2to3', 'distutils',
                    'setuptools', 'pip', 'wheel', 'pkg_resources',
                ])

            # 4) collect_all 대상 core 패키지 중 실제로 사용되는 것만 선택
            used_core_pkgs = set()
            for py_path, _ in self.selected_files:
                bases = per_file_bases.get(py_path, set())
                for pkg in self.collect_all_packages:
                    if pkg in bases:
                        used_core_pkgs.add(pkg)

            needs_collect_all = sorted(
                pkg for pkg in used_core_pkgs if self.use_collect_all.get()
            )

            # numpy 관련 필수 서브모듈: numpy를 쓰는 exe에만 붙임
            numpy_critical = [
                'numpy._core',
                'numpy._core._exceptions',
                'numpy._core._multiarray_umath',
                'numpy._core.multiarray',
                'numpy.linalg._umath_linalg',
            ]
            # scipy 관련 필수 서브모듈: Pyinstaller가 자동으로 못잡는경우
            scipy_critical = [
                'scipy._cyutility',
            ]

            # pandas 관련 필수 서브모듈: Pyinstaller가 자동으로 못잡는경우
            pandas_critical = [
                'numpy._core',
                'numpy._core._exceptions',
                'numpy._core._multiarray_umath',
                'numpy._core.multiarray',
                'numpy.linalg._umath_linalg',
            ]
                        
            # 5) collect_all 구간 (data/binaries만 공통으로 묶고 hidden_*은 전역으로 안 씀)
            if needs_collect_all:
                lines.append("from PyInstaller.utils.hooks import collect_all, copy_metadata")
                lines.append("")
                lines.append("# ---- Collect all data/binaries for core packages ----")
                for pkg in needs_collect_all:
                    lines.append(f"datas_{pkg}, bins_{pkg}, hidden_{pkg} = collect_all('{pkg}')")
                lines.append("")

                # numpy/pandas 메타데이터 (있으면)
                if 'numpy' in needs_collect_all or 'pandas' in needs_collect_all:
                    lines.append("# ---- Special handling for numpy/pandas metadata ----")
                    if 'numpy' in needs_collect_all:
                        lines.append("datas_numpy += copy_metadata('numpy')")
                    if 'pandas' in needs_collect_all:
                        lines.append("datas_pandas += copy_metadata('pandas')")
                    lines.append("")

                # 공통 data/binaries만 합치기
                lines.append("# Combined data/binaries for all core packages")
                lines.append("datas_collected = []")
                lines.append("binaries_collected = []")
                for pkg in needs_collect_all:
                    lines.append(f"datas_collected += datas_{pkg}")
                    lines.append(f"binaries_collected += bins_{pkg}")
                lines.append("hiddenimports_collected = []  # per-exe hiddenimports only; core hidden handled per exe")
                lines.append("")
            else:
                lines.append("# Minimal mode - no collect_all used")
                lines.append("datas_collected = []")
                lines.append("binaries_collected = []")
                lines.append("hiddenimports_collected = []  # placeholder")
                lines.append("")

            exes = []
            analyses = []
            console_value = "True" if self.console_mode.get() else "False"

            # 6) 각 파일별 Analysis / EXE 생성
            for i, (fpath, icon_path) in enumerate(self.selected_files):
                base = fpath.rsplit('/', 1)[-1].rsplit('\\', 1)[-1].rsplit('.', 1)[0]
                icon = f"'{icon_path}'" if (icon_path and icon_path.strip()) else "None"

                # datas 블록
                if self.data_files:
                    datas_lines = [f"        ('{src}', '{dst}')," for (src, dst) in self.data_files]
                    datas_block = "    datas=datas_collected + [\n" + "\n".join(datas_lines) + "\n    ],"
                else:
                    datas_block = "    datas=datas_collected,"

                # --- per-exe hiddenimports 계산 ---
                raw_mods = set()
                mods_for_file = modules_by_file.get(fpath, set())
                bases_for_file = per_file_bases.get(fpath, set())

                # 1) 이 파일이 실제로 import 한 모듈 중 stdlib 아닌 것
                for mod in mods_for_file:
                    if not mod:
                        continue
                    b = mod.split('.')[0]
                    if b in stdlib:
                        continue
                    raw_mods.add(mod)

                # 2) 수동 hiddenimports는 모든 exe에 공통으로 추가
                raw_mods |= manual_hidden

                # 3) 이 exe가 numpy 사용하면 numpy_critical 서브모듈만 추가
                if 'numpy' in bases_for_file: 
                    raw_mods.update(numpy_critical)

                # 4) 이 exe가 scipy를 사용하면 scipy_critical 서브모듈 추가
                if 'scipy' in bases_for_file:
                    raw_mods.update(scipy_critical)
                
                # 5) 이 exe가 pandas를 사용하면 pandas_critical 서브모듈 추가
                if 'pandas' in bases_for_file:
                    raw_mods.update(pandas_critical)
                    
                file_hidden = sorted(raw_mods)

                if file_hidden:
                    hidden_lines = [f"        '{mod}'," for mod in file_hidden]
                    hidden_block = (
                        "    hiddenimports=hiddenimports_collected + [\n"
                        + "\n".join(hidden_lines)
                        + "\n    ],"
                    )
                else:
                    hidden_block = "    hiddenimports=hiddenimports_collected,"

                # excludes 블록
                if excludes_list:
                    ex_lines = [f"        '{mod}'," for mod in sorted(set(excludes_list))]
                    excludes_block = (
                        "    excludes=[\n"
                        + "\n".join(ex_lines)
                        + "\n    ],"
                    )
                else:
                    excludes_block = "    excludes=[],"

                # ---- One-file / One-folder 분기 ----
                if self.onefile_mode.get():
                    # One-file 모드
                    lines += [
                        f"\n# ---- {base} (One-file mode) ----",
                        f"a{i} = Analysis(",
                        f"    ['{fpath}'],",
                        "    pathex=[],",
                        "    binaries=binaries_collected,",
                        f"{datas_block}",
                        f"{hidden_block}",
                        "    hookspath=[],",
                        "    hooksconfig={},",
                        "    runtime_hooks=[],",
                        f"{excludes_block}",
                        "    noarchive=False,",
                        "    optimize=0,",
                        ")",
                        f"pyz{i} = PYZ(a{i}.pure)",
                        f"exe{i} = EXE(",
                        f"    pyz{i},",
                        f"    a{i}.scripts,",
                        f"    a{i}.binaries,",
                        f"    a{i}.datas,",
                        "    [],",
                        f"    name='{base}',",
                        "    debug=False,",
                        "    bootloader_ignore_signals=False,",
                        "    strip=False,",
                        "    upx=True,",
                        "    upx_exclude=[],",
                        "    runtime_tmpdir=None,",
                        f"    console={console_value},",
                        "    disable_windowed_traceback=False,",
                        "    argv_emulation=False,",
                        "    target_arch=None,",
                        "    codesign_identity=None,",
                        "    entitlements_file=None,",
                        f"    icon={icon}",
                        ")",
                    ]
                    exes.append(f"exe{i}")
                else:
                    # One-folder 모드
                    lines += [
                        f"\n# ---- {base} (One-folder mode) ----",
                        f"a{i} = Analysis(",
                        f"    ['{fpath}'],",
                        "    pathex=[],",
                        "    binaries=binaries_collected,",
                        f"{datas_block}",
                        f"{hidden_block}",
                        "    hookspath=[],",
                        "    hooksconfig={},",
                        "    runtime_hooks=[],",
                        f"{excludes_block}",
                        "    noarchive=False,",
                        "    optimize=0,",
                        ")",
                        f"pyz{i} = PYZ(a{i}.pure)",
                        f"exe{i} = EXE(",
                        f"    pyz{i},",
                        f"    a{i}.scripts,",
                        "    [],",
                        "    exclude_binaries=True,",
                        f"    name='{base}',",
                        "    debug=False,",
                        "    bootloader_ignore_signals=False,",
                        "    strip=False,",
                        "    upx=True,",
                        f"    console={console_value},",
                        "    disable_windowed_traceback=False,",
                        "    argv_emulation=False,",
                        "    target_arch=None,",
                        "    codesign_identity=None,",
                        "    entitlements_file=None,",
                        f"    icon={icon}",
                        ")",
                    ]
                    exes.append(f"exe{i}")
                    analyses.append(f"a{i}")

            # 7) COLLECT (one-folder 모드일 때만)
            if not self.onefile_mode.get():
                if analyses:
                    binaries_join = " + ".join(f"{a}.binaries" for a in analyses)
                    datas_join = " + ".join(f"{a}.datas" for a in analyses)
                else:
                    binaries_join = "[]"
                    datas_join = "[]"

                lines += [
                    "",
                    "coll = COLLECT(",
                    f"    {', '.join(exes)},",
                    f"    {binaries_join},",
                    f"    {datas_join},",
                    "    strip=False,",
                    "    upx=True,",
                    "    upx_exclude=[],",
                    f"    name='{name}'",
                    ")",
                    "",
                ]

            # 8) spec 파일 저장 + 간단 문법 체크
            spec_target = self.spec_path.get()
            self.backup_spec_file(spec_target)

            spec_text = "\n".join(lines)
            # spec 문법 오류 방지용 간단 체크
            compile(spec_text, "<spec>", "exec")

            with open(spec_target, "w", encoding="utf-8") as f_out:
                f_out.write(spec_text)

            # 9) 로그 및 메시지
            self.log("\n" + "=" * 60)
            self.log("✅ Spec file generated successfully! (final7.1 per-exe hiddenimports)")
            self.log("=" * 60)
            self.log(f"📝 File: {self.spec_path.get()}")
            self.log(f"📦 Python files: {len(self.selected_files)}")
            self.log(f"📚 Global hidden imports (union): {len(all_hidden_union)}")
            if needs_collect_all:
                self.log(f"🔧 collect_all core packages (shared data/binaries): {', '.join(needs_collect_all)}")
            else:
                self.log("⚡ Minimal mode (no collect_all)")
            self.log(f"📁 Data files: {len(self.data_files)}")
            self.log(f"🖥️  Console mode: {self.console_mode.get()}")
            self.log(f"📄 One-file mode: {self.onefile_mode.get()}")
            if excludes_list:
                self.log(f"🗜️  Excluded modules: {len(excludes_list)} (size optimization)")
            self.log("\n🔨 Build command:")
            self.log(f"   pyinstaller --clean {os.path.basename(self.spec_path.get())}")
            self.log("=" * 60 + "\n")

            msg = "✅ Spec file generated successfully!\n\n"
            msg += "📊 Summary:\n"
            msg += f"  • Python files: {len(self.selected_files)}\n"
            msg += f"  • Global hidden imports (union): {len(all_hidden_union)}\n"
            if needs_collect_all:
                msg += f"  • collect_all (data/binaries): {', '.join(needs_collect_all)}\n"
            msg += f"  • Data files: {len(self.data_files)}\n"
            if excludes_list:
                msg += f"  • Excluded: {len(excludes_list)} modules (size optimization)\n"
            msg += f"  • Console mode: {self.console_mode.get()}\n"
            msg += f"  • One-file mode: {self.onefile_mode.get()}\n\n"
            msg += "🔨 Build command:\n"
            msg += f"pyinstaller --clean {os.path.basename(self.spec_path.get())}"

            messagebox.showinfo("Success", msg)

        except Exception as e:
            self.log(f"\n❌ Error generating spec file: {e}")
            messagebox.showerror("Error", f"Failed to generate spec file:\n\n{str(e)}")



    # ========== 기존 Spec 파일 로드 ==========
    def load_existing_spec(self):
        """기존 spec 파일을 로드하여 UI에 복원"""
        spec_file = filedialog.askopenfilename(
            title="Load existing spec file",
            filetypes=[("Spec Files", "*.spec"), ("All Files", "*.*")]
        )
        if not spec_file:
            return

        try:
            with open(spec_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 초기화
            self.selected_files.clear()
            self.files_listbox.delete(0, tk.END)
            self.data_files.clear()
            self.data_files_listbox.delete(0, tk.END)
            self.hiddenimports.clear()
            self.manual_hiddenimports.clear()

            # Python 파일 추출
            analysis_blocks = re.findall(r"Analysis\(\s*\[([^\]]+)\]", content, re.DOTALL)
            for block in analysis_blocks:
                py_paths = re.findall(r"'([^']+\.py)'", block)
                for py_file in py_paths:
                    self.selected_files.append((py_file, ""))
                    self.files_listbox.insert(tk.END, py_file)

            # datas 추출 (collect_all 제외)
            datas_matches = re.findall(
                r"datas\s*=\s*(?:datas_collected\s*\+\s*)?\[([^\]]*)\]",
                content,
                re.DOTALL
            )
            for datas_str in datas_matches:
                if datas_str.strip():
                    pairs = re.findall(r"\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)", datas_str)
                    for src, dst in pairs:
                        if (src, dst) not in self.data_files:
                            self.data_files.append((src, dst))
                            self.data_files_listbox.insert(tk.END, f"{src} -> {dst}")

            # hiddenimports 추출 (collect_all 제외)
            hidden_matches = re.findall(
                r"hiddenimports\s*=\s*(?:hiddenimports_collected\s*\+\s*)?\[([^\]]*)\]",
                content,
                re.DOTALL
            )
            for hidden_str in hidden_matches:
                if hidden_str.strip():
                    modules = re.findall(r"'([^']+)'", hidden_str)
                    for mod in modules:
                        if mod not in self.manual_hiddenimports:
                            self.manual_hiddenimports.append(mod)

            # collect_all에서 사용된 패키지도 hiddenimports에 추가
            collect_all_matches = re.findall(r"collect_all\('([^']+)'\)", content)
            for pkg in collect_all_matches:
                if pkg not in self.manual_hiddenimports:
                    self.manual_hiddenimports.append(pkg)

            # 🔽🔽🔽 여기부터 "아이콘 읽기" 부분 (v5 방식) 🔽🔽🔽
            # exeN = EXE(...) 블록을 다음 "# ----", 다음 exe, COLLECT 전까지 하나의 블록으로 인식
            icon_map = {}

            exe_pattern = r"exe(\d+)\s*=\s*EXE\((.*?)(?=\n# ----|\nexe\d+\s*=\s*EXE|\ncoll\s*=\s*COLLECT)"
            for m in re.finditer(exe_pattern, content, re.DOTALL):
                idx = int(m.group(1))
                body = m.group(2)

                # icon=None, icon='...', icon="...", icon=r'...' 모두 처리
                icon_match = re.search(
                    r"icon\s*=\s*(None|[rR]?['\"](.*?)['\"])",
                    body
                )
                if not icon_match:
                    continue
                if icon_match.group(1) == "None":
                    continue

                icon_path = icon_match.group(2)
                if not icon_path or not icon_path.strip():
                    continue

                if 0 <= idx < len(self.selected_files):
                    py_file, _ = self.selected_files[idx]
                    icon_map[py_file] = icon_path

            # 매핑된 icon 을 selected_files 에 반영
            for i, (py_file, _) in enumerate(self.selected_files):
                icon = icon_map.get(py_file, "")
                self.selected_files[i] = (py_file, icon)
                if icon:
                    self.log(
                        f"📌 Loaded icon for {os.path.basename(py_file)}: "
                        f"{os.path.basename(icon)}"
                    )
            # 🔼🔼🔼 아이콘 읽기 끝 🔼🔼🔼


            # 빌드 옵션 복원
            if "collect_all" in content:
                self.use_collect_all.set(True)
            console_match = re.search(r"console\s*=\s*(True|False)", content)
            if console_match:
                self.console_mode.set(console_match.group(1) == "True")
            
            # One-file 모드 감지
            if "exclude_binaries=True" in content:
                self.onefile_mode.set(False)
            elif re.search(r"exe\d+\s*=\s*EXE\([^)]*a\d+\.binaries", content):
                self.onefile_mode.set(True)

            self.update_hiddenimports_display()
            self.spec_path.set(spec_file)
            
            self.log(f"\n{'='*60}")
            self.log(f"✅ Loaded spec file successfully!")
            self.log(f"{'='*60}")
            self.log(f"📝 File: {spec_file}")
            self.log(f"📦 Python files: {len(self.selected_files)}")
            self.log(f"📚 Hidden imports: {len(self.manual_hiddenimports)}")
            self.log(f"📁 Data files: {len(self.data_files)}")
            self.log(f"🔧 collect_all mode: {self.use_collect_all.get()}")
            self.log(f"🖥️  Console mode: {self.console_mode.get()}")
            self.log(f"📄 One-file mode: {self.onefile_mode.get()}")
            self.log(f"{'='*60}\n")

        except Exception as e:
            self.log(f"\n❌ Error loading spec file: {e}")
            messagebox.showerror("Error", f"Failed to load spec file:\n\n{str(e)}")


    def append_spec(self):
        """기존 UI 상태에 다른 spec 파일 내용을 추가 병합"""
        spec_file = filedialog.askopenfilename(
            title="Append existing spec file",
            filetypes=[("Spec Files", "*.spec"), ("All Files", "*.*")]
        )
        if not spec_file:
            return

        try:
            with open(spec_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # ---------- 1) Python 파일 병합 ----------
            existing_py_files = {py for py, _ in self.selected_files}

            analysis_blocks = re.findall(
                r"Analysis\(\s*\[([^\]]+)\]",
                content,
                re.DOTALL
            )
            new_py_count = 0
            for block in analysis_blocks:
                py_paths = re.findall(r"'([^']+\.py)'", block)
                for py_file in py_paths:
                    if py_file not in existing_py_files:
                        self.selected_files.append((py_file, ""))
                        self.files_listbox.insert(tk.END, py_file)
                        existing_py_files.add(py_file)
                        new_py_count += 1

            # ---------- 2) data_files 병합 ----------
            existing_data = set(self.data_files)
            datas_matches = re.findall(
                r"datas\s*=\s*(?:datas_collected\s*\+\s*)?\[([^\]]*)\]",
                content,
                re.DOTALL
            )
            new_data_count = 0
            for datas_str in datas_matches:
                if datas_str.strip():
                    pairs = re.findall(r"\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)", datas_str)
                    for src, dst in pairs:
                        pair = (src, dst)
                        if pair not in existing_data:
                            self.data_files.append(pair)
                            self.data_files_listbox.insert(tk.END, f"{src} -> {dst}")
                            existing_data.add(pair)
                            new_data_count += 1

            # ---------- 3) hiddenimports / collect_all 패키지 병합 ----------
            existing_manual = set(self.manual_hiddenimports)

            hidden_matches = re.findall(
                r"hiddenimports\s*=\s*(?:hiddenimports_collected\s*\+\s*)?\[([^\]]*)\]",
                content,
                re.DOTALL
            )
            new_hidden_count = 0
            for hidden_str in hidden_matches:
                if hidden_str.strip():
                    modules = re.findall(r"'([^']+)'", hidden_str)
                    for mod in modules:
                        if mod not in existing_manual:
                            self.manual_hiddenimports.append(mod)
                            existing_manual.add(mod)
                            new_hidden_count += 1

            collect_all_matches = re.findall(r"collect_all\('([^']+)'\)", content)
            for pkg in collect_all_matches:
                if pkg not in existing_manual:
                    self.manual_hiddenimports.append(pkg)
                    existing_manual.add(pkg)
                    new_hidden_count += 1

            # ---------- 4) icon 정보 병합 (v5 방식) ----------
            icon_map = {}

            exe_pattern = r"exe(\d+)\s*=\s*EXE\((.*?)(?=\n# ----|\nexe\d+\s*=\s*EXE|\ncoll\s*=\s*COLLECT)"
            for m in re.finditer(exe_pattern, content, re.DOTALL):
                idx = int(m.group(1))
                body = m.group(2)

                icon_match = re.search(
                    r"icon\s*=\s*(None|[rR]?['\"](.*?)['\"])",
                    body
                )
                if not icon_match:
                    continue
                if icon_match.group(1) == "None":
                    continue

                icon_path = icon_match.group(2)
                if not icon_path or not icon_path.strip():
                    continue

                # append 시에는 "기존에 아이콘이 없는 경우만" 덮어쓰기
                if 0 <= idx < len(self.selected_files):
                    py_file, cur_icon = self.selected_files[idx]
                    if not cur_icon:
                        icon_map[py_file] = icon_path

            for i, (py_file, cur_icon) in enumerate(self.selected_files):
                if py_file in icon_map and not cur_icon:
                    new_icon = icon_map[py_file]
                    self.selected_files[i] = (py_file, new_icon)
                    self.log(
                        f"📌 (Append) Loaded icon for "
                        f"{os.path.basename(py_file)}: {os.path.basename(new_icon)}"
                    )


            # ---------- 5) hiddenimports 리스트박스 갱신 ----------
            self.update_hiddenimports_display()

            # ---------- 6) 로그 출력 ----------
            self.log(f"\n{'='*60}")
            self.log(f"✅ Spec file appended successfully!")
            self.log(f"{'='*60}")
            self.log(f"📝 Appended from: {spec_file}")
            self.log(f"➕ New Python files: {new_py_count}")
            self.log(f"➕ New data files: {new_data_count}")
            self.log(f"➕ New hidden imports: {new_hidden_count}")
            self.log(f"📦 Total Python files now: {len(self.selected_files)}")
            self.log(f"📚 Total manual hiddenimports now: {len(self.manual_hiddenimports)}")
            self.log(f"📁 Total data files now: {len(self.data_files)}")
            self.log(f"{'='*60}\n")

        except Exception as e:
            self.log(f"\n❌ Error appending spec file: {e}")
            messagebox.showerror("Error", f"Failed to append spec file:\n\n{str(e)}")



    def build_exe_from_spec(self):
        """PyInstaller를 사용하여 Spec 파일로부터 EXE 빌드 (한글 경로 지원)"""
        spec_path = self.spec_path.get()
        
        if not spec_path or not os.path.isfile(spec_path):
            messagebox.showerror("Error", f"Spec file not found: {spec_path}")
            return
        
        try:
            result = messagebox.askyesno(
                "Build Confirmation",
                f"Build EXE from spec?\n\n{spec_path}\n\n"
                "This may take several minutes..."
            )
            if not result:
                return
            
            # 빌드 시작 로그
            self.log(f"\n{'='*60}")
            self.log(f"🔨 Starting PyInstaller build...")
            self.log(f"{'='*60}")
            self.log(f"📝 Spec file: {spec_path}")
            self.log(f"📁 Working directory: {os.getcwd()}")
            
            # PyInstaller 명령어 구성
            spec_dir = os.path.dirname(spec_path) or "."
            spec_file = os.path.basename(spec_path)
            dist_dir = os.path.join(spec_dir, 'dist')
            
            # dist 폴더 자동 삭제 (한글 경로 문제 방지)
            if os.path.isdir(dist_dir):
                self.log(f"🗑️  Removing existing dist folder...")
                try:
                    shutil.rmtree(dist_dir)
                    self.log(f"✅ dist folder removed")
                except Exception as e:
                    self.log(f"⚠️  Warning: Could not remove dist folder: {e}")
            
            # build 폴더도 정리 (선택사항)
            build_dir = os.path.join(spec_dir, 'build')
            if os.path.isdir(build_dir):
                try:
                    shutil.rmtree(build_dir)
                    self.log(f"✅ build folder removed")
                except Exception as e:
                    pass
            
            # PyInstaller 명령어 (--clean과 -y 옵션 추가)
            cmd = ["pyinstaller", "--clean", "-y", spec_file]
            
            # 빌드를 별도 스레드에서 실행하여 UI가 멈추지 않도록 함
            def run_build():
                try:
                    self.log(f"▶️  Running: {' '.join(cmd)}")
                    self.log(f"   (UTF-8 encoding for Korean path support)")
                    
                    # 한글 경로 지원을 위해 명시적으로 UTF-8 인코딩 설정
                    process = subprocess.Popen(
                        cmd,
                        cwd=spec_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        encoding='utf-8',  # 명시적 UTF-8
                        errors='replace',   # 인코딩 오류 시 치환
                        creationflags=0x08000000  # Windows: CREATE_NO_WINDOW 플래그 (선택사항)
                    )
                    
                    # 실시간 출력 읽기 (UTF-8 디코딩)
                    for line in process.stdout:
                        line = line.rstrip()
                        if line:
                            self.log(f"   {line}")
                    
                    returncode = process.wait()
                    
                    # 빌드 완료
                    self.log("")
                    if returncode == 0:
                        self.log(f"{'='*60}")
                        self.log(f"✅ Build completed successfully!")
                        self.log(f"{'='*60}")
                        self.log(f"📦 Output folder: {dist_dir}")
                        messagebox.showinfo(
                            "Build Success",
                            f"EXE build completed!\n\n"
                            f"Output folder: {dist_dir}"
                        )
                    else:
                        self.log(f"{'='*60}")
                        self.log(f"❌ Build failed with exit code {returncode}")
                        self.log(f"{'='*60}")
                        messagebox.showerror(
                            "Build Failed",
                            f"Build failed with exit code {returncode}\n\n"
                            f"Check log for details"
                        )
                except Exception as e:
                    error_msg = str(e)
                    self.log(f"❌ Error: {error_msg}")
                    messagebox.showerror("Error", f"Build error: {error_msg}")
            
            # 스레드 시작
            build_thread = threading.Thread(target=run_build, daemon=True)
            build_thread.start()
            
        except Exception as e:
            error_msg = str(e)
            self.log(f"❌ Error preparing build: {error_msg}")
            messagebox.showerror("Error", f"Failed to start build: {error_msg}")



def main():
    """메인 함수"""
    # UTF-8 인코딩 설정 (한글 경로 지원)
    import locale
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    root = tk.Tk()
    app = PyInstallerSpecMerger(root)
    
    # 종료 시 창 크기 저장
    def on_closing():
        app._save_window_size_on_change()  # 명시적 저장
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()
