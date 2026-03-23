import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import subprocess
import os
import json
import time
import math
import webbrowser
from tkinter import simpledialog, colorchooser 

# 멀티 모니터 지원을 위한 임포트
try:
    import win32api
    MULTI_MONITOR_SUPPORT = True
except ImportError:
    MULTI_MONITOR_SUPPORT = False
    print("Warning: win32api not available. Multi-monitor support disabled.")
    print("Install with: pip install pywin32")

# 홈 디렉토리 경로 가져오기
home_dir = os.path.expanduser("~")
config_file = os.path.join(home_dir, "launcher_config.json")

# 기본 설정값
default_launcher_position = {'x': 1600, 'y': 500, 'width': 45, 'height': 550}
default_setup_position = {'x': 1600, 'y': 200, 'width': 680, 'height': 680}
default_layout_settings = {
    'column_count': 1,
    'auto_columns': True,
    'gui_pad_x': 2,
    'gui_pad_y': 2,
    'button_pad_x': 2,
    'button_pad_y': 2,
}

# 버튼 이름과 실행 경로를 저장할 리스트
button_names = ["Setup"]
program_paths = [""]
layout_settings = default_layout_settings.copy()
button_widgets = []
button_container = None
entries = []
button_colors = [] 

# === 자동 숨김 & 페이드 설정 ===
FADE_ALPHA_VISIBLE = 1.0
FADE_ALPHA_HIDDEN  = 0.5
FADE_STEP          = 0.08
FADE_INTERVAL_MS   = 12

SLIDE_STEP_PX      = 14
SLIDE_INTERVAL_MS  = 10
HIDE_DELAY_MS      = 400
EDGE_SNAP_MARGIN   = 100  # 엣지 스냅 감지 거리 증가
PEEK_EXPOSE_PX     = 5
SHOW_DELAY_MS      = 300
ESTIMATED_BUTTON_HEIGHT = 60

# 동작 상태 플래그
_state = {
    "animating_fade": False,
    "animating_slide": False,
    "hide_scheduled": None,
    "show_scheduled": None,
    "hidden": False,
    "docked_edge": None,  # 'left', 'right', None
    "docked_monitor": None,  # 모니터 인덱스
    "target_alpha": None,
    "target_x": None
}

# 모니터 정보 캐시 (해상도 변경 감지용)
_monitors_cache = None
_monitors_cache_key = None  # (screenwidth, screenheight) 캐시 키

def get_monitors_info():
    """모든 모니터의 정보를 반환 (왼쪽에서 오른쪽 순서로 정렬)"""
    global _monitors_cache, _monitors_cache_key

    if not MULTI_MONITOR_SUPPORT:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        return [{'left': 0, 'top': 0, 'right': sw, 'bottom': sh, 'width': sw, 'height': sh}]

    # 해상도가 바뀌면 캐시 무효화
    try:
        cache_key = (root.winfo_screenwidth(), root.winfo_screenheight())
    except Exception:
        cache_key = None

    if _monitors_cache is not None and cache_key == _monitors_cache_key:
        return _monitors_cache

    monitors = []
    try:
        for monitor in win32api.EnumDisplayMonitors():
            monitor_info = win32api.GetMonitorInfo(monitor[0])
            work_area = monitor_info['Work']
            monitors.append({
                'left': work_area[0],
                'top': work_area[1],
                'right': work_area[2],
                'bottom': work_area[3],
                'width': work_area[2] - work_area[0],
                'height': work_area[3] - work_area[1]
            })
    except Exception:
        pass

    if not monitors:
        # 폴백: tkinter 기본 화면
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        monitors = [{'left': 0, 'top': 0, 'right': sw, 'bottom': sh, 'width': sw, 'height': sh}]

    monitors.sort(key=lambda m: m['left'])
    _monitors_cache = monitors
    _monitors_cache_key = cache_key
    return monitors

def find_nearest_edge(x, y, width, height):
    """
    현재 창 위치에서 가장 가까운 모니터 엣지를 찾음
    반환: (monitor_index, edge, snap_x) 또는 None
    edge는 'left' 또는 'right'
    """
    monitors = get_monitors_info()
    window_center_x = x + width // 2
    window_center_y = y + height // 2
    
    candidates = []
    
    for idx, mon in enumerate(monitors):
        # 창이 이 모니터의 Y 범위 내에 있는지 확인
        if not (mon['top'] <= window_center_y <= mon['bottom']):
            continue
        
        # 왼쪽 엣지까지의 거리
        left_edge_x = mon['left']
        dist_to_left = abs(x - left_edge_x)
        if dist_to_left <= EDGE_SNAP_MARGIN:
            candidates.append((dist_to_left, idx, 'left', left_edge_x))
        
        # 오른쪽 엣지까지의 거리
        right_edge_x = mon['right'] - width
        dist_to_right = abs(x - right_edge_x)
        if dist_to_right <= EDGE_SNAP_MARGIN:
            candidates.append((dist_to_right, idx, 'right', right_edge_x))
    
    if not candidates:
        return None
    
    # 가장 가까운 엣지 선택
    candidates.sort(key=lambda c: c[0])
    _, monitor_idx, edge, snap_x = candidates[0]
    return monitor_idx, edge, snap_x

def load_settings():
    global button_names, program_paths, launcher_position, setup_position, layout_settings, button_colors

    launcher_position = default_launcher_position.copy()
    setup_position = default_setup_position.copy()
    layout_settings = default_layout_settings.copy()

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8-sig') as f:
                config_data = json.load(f)

            button_names = config_data.get("button_names", button_names)
            program_paths = config_data.get("program_paths", program_paths)

            button_colors = config_data.get(
                "button_colors",
                ["#f0f0f0"] * len(button_names)
            )

            launcher_position.update(config_data.get("launcher_position", {}))
            setup_position.update(config_data.get("setup_position", {}))
            layout_settings.update(config_data.get("layout_settings", {}))

        except Exception:
            messagebox.showerror(
                "설정 파일 오류",
                "설정 파일을 읽을 수 없습니다.\n기본 설정으로 복구합니다."
            )
            return  # 기본값 유지

    else:
        # 설정 파일이 없으면 기본 화면 중앙 배치
        try:
            temp_root = tk.Tk()
            screen_width = temp_root.winfo_screenwidth()
            screen_height = temp_root.winfo_screenheight()
            temp_root.destroy()

            launcher_w = default_launcher_position['width']
            launcher_h = default_launcher_position['height']
            launcher_position.update({
                'x': max(0, (screen_width - launcher_w) // 2),
                'y': max(0, (screen_height - launcher_h) // 2),
                'width': launcher_w,
                'height': launcher_h
            })

            setup_w = default_setup_position['width']
            setup_h = default_setup_position['height']
            setup_position.update({
                'x': max(0, (screen_width - setup_w) // 2),
                'y': max(0, (screen_height - setup_h) // 2),
                'width': setup_w,
                'height': setup_h
            })

        except Exception:
            pass

    # 데이터 개수 동기화
    while len(button_colors) < len(button_names):
        button_colors.append("#f0f0f0")
        # button_names / program_paths 길이 동기화
        min_len = min(len(button_names), len(program_paths))
        button_names[:] = button_names[:min_len]
        program_paths[:] = program_paths[:min_len]
        button_colors[:] = button_colors[:min_len]


def save_settings():
    update_window_state()

    # ── 저장 전 위치 보정 ──────────────────────────────────────────────────
    # 숨김 슬라이드 상태에서 종료하면 hidden_x 가 저장되어 다음 부팅 때
    # 화면 밖에서 시작하는 문제를 방지.
    # 도킹 중이라면 visible_x(완전히 보이는 위치)로 덮어씁니다.
    save_pos = launcher_position.copy()
    if _state.get("docked_edge") is not None and _state.get("docked_monitor") is not None:
        monitors = get_monitors_info()
        midx = _state["docked_monitor"]
        if midx < len(monitors):
            mon = monitors[midx]
            w = save_pos["width"]
            if _state["docked_edge"] == "right":
                save_pos["x"] = mon["right"] - w
            else:  # left
                save_pos["x"] = mon["left"]
    else:
        # 도킹 안 된 경우: 화면 안쪽으로 클램프
        monitors = get_monitors_info()
        sx = save_pos["x"]
        sy = save_pos["y"]
        sw = save_pos["width"]
        sh = save_pos["height"]
        clamped = False
        for mon in monitors:
            # 창이 이 모니터에 속하는지 간단 판정
            cx = sx + sw // 2
            cy = sy + sh // 2
            if mon["left"] <= cx <= mon["right"] and mon["top"] <= cy <= mon["bottom"]:
                # 화면 안으로 클램프 (최소 50px 이상 보이게)
                margin = 50
                save_pos["x"] = max(mon["left"], min(sx, mon["right"] - sw))
                save_pos["y"] = max(mon["top"],  min(sy, mon["bottom"] - sh))
                clamped = True
                break
        if not clamped and monitors:
            # 어느 모니터에도 속하지 않으면 주 모니터 중앙으로
            mon = monitors[0]
            save_pos["x"] = mon["left"] + (mon["width"] - sw) // 2
            save_pos["y"] = mon["top"]  + (mon["height"] - sh) // 2

    config_data = {
        "button_names": button_names,
        "program_paths": program_paths,
        "button_colors": button_colors,
        "launcher_position": save_pos,
        "setup_position": setup_position,
        "layout_settings": layout_settings
    }

    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

def update_window_state(event=None):
    if root.winfo_exists():
        # 슬라이드 애니메이션 중(숨김 이동 중)에는 좌표를 갱신하지 않음
        # → 저장 시 hidden_x 가 launcher_position 에 기록되는 것을 방지
        if _state.get("animating_slide"):
            return
        launcher_position['x'] = root.winfo_x()
        launcher_position['y'] = root.winfo_y()
        launcher_position['width'] = root.winfo_width()
        launcher_position['height'] = root.winfo_height()

def safe_int(value, fallback):
    try:
        return int(value)
    except (ValueError, TypeError):
        return fallback

class SetupWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Windows Launcher Setup v3.5 Multi-Monitor by sungkb04@khnp.co.kr")
        self.geometry(f"{setup_position['width']}x{setup_position['height']}+{setup_position['x']}+{setup_position['y']}")

        self.bind("<Configure>", self.on_window_configure)
        self.setup_ui()

    def on_window_configure(self, event=None):
        if event.widget == self:
            setup_position['x'] = self.winfo_x()
            setup_position['y'] = self.winfo_y()
            setup_position['width'] = self.winfo_width()
            setup_position['height'] = self.winfo_height()

    def sync_entries_to_global(self):
        """현재 entries의 임시값을 전역 변수에 동기화"""
        for i, (entry_name, entry_path) in enumerate(entries):
            if i < len(button_names):
                button_names[i] = entry_name.get()
            if i < len(program_paths):
                program_paths[i] = entry_path.get()

    def setup_ui(self):
        global entries
        entries = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        settings_frame = tk.Frame(self)
        settings_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))
        settings_frame.columnconfigure(7, weight=1)

        self.width_var = tk.StringVar(value=str(launcher_position['width']))
        self.height_var = tk.StringVar(value=str(launcher_position['height']))
        self.columns_var = tk.StringVar(value=str(layout_settings.get("column_count", 1)))
        self.auto_columns_var = tk.BooleanVar(value=layout_settings.get("auto_columns", True))
        self.gui_pad_x_var = tk.StringVar(value=str(layout_settings.get("gui_pad_x", 2)))
        self.gui_pad_y_var = tk.StringVar(value=str(layout_settings.get("gui_pad_y", 2)))
        self.button_pad_x_var = tk.StringVar(value=str(layout_settings.get("button_pad_x", 2)))
        self.button_pad_y_var = tk.StringVar(value=str(layout_settings.get("button_pad_y", 2)))

        tk.Label(settings_frame, text="Width").grid(row=0, column=0, padx=(0, 3), sticky="w")
        self.width_entry = tk.Entry(settings_frame, width=6, textvariable=self.width_var)
        self.width_entry.grid(row=0, column=1, padx=(0, 8))

        tk.Label(settings_frame, text="Height").grid(row=0, column=2, padx=(0, 3), sticky="w")
        self.height_entry = tk.Entry(settings_frame, width=6, textvariable=self.height_var)
        self.height_entry.grid(row=0, column=3, padx=(0, 8))

        tk.Label(settings_frame, text="Columns").grid(row=0, column=4, padx=(0, 3), sticky="w")
        self.columns_entry = tk.Entry(settings_frame, width=4, textvariable=self.columns_var)
        self.columns_entry.grid(row=0, column=5, padx=(0, 8))

        auto_btn = tk.Checkbutton(
            settings_frame,
            text="Auto Columns",
            variable=self.auto_columns_var,
            command=self.update_column_entry_state
        )
        auto_btn.grid(row=0, column=6, sticky="w")

        tk.Label(settings_frame, text="GUI Pad X").grid(row=1, column=0, padx=(0, 3), sticky="w")
        self.gui_pad_x_entry = tk.Entry(settings_frame, width=4, textvariable=self.gui_pad_x_var)
        self.gui_pad_x_entry.grid(row=1, column=1, padx=(0, 8))

        tk.Label(settings_frame, text="GUI Pad Y").grid(row=1, column=2, padx=(0, 3), sticky="w")
        self.gui_pad_y_entry = tk.Entry(settings_frame, width=4, textvariable=self.gui_pad_y_var)
        self.gui_pad_y_entry.grid(row=1, column=3, padx=(0, 8))

        tk.Label(settings_frame, text="Button Pad X").grid(row=1, column=4, padx=(0, 3), sticky="w")
        self.button_pad_x_entry = tk.Entry(settings_frame, width=4, textvariable=self.button_pad_x_var)
        self.button_pad_x_entry.grid(row=1, column=5, padx=(0, 8))

        tk.Label(settings_frame, text="Button Pad Y").grid(row=1, column=6, padx=(0, 3), sticky="w")
        self.button_pad_y_entry = tk.Entry(settings_frame, width=4, textvariable=self.button_pad_y_var)
        self.button_pad_y_entry.grid(row=1, column=7, sticky="w")

        self.entries_container = tk.Frame(self)
        self.entries_container.grid(row=2, column=0, sticky="nsew", padx=5, pady=(5, 0))
        self.entries_container.columnconfigure(0, weight=1)
        self.entries_container.rowconfigure(0, weight=1)

        self.entries_canvas = tk.Canvas(self.entries_container, highlightthickness=0)
        self.entries_canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(self.entries_container, orient="vertical", command=self.entries_canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.entries_canvas.configure(yscrollcommand=scrollbar.set)

        self.entries_inner = tk.Frame(self.entries_canvas)
        self.entries_window = self.entries_canvas.create_window((0, 0), window=self.entries_inner, anchor="nw")

        self.entries_inner.bind("<Configure>", self._on_entries_configure)
        self.entries_canvas.bind("<Configure>", self._on_canvas_configure)
        self.entries_canvas.bind("<Enter>", lambda _: self._bind_mousewheel())
        self.entries_canvas.bind("<Leave>", lambda _: self._unbind_mousewheel())
        self.bind("<Destroy>", self._on_destroy)
        self._mousewheel_bound = False

        self.update_column_entry_state()

        def save_and_update():
            # 엔트리 값을 전역변수에 동기화
            self.sync_entries_to_global()
            # 윈도우 설정 적용
            self.apply_window_settings()
            # 설정 저장
            save_settings()
            # 메인 런처 업데이트
            update_buttons()

        # 컨트롤 프레임 (모든 버튼을 한 줄에 배치)
        control_frame = tk.Frame(self)
        control_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        #apply_btn = tk.Button(control_frame, text="Apply size/spacing", command=self.apply_window_settings)
        #apply_btn.pack(side=tk.LEFT, padx=2)

        # 오른쪽 정렬: 저장/닫기 버튼 (side=tk.RIGHT 사용)
        help_button = tk.Button(control_frame, text="Help", width=8, command=self.show_help)
        help_button.pack(side=tk.RIGHT, padx=2)

        close_button = tk.Button(control_frame, text="닫기", width=8, command=self.destroy)
        close_button.pack(side=tk.RIGHT, padx=2)

        save_button = tk.Button(control_frame, text="Save", width=8, bg="#e1f5fe", command=save_and_update)
        save_button.pack(side=tk.RIGHT, padx=2)

        # 항목 리스트 업데이트
        self.refresh_entries()

    def _bind_mousewheel(self):
        if not self._mousewheel_bound:
            self.bind_all("<MouseWheel>", self._on_mousewheel)
            self._mousewheel_bound = True

    def _unbind_mousewheel(self):
        if self._mousewheel_bound:
            self.unbind_all("<MouseWheel>")
            self._mousewheel_bound = False

    def _on_mousewheel(self, event):
        if event.delta == 0:
            return
        step = -1 if event.delta > 0 else 1
        self.entries_canvas.yview_scroll(step, "units")

    def _on_destroy(self, event):
        if event.widget == self:
            self._unbind_mousewheel()

    def _on_entries_configure(self, event):
        bbox = self.entries_canvas.bbox("all")
        if bbox:
            self.entries_canvas.configure(scrollregion=bbox)

    def _on_canvas_configure(self, event):
        if self.entries_canvas.winfo_exists():
            self.entries_canvas.itemconfigure(self.entries_window, width=event.width)



    def refresh_entries(self):
        # 안전장치: button_colors 개수가 부족하면 보충합니다.
        while len(button_colors) < len(button_names):
            button_colors.append("#f0f0f0")
            
        for widget in self.entries_inner.winfo_children():
            widget.destroy()
        entries.clear()
    
        for i, name in enumerate(button_names):
            frame = tk.Frame(self.entries_inner)
            frame.pack(fill=tk.X, pady=2, padx=2)
    
            # 각 컬럼 설정
            tk.Label(frame, text=f"{i+1}:", width=3).grid(row=0, column=0, padx=2)
    
            entry_name = tk.Entry(frame, width=15)
            entry_name.insert(0, name)
            entry_name.grid(row=0, column=1, padx=2)
    
            entry_path = tk.Entry(frame, width=30)
            entry_path.insert(0, program_paths[i])
            entry_path.grid(row=0, column=2, padx=2)
    
            # 색상 선택 버튼 (현재 색상을 배경색으로 표시)
            color_btn = tk.Button(
                frame, 
                text="Color", 
                width=6,
                bg=button_colors[i],
                command=lambda idx=i: self.pick_color_for_setup(idx)
            )
            color_btn.grid(row=0, column=3, padx=2)
    
            if i == 0:
                # Setup 버튼: 아래에 추가 (원래 아이콘)
                tk.Button(frame, text="▼+", width=3, bg="#ccffcc", command=lambda idx=i: self.insert_button_after(idx)).grid(row=0, column=6, padx=2)
            else:
                # 일반 버튼: Browse, Del, 아래에 추가(▼+), 아래로(▼), 위로(▲)
                tk.Button(frame, text="Browse", width=8, command=lambda idx=i: self.browse_file(idx)).grid(row=0, column=4, padx=2)
                tk.Button(frame, text="Del", width=5, bg="#ffcccc", command=lambda idx=i: self.delete_button_at(idx)).grid(row=0, column=5, padx=2)
                tk.Button(frame, text="▼+", width=3, bg="#ccffcc", command=lambda idx=i: self.insert_button_after(idx)).grid(row=0, column=6, padx=2)
                tk.Button(frame, text="▼", width=3, bg="#d3d3d3", command=lambda idx=i: self.move_button_down(idx)).grid(row=0, column=7, padx=2)
                tk.Button(frame, text="▲", width=3, bg="#d3d3d3", command=lambda idx=i: self.move_button_up(idx)).grid(row=0, column=8, padx=2)
    
            entries.append((entry_name, entry_path))





    def delete_button_at(self, index):
        """특정 인덱스의 버튼 삭제"""
        if index == 0:  # Setup 버튼은 삭제 불가
            self.show_centered_message("경고", "Setup 버튼은 삭제할 수 없습니다.", "warning")
            return
        
        if len(button_names) <= 1:
            self.show_centered_message("경고", "최소 1개의 버튼이 필요합니다.", "warning")
            return
        
        # ★ 핵심: 삭제 전에 현재 entries 값을 동기화
        self.sync_entries_to_global()
        
        # 확인 메시지
        if self.show_centered_question("삭제 확인", f"'{button_names[index]}' 버튼을 삭제하시겠습니까?"):
            button_names.pop(index)
            program_paths.pop(index)
            if index < len(button_colors):
                button_colors.pop(index)
            self.refresh_entries()

    def show_centered_message(self, title, message, msg_type="info"):
        """Setup 창 중앙에 메시지 박스 표시"""
        msg_window = tk.Toplevel(self)
        msg_window.title(title)
        msg_window.transient(self)
        msg_window.grab_set()
        
        # Setup 창 중앙에 배치
        self.update_idletasks()
        setup_x = self.winfo_x()
        setup_y = self.winfo_y()
        setup_w = self.winfo_width()
        setup_h = self.winfo_height()
        
        msg_w = 300
        msg_h = 150
        pos_x = setup_x + (setup_w - msg_w) // 2
        pos_y = setup_y + (setup_h - msg_h) // 2
        
        msg_window.geometry(f"{msg_w}x{msg_h}+{pos_x}+{pos_y}")
        
        # 아이콘과 메시지
        icon_text = "⚠" if msg_type == "warning" else "ℹ"
        tk.Label(msg_window, text=icon_text, font=("", 24)).pack(pady=(15, 5))
        tk.Label(msg_window, text=message, wraplength=250).pack(pady=5)
        
        tk.Button(msg_window, text="확인", width=10, command=msg_window.destroy).pack(pady=10)
        
        msg_window.bind("<Return>", lambda e: msg_window.destroy())
        msg_window.bind("<Escape>", lambda e: msg_window.destroy())

    def show_centered_question(self, title, message):
        """Setup 창 중앙에 예/아니오 질문 표시"""
        result = [False]  # 결과를 저장할 리스트
        
        q_window = tk.Toplevel(self)
        q_window.title(title)
        q_window.transient(self)
        q_window.grab_set()
        
        # Setup 창 중앙에 배치
        self.update_idletasks()
        setup_x = self.winfo_x()
        setup_y = self.winfo_y()
        setup_w = self.winfo_width()
        setup_h = self.winfo_height()
        
        q_w = 350
        q_h = 130
        pos_x = setup_x + (setup_w - q_w) // 2
        pos_y = setup_y + (setup_h - q_h) // 2
        
        q_window.geometry(f"{q_w}x{q_h}+{pos_x}+{pos_y}")
        
        # 질문 메시지
        tk.Label(q_window, text="❓", font=("", 24)).pack(pady=(15, 5))
        tk.Label(q_window, text=message, wraplength=300).pack(pady=5)
        
        def on_yes():
            result[0] = True
            q_window.destroy()
        
        def on_no():
            result[0] = False
            q_window.destroy()
        
        btn_frame = tk.Frame(q_window)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="예", width=10, command=on_yes).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="아니오", width=10, command=on_no).pack(side=tk.LEFT, padx=5)
        
        q_window.bind("<Return>", lambda e: on_yes())
        q_window.bind("<Escape>", lambda e: on_no())
        
        q_window.wait_window()  # 창이 닫힐 때까지 대기
        return result[0]

    def insert_button_after(self, index):
        """특정 인덱스 다음에 버튼 추가"""
        # ★ 핵심: 추가 전에 현재 entries 값을 동기화
        self.sync_entries_to_global()
        
        insert_pos = index + 1
        button_names.insert(insert_pos, f"Button {len(button_names) + 1}")
        program_paths.insert(insert_pos, "")
        button_colors.insert(insert_pos, "#f0f0f0")
        self.refresh_entries()

    def move_button_up(self, index):
        """인덱스의 버튼을 한 칸 위로 이동 (Setup(0)은 고정)"""
        if index <= 1:
            self.show_centered_message("알림", "위로 이동할 수 없습니다.", "info")
            return
        self.sync_entries_to_global()
        button_names[index-1], button_names[index] = button_names[index], button_names[index-1]
        program_paths[index-1], program_paths[index] = program_paths[index], program_paths[index-1]
        if index < len(button_colors):
            button_colors[index-1], button_colors[index] = button_colors[index], button_colors[index-1]
        self.refresh_entries()

    def move_button_down(self, index):
        """인덱스의 버튼을 한 칸 아래로 이동"""
        if index >= len(button_names) - 1:
            self.show_centered_message("알림", "아래로 이동할 수 없습니다.", "info")
            return
        self.sync_entries_to_global()
        button_names[index+1], button_names[index] = button_names[index], button_names[index+1]
        program_paths[index+1], program_paths[index] = program_paths[index], program_paths[index+1]
        if index < len(button_colors)-1:
            button_colors[index+1], button_colors[index] = button_colors[index], button_colors[index+1]
        self.refresh_entries()

    def pick_color_for_setup(self, index):
        """셋업 창 내에서 색상을 선택. 스포이드는 열린 창의 '화면 색상 선택'을 이용하세요."""
        # ★ 핵심: 색상 선택 전에 현재 entries 값을 동기화
        self.sync_entries_to_global()
        
        current_color = button_colors[index]
        
        # askcolor 호출 시 initialcolor를 정확히 전달하면 
        # 대부분의 윈도우 환경에서 사용자 지정 색 영역이 활성화됩니다.
        _, color_code = colorchooser.askcolor(
            title=f"'{button_names[index]}' 색상 선택 (스포이드 활용)", 
            initialcolor=current_color
        )
        
        if color_code:
            button_colors[index] = color_code
            # 화면 전체를 새로고침(refresh_entries)하지 않고  
            # 현재 줄의 버튼 색상만 즉시 변경하여 깜빡임을 방지합니다.
            self.refresh_entries()

    def browse_file(self, index):
        """파일, 폴더, 또는 URL을 선택하는 다이얼로그"""
        # ★ 핵심: 브라우저 열기 전에 현재 entries 값을 동기화
        self.sync_entries_to_global()
        
        # 현재 경로 가져오기
        current_path = program_paths[index] if index < len(program_paths) else ""
        
        # 선택 창 생성
        choice_window = tk.Toplevel(self)
        choice_window.title("경로 선택")
        choice_window.transient(self)
        choice_window.grab_set()
        
        # Setup 창 위치 기준으로 중앙 배치
        self.update_idletasks()  # 위치 정보 업데이트
        setup_x = self.winfo_x()
        setup_y = self.winfo_y()
        setup_w = self.winfo_width()
        setup_h = self.winfo_height()
        
        choice_w = 150
        choice_h = 180
        
        # Setup 창 중앙에 배치
        pos_x = setup_x + (setup_w - choice_w) // 2
        pos_y = setup_y + (setup_h - choice_h) // 2
        
        choice_window.geometry(f"{choice_w}x{choice_h}+{pos_x}+{pos_y}")
        
        tk.Label(choice_window, text="선택하세요:", font=("", 10, "bold")).pack(pady=15)
        
        def select_file():
            choice_window.destroy()
            file_path = filedialog.askopenfilename(
                title="실행 파일 선택",
                initialdir=os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else os.path.expanduser("~"),
                filetypes=[
                    ("모든 파일", "*.*"),
                    ("실행 파일", "*.exe"),
                    ("배치 파일", "*.bat"),
                    ("바로가기", "*.lnk")
                ]
            )
            if file_path:
                entries[index][1].delete(0, tk.END)
                entries[index][1].insert(0, file_path)
        
        def select_folder():
            choice_window.destroy()
            folder_path = filedialog.askdirectory(
                title="폴더 선택",
                initialdir=os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else os.path.expanduser("~")
            )
            if folder_path:
                entries[index][1].delete(0, tk.END)
                entries[index][1].insert(0, folder_path)
        
        def enter_url():
            choice_window.destroy()
            
            # URL 입력 창 생성
            url_window = tk.Toplevel(self)
            url_window.title("URL 입력")
            url_window.transient(self)
            url_window.grab_set()
            
            # Setup 창 중앙에 배치
            url_w = 600
            url_h = 120
            url_x = setup_x + (setup_w - url_w) // 2
            url_y = setup_y + (setup_h - url_h) // 2
            url_window.geometry(f"{url_w}x{url_h}+{url_x}+{url_y}")
            
            tk.Label(url_window, text="웹 주소를 입력하세요:", font=("", 9)).pack(pady=(15, 5))
            tk.Label(url_window, text="(예: https://www.google.com)", font=("", 8), fg="gray").pack()
            
            url_entry = tk.Entry(url_window, width=70, font=("", 9))
            url_entry.pack(pady=10, padx=20)
            
            initial_value = current_path if current_path.startswith(('http://', 'https://')) else "https://"
            url_entry.insert(0, initial_value)
            url_entry.focus_set()
            url_entry.select_range(0, tk.END)
            
            def on_ok():
                url = url_entry.get().strip()
                if url:
                    entries[index][1].delete(0, tk.END)
                    entries[index][1].insert(0, url)
                url_window.destroy()
            
            def on_cancel():
                url_window.destroy()
            
            btn_frame = tk.Frame(url_window)
            btn_frame.pack(pady=5)
            
            tk.Button(btn_frame, text="확인", width=10, command=on_ok).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="취소", width=10, command=on_cancel).pack(side=tk.LEFT, padx=5)
            
            url_entry.bind("<Return>", lambda e: on_ok())
            url_entry.bind("<Escape>", lambda e: on_cancel())
        
        # 버튼들
        btn_frame = tk.Frame(choice_window)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="파일 선택", width=12, command=select_file).pack(pady=3)
        tk.Button(btn_frame, text="폴더 선택", width=12, command=select_folder).pack(pady=3)
        tk.Button(btn_frame, text="URL 입력", width=12, command=enter_url).pack(pady=3)

    def update_column_entry_state(self):
        state = tk.DISABLED if self.auto_columns_var.get() else tk.NORMAL
        self.columns_entry.configure(state=state)

    def apply_window_settings(self):
        new_width = max(45, safe_int(self.width_var.get(), launcher_position['width']))
        new_height = max(100, safe_int(self.height_var.get(), launcher_position['height']))
        launcher_position['width'] = new_width
        launcher_position['height'] = new_height

        layout_settings['auto_columns'] = self.auto_columns_var.get()
        layout_settings['column_count'] = max(1, safe_int(self.columns_var.get(), layout_settings['column_count']))
        layout_settings['gui_pad_x'] = max(0, safe_int(self.gui_pad_x_var.get(), layout_settings['gui_pad_x']))
        layout_settings['gui_pad_y'] = max(0, safe_int(self.gui_pad_y_var.get(), layout_settings['gui_pad_y']))
        layout_settings['button_pad_x'] = max(0, safe_int(self.button_pad_x_var.get(), layout_settings['button_pad_x']))
        layout_settings['button_pad_y'] = max(0, safe_int(self.button_pad_y_var.get(), layout_settings['button_pad_y']))

        root.geometry(f'{new_width}x{new_height}+{launcher_position["x"]}+{launcher_position["y"]}')
        apply_container_padding()
        update_buttons()

    def show_help(self):
        help_window = tk.Toplevel(self)
        help_window.title("Windows Launcher 도움말")
        help_window.geometry(
            f"600x561+{setup_position['x'] - 600}+{setup_position['y']}"
        )
    
        # ──────────────────────────────
        # 도움말 텍스트 (v3.4 업데이트)
        # ──────────────────────────────
        help_text = """
    Windows Launcher 사용법 v3.5

    이 프로그램은 Windows에서 빠르게 프로그램을 실행할 수 있는 런처입니다.
    멀티 모니터를 지원하며, 자동 숨김 기능이 있습니다.

    설정 창 설명:

    - Width: 런처 창의 너비를 픽셀 단위로 설정합니다. 최소 45px입니다.
    - Height: 런처 창의 높이를 픽셀 단위로 설정합니다. 최소 100px입니다.
    - Columns: 버튼을 배치할 열의 수를 수동으로 설정합니다.
    - Auto Columns: 창 높이에 따라 열 수를 자동으로 조정합니다.
    - GUI Pad X / Y: 런처 창 내부 여백 설정
    - Button Pad X / Y: 버튼 간 여백 설정

    버튼 관리:

    - 이름: 버튼에 표시될 텍스트입니다.
    - 경로: 실행할 파일, 폴더, 또는 URL입니다.
    - Color: 버튼 배경색 선택 (스포이드 가능)
    - Browse: 파일 / 폴더 / URL 선택
    - Del: 해당 버튼 삭제 (현재 값 자동 저장 후 삭제)
    - ▼+: 해당 버튼 아래에 새 버튼 추가 (현재 값 자동 저장 후 추가)
    - ▼ : 선택한 버튼을 아래로 한 칸 이동합니다.
      마지막 버튼에서는 더 이상 아래로 이동할 수 없습니다.
    - ▲ : 선택한 버튼을 위로 한 칸 이동합니다.
      단, 첫 번째 버튼(`Setup`)은 고정되어 위로 이동할 수 없습니다.
    - 이동이 불가능할 때는 안내 대화상자
      (예: "위로/아래로 이동할 수 없습니다.")가 표시됩니다.

    메인 기능:

    - 버튼 클릭 → 프로그램 실행
    - Setup 버튼 1초이상 눌러 드래그 → 런처창 전체 이동
    - 모니터 엣지 도킹 → 자동 숨김
    - 마우스 오버 → 자동 표시

    설정 저장:

    - Save: 변경사항 저장 (창 유지, 즉시 적용)
    - 닫기: 창 닫기
    - Alt + F4: 프로그램 종료 (설정 자동 저장)

    기타:

    - 멀티 모니터 지원: 여러 모니터를 인식합니다.
    - 설정 파일: C:\\Users\\[사용자명]\\launcher_config.json에 저장됩니다.
    - URL 지원: http:// 또는 https://로 시작하는 경로는 URL로 인식합니다.
    - 폴더 열기: 경로가 폴더면 탐색기로 엽니다.(예, C:\\ldmtemp, P:\\ldmtemp 등)
    - 색상 선택: 입력된 값을 자동으로 보존합니다.

    문의:

    - 한울교육훈련센터
    - sungkb04@khnp.co.kr
    """
    
        # ──────────────────────────────
        # 레이아웃 (Frame + grid 정의)
        # ──────────────────────────────
        help_window.rowconfigure(0, weight=1)
        help_window.columnconfigure(0, weight=1)
    
        container = tk.Frame(help_window)
        container.grid(row=0, column=0, sticky="nsew")
    
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
    
        text = tk.Text(
            container,
            wrap=tk.WORD,
            padx=8,
            pady=8
        )
        text.grid(row=0, column=0, sticky="nsew")
    
        scrollbar = tk.Scrollbar(
            container,
            orient="vertical",
            command=text.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
    
        text.config(yscrollcommand=scrollbar.set)
    
        # 내용 삽입 (하단 여백 방지)
        text.insert("1.0", help_text.strip())
        text.config(state=tk.DISABLED)


def open_program(index):
    path = program_paths[index]
    if not path:
        return

    if path.lower() in ('c:\\ldmtemp', 'p:\\ldmtemp'):
        try:
            subprocess.Popen(['explorer', path])
        except Exception as e:
            messagebox.showerror("Error", f"Error opening explorer: {e}")
        return

    is_url = (
        path.startswith(('http://', 'https://')) or
        ('.' in path and not os.path.exists(path))
    )

    if is_url:
        try:
            webbrowser.open(path)
        except Exception as e:
            messagebox.showerror("Error", f"Error opening URL: {e}")
    else:
        path = os.path.normpath(path)
        try:
            if os.path.isdir(path):
                subprocess.Popen(['explorer', path])
            else:
                subprocess.Popen(path, shell=True)
        except Exception as e:
            messagebox.showerror("Error", f"Error opening path: {e}")

def open_setup():
    setup_window = SetupWindow(root)
    setup_window.grab_set()

def apply_container_padding():
    if button_container is not None and button_container.winfo_manager():
        button_container.pack_configure(
            padx=layout_settings.get("gui_pad_x", 2),
            pady=layout_settings.get("gui_pad_y", 2)
        )

def determine_column_count(total_buttons):
    if total_buttons <= 0:
        return 1

    auto_mode = layout_settings.get("auto_columns", True)
    manual_columns = max(1, layout_settings.get("column_count", 1))

    if not auto_mode:
        return manual_columns

    available_height = launcher_position.get("height") or root.winfo_screenheight()
    approx_unit = max(1, ESTIMATED_BUTTON_HEIGHT)
    max_rows = max(1, available_height // approx_unit)

    needed_columns = math.ceil(total_buttons / max_rows)
    return max(1, needed_columns)

def update_buttons():
    if button_container is None: return

    for widget in button_container.winfo_children():
        widget.destroy()
    button_widgets.clear()

    total = len(button_names)
    if total == 0: return

    column_count = max(1, determine_column_count(total))
    rows_per_column = max(1, math.ceil(total / column_count))

    pad_x = layout_settings.get("button_pad_x", 2)
    pad_y = layout_settings.get("button_pad_y", 2)

    for index in range(total):
        # 저장된 색상 적용 (없으면 기본값)
        bg_color = button_colors[index] if index < len(button_colors) else "lightgray"
        
        if index == 0:
            button = tk.Button(button_container, text="Setup", command=open_setup, bg=bg_color)
            button.bind("<ButtonPress-1>", start_drag)
        elif program_paths[index]:
            button = tk.Button(
                button_container,
                text=button_names[index],
                command=lambda i=index: open_program(i),
                bg=bg_color
            )
        else:
            button = tk.Button(button_container, text=button_names[index], state="disabled", bg=bg_color)

        button_widgets.append(button)
        row = index % rows_per_column
        col = index // rows_per_column
        button.grid(row=row, column=col, padx=pad_x, pady=pad_y, sticky="nsew")


# 드래그를 위한 변수와 타이머 설정
dragging = False
press_time = 0
drag_button = None
_drag_check_id = None  # after() 취소용 ID

def start_drag(event):
    global press_time, dragging, drag_button, _drag_check_id
    drag_button = event.widget
    press_time = time.time()
    # 이전 pending 콜백이 있으면 취소 (누적 방지)
    if _drag_check_id is not None:
        try:
            root.after_cancel(_drag_check_id)
        except Exception:
            pass
    _drag_check_id = root.after(1000, check_drag)

def check_drag():
    global press_time, dragging, drag_button, _drag_check_id
    _drag_check_id = None
    if time.time() - press_time >= 1:
        dragging = True
        drag_button.bind("<B1-Motion>", do_drag)
        drag_button.bind("<ButtonRelease-1>", stop_drag)

def do_drag(event):
    if dragging:
        cancel_hide_schedule()
        cancel_show_schedule()
        stop_slide_animation()
        stop_fade_animation()
        root.attributes('-alpha', FADE_ALPHA_VISIBLE)
        _state["hidden"] = False
        x = event.x_root
        y = event.y_root
        root.geometry(f'+{x}+{y}')

def stop_drag(event):
    global dragging, _drag_check_id
    dragging = False
    # 혹시 남은 check_drag 타이머도 취소
    if _drag_check_id is not None:
        try:
            root.after_cancel(_drag_check_id)
        except Exception:
            pass
        _drag_check_id = None
    drag_button.unbind("<B1-Motion>")
    drag_button.unbind("<ButtonRelease-1>")
    evaluate_docking()

# ========= 자동 숨김 & 페이드(애니메이션) 유틸 =========

def stop_fade_animation():
    _state["animating_fade"] = False
    _state["target_alpha"] = None

def stop_slide_animation():
    _state["animating_slide"] = False
    _state["target_x"] = None

def cancel_hide_schedule():
    if _state["hide_scheduled"] is not None:
        try:
            root.after_cancel(_state["hide_scheduled"])
        except Exception:
            pass
        _state["hide_scheduled"] = None

def cancel_show_schedule():
    if _state["show_scheduled"] is not None:
        try:
            root.after_cancel(_state["show_scheduled"])
        except Exception:
            pass
        _state["show_scheduled"] = None

def schedule_delayed_show():
    cancel_show_schedule()

    def trigger():
        _state["show_scheduled"] = None
        if mouse_inside_window():
            show_launcher()

    _state["show_scheduled"] = root.after(SHOW_DELAY_MS, trigger)

def get_window_bbox():
    """현재 창의 화면 좌표 bbox (x1,y1,x2,y2)"""
    x1 = root.winfo_x()
    y1 = root.winfo_y()
    x2 = x1 + root.winfo_width()
    y2 = y1 + root.winfo_height()
    return x1, y1, x2, y2

def mouse_inside_window():
    px = root.winfo_pointerx()
    py = root.winfo_pointery()
    x1, y1, x2, y2 = get_window_bbox()
    return (x1 <= px <= x2) and (y1 <= py <= y2)

def fade_to(target_alpha):
    if _state["animating_fade"] and _state["target_alpha"] == target_alpha:
        return
    _state["animating_fade"] = True
    _state["target_alpha"] = target_alpha

    def step():
        if not _state["animating_fade"]:
            return
        try:
            if not root.winfo_exists():
                stop_fade_animation()
                return
            current = float(root.attributes('-alpha'))
            diff = target_alpha - current
            if abs(diff) <= FADE_STEP:
                root.attributes('-alpha', target_alpha)
                stop_fade_animation()
                return
            root.attributes('-alpha', current + (FADE_STEP if diff > 0 else -FADE_STEP))
            root.after(FADE_INTERVAL_MS, step)
        except Exception:
            stop_fade_animation()

    step()

def slide_to(target_x):
    if _state["animating_slide"] and _state["target_x"] == target_x:
        return
    _state["animating_slide"] = True
    _state["target_x"] = target_x

    def step():
        if not _state["animating_slide"]:
            return
        try:
            if not root.winfo_exists():
                stop_slide_animation()
                return
            x = root.winfo_x()
            y = root.winfo_y()
            diff = target_x - x
            if abs(diff) <= SLIDE_STEP_PX:
                root.geometry(f"+{target_x}+{y}")
                stop_slide_animation()
                return
            x_next = x + (SLIDE_STEP_PX if diff > 0 else -SLIDE_STEP_PX)
            root.geometry(f"+{x_next}+{y}")
            root.after(SLIDE_INTERVAL_MS, step)
        except Exception:
            stop_slide_animation()

    step()

def evaluate_docking():
    """드래그 후 가장 가까운 엣지로 스냅"""
    x = root.winfo_x()
    y = root.winfo_y()
    w = root.winfo_width()
    h = root.winfo_height()
    
    result = find_nearest_edge(x, y, w, h)
    
    if result:
        monitor_idx, edge, snap_x = result
        _state["docked_edge"] = edge
        _state["docked_monitor"] = monitor_idx
        # 스냅 위치로 즉시 이동
        root.geometry(f"+{snap_x}+{y}")
        print(f"Docked to Monitor {monitor_idx + 1} {edge} edge")
    else:
        _state["docked_edge"] = None
        _state["docked_monitor"] = None

def compute_positions_for_dock():
    """현재 도킹된 엣지에 대한 visible/hidden x 좌표 계산"""
    if _state["docked_edge"] is None or _state["docked_monitor"] is None:
        return None, None
    
    monitors = get_monitors_info()
    if _state["docked_monitor"] >= len(monitors):
        return None, None
    
    mon = monitors[_state["docked_monitor"]]
    w = root.winfo_width()
    
    if _state["docked_edge"] == 'left':
        visible_x = mon['left']
        hidden_x = mon['left'] - w + PEEK_EXPOSE_PX
    else:  # 'right'
        visible_x = mon['right'] - w
        hidden_x = mon['right'] - PEEK_EXPOSE_PX
    
    return visible_x, hidden_x

def show_launcher():
    """슬라이드 인 + 페이드 인"""
    cancel_hide_schedule()
    cancel_show_schedule()
    
    if _state["docked_edge"] is not None:
        visible_x, hidden_x = compute_positions_for_dock()
        if visible_x is not None:
            slide_to(visible_x)
    
    fade_to(FADE_ALPHA_VISIBLE)
    _state["hidden"] = False

def hide_launcher():
    """슬라이드 아웃 + 페이드 아웃(반투명)"""
    cancel_show_schedule()
    
    if _state["docked_edge"] is not None:
        visible_x, hidden_x = compute_positions_for_dock()
        if hidden_x is not None:
            slide_to(hidden_x)
    
    fade_to(FADE_ALPHA_HIDDEN)
    _state["hidden"] = True

def schedule_hide_if_outside():
    """마우스가 창 밖에 계속 있으면 숨김 실행"""
    cancel_hide_schedule()
    def decide():
        if not mouse_inside_window():
            hide_launcher()
    _state["hide_scheduled"] = root.after(HIDE_DELAY_MS, decide)

def on_mouse_enter(event=None):
    cancel_hide_schedule()
    if _state["docked_edge"] is not None and _state["hidden"]:
        schedule_delayed_show()
    else:
        cancel_show_schedule()
        show_launcher()

def on_mouse_leave(event=None):
    cancel_show_schedule()
    schedule_hide_if_outside()

# ========== 메인 윈도우 설정 ==========
root = tk.Tk()
root.overrideredirect(True)
root.attributes('-topmost', True)
root.attributes('-toolwindow', True)  # 작업표시줄에서 숨김

load_settings()

root.geometry(f'{launcher_position["width"]}x{launcher_position["height"]}+{launcher_position["x"]}+{launcher_position["y"]}')
root.configure(bg='lightgray')
root.bind("<Configure>", update_window_state)

button_container = tk.Frame(root, bg='lightgray')
button_container.pack(fill=tk.BOTH, expand=True)
apply_container_padding()

button_widgets = []
update_buttons()

# 초기 도킹 판정 및 숨김 상태 배치
root.update_idletasks()

# 초기에는 잠시 완전 보이는 상태로 시작 (0.5초 대기)
root.attributes('-alpha', FADE_ALPHA_VISIBLE)
_state["hidden"] = False

def delayed_initial_docking():
    """프로그램 시작 후 0.5초 뒤에 도킹 상태 확인 및 숨김 처리"""
    global _monitors_cache, _monitors_cache_key
    # 부팅 직후 해상도가 아직 최종값이 아닐 수 있으므로 캐시 강제 갱신
    _monitors_cache = None
    _monitors_cache_key = None

    evaluate_docking()
    
    # 도킹되어 있으면 숨긴 상태로 전환
    if _state["docked_edge"] is not None:
        vx, hx = compute_positions_for_dock()
        if hx is not None:
            y = root.winfo_y()
            root.geometry(f'+{hx}+{y}')
            root.update_idletasks()
            current_x = root.winfo_x()
            monitors = get_monitors_info()
            if _state["docked_monitor"] < len(monitors):
                mon = monitors[_state["docked_monitor"]]
                w = root.winfo_width()
                if _state["docked_edge"] == 'left':
                    min_x = mon['left'] - w + PEEK_EXPOSE_PX
                    if current_x < min_x:
                        root.geometry(f'+{min_x}+{y}')
                elif _state["docked_edge"] == 'right':
                    max_x = mon['right'] - PEEK_EXPOSE_PX
                    if current_x > max_x:
                        root.geometry(f'+{max_x}+{y}')
        
        root.attributes('-alpha', FADE_ALPHA_HIDDEN)
        _state["hidden"] = True
        print(f"Initial state: Docked to {_state['docked_edge']} edge (hidden with {PEEK_EXPOSE_PX}px visible)")
    else:
        # 도킹 안 된 경우: 화면 안에 있는지 확인 후 필요하면 강제 이동
        monitors = get_monitors_info()
        x = root.winfo_x()
        y = root.winfo_y()
        w = root.winfo_width()
        h = root.winfo_height()
        on_screen = any(
            mon['left'] <= x + w // 2 <= mon['right'] and
            mon['top']  <= y + h // 2 <= mon['bottom']
            for mon in monitors
        )
        if not on_screen and monitors:
            mon = monitors[0]
            nx = mon['left'] + (mon['width']  - w) // 2
            ny = mon['top']  + (mon['height'] - h) // 2
            root.geometry(f'+{nx}+{ny}')
            print(f"Position corrected to on-screen: +{nx}+{ny}")
        print("Initial state: Not docked (fully visible)")

# 0.5초 후에 초기 도킹 처리 실행
root.after(500, delayed_initial_docking)

# 마우스 진입/이탈 이벤트
root.bind("<Enter>", on_mouse_enter)
root.bind("<Leave>", on_mouse_leave)

# 프로그램 종료 시 설정 저장
root.protocol("WM_DELETE_WINDOW", lambda: (save_settings(), root.quit()))

print("=" * 50)
print("Multi-Monitor Launcher Started v3.5")
print("=" * 50)
if MULTI_MONITOR_SUPPORT:
    monitors = get_monitors_info()
    print(f"Detected {len(monitors)} monitor(s):")
    for idx, mon in enumerate(monitors):
        print(f"  Monitor {idx + 1}: {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})")
else:
    print("Running in single-monitor mode (install pywin32 for multi-monitor support)")
print("=" * 50)

root.mainloop()