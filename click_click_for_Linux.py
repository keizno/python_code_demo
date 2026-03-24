# sudo apt-get install python3-tk scrot x11-xserver-utils libgl1 libglib2.0-0 python3-xlib
# sudo apt install python3-pip
# pip3 install Pillow numpy pyautogui pynput opencv-python --break-system-packages
# sudo apt-get install python3-pil.imagetk
# usr/bin/python3 "/home/keizno/바탕화면/click_click_for_Linux.py"

### 설치 가이드 Linux for ARM
# 1. 시스템 필수 패키지 및 OpenCV, Numpy를 apt로 안전하게 설치
# sudo apt-get update
# sudo apt-get install python3-tk scrot x11-xserver-utils libgl1 libglib2.0-0 python3-xlib python3-opencv python3-numpy python3-pil.imagetk

# 2. 나머지 라이브러리만 pip로 설치
# pip3 install Pillow pyautogui pynput --break-system-packages

# kasm에서는 파이썬과 모듈 추가 설치 필요..
# sudo apt update
# sudo apt install python3 python3-pip
# 캡처 실패함..아래와 같이 추가설치..@kasm
# sudo apt install gnome-screenshot
# 카즘에서 정상작동함..

import tkinter as tk
import threading
import time
import sys
import pyautogui
import os
import json
import numpy as np
from PIL import Image, ImageTk
from tkinter import simpledialog, messagebox
from datetime import datetime
import gc
import ctypes
from pynput import keyboard as pynput_keyboard
import copy

# 화면 보호기를 비활성화하는 상수
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

# 전역 변수
# === 상태 이벤트 ===
running = False
monitoring_thread = None
monitoring_event = threading.Event()
shutdown_event = threading.Event()
capturing_mode = False
capture_step = 0  # 0: 대기 중, 1: 트리거 캡처 중, 2: 타겟 캡처 중
# 전역 변수에 캡처 크기 배율 추가 (트리거/타겟 개별 설정)
capture_size_multiplier = 1  # 기본값: 보통(x1) - 하위호환성 유지
trigger_capture_multiplier = 1  # 트리거 이미지 캡처 배율
target_capture_multiplier = 1   # 타겟 이미지 캡처 배율
app = None  # 전역 앱 인스턴스 변수 추가
profile_switching = False  # 프로필 전환 중인지 여부 플래그 추가

# ========== 프로필 관리 전역 변수 ==========
current_profile_name = "default"  # 현재 활성 프로필명
all_profiles = {}  # 모든 프로필 데이터

def prevent_screen_saver():
    """화면 보호기 실행을 방지하는 함수"""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            os.system("xset s off -dpms")
        except Exception:
            pass

def restore_screen_saver():
    """화면 보호기 설정을 원래대로 복원하는 함수"""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            os.system("xset s on +dpms")
        except Exception:
            pass

# 메모리 정리 함수
def clean_memory():
    gc.collect()
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1)


# 주기적으로 메모리 정리 실행
def start_memory_cleaner():
    def memory_cleaner():
        while not shutdown_event.is_set():
            time.sleep(120)
            clean_memory()
    threading.Thread(target=memory_cleaner, daemon=True).start()


# 화면 활성 상태 유지를 위한 함수 추가
def keep_screen_active():
    """주기적으로 마우스를 살짝 움직이고 키 입력을 시뮬레이션하여 화면을 활성 상태로 유지"""
    try:
        while running:
            # 현재 마우스 위치 저장
            current_x, current_y = pyautogui.position()
            
            # 마우스를 살짝 움직인 후 원래 위치로 복귀
            pyautogui.moveRel(1, 0, duration=0.1)
            pyautogui.moveRel(-1, 0, duration=0.1)
            
            # Shift 키를 누르고 떼는 시뮬레이션 (화면에 영향 없음)
            pyautogui.press('shift')
            
            # 화면 보호기 방지 함수 다시 호출 (일부 시스템에서 필요)
            prevent_screen_saver()
            
            # 60초마다 실행 (너무 자주 하면 시스템 부하 증가)
            time.sleep(60)
    except Exception as e:
        print(f"화면 활성화 오류: {e}")

# 설정 파일 경로 
#CONFIG_FILE = os.path.expanduser("~") + "\\click_config.json"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), "click_config.json")
# 임시 캡처 데이터
temp_trigger_data = None
temp_target_data = None

# 이미지 쌍 저장소
image_pairs = []

# 로그 UI 변수
log_text = None

# 마우스 위치 주변의 화면 영역 캡처 및 픽셀 데이터로 변환
# 기존 capture_screen_region 함수 수정 배율적용..
def capture_screen_region(x, y, width=60, height=25, multiplier=1):
    try:
        # 전달된 multiplier를 사용, 없으면 기본값 1
        adjusted_width = width * multiplier
        adjusted_height = height * multiplier
        
        # 마우스 위치 중심으로 캡처 영역 계산
        left = max(0, x - adjusted_width // 2)
        top = max(0, y - adjusted_height // 2)
        
        # 스크린샷 촬영
        screenshot = pyautogui.screenshot(region=(left, top, adjusted_width, adjusted_height))
        
        # 픽셀 데이터 추출
        pixel_data = []
        for y_pos in range(screenshot.height):
            row = []
            for x_pos in range(screenshot.width):
                r, g, b = screenshot.getpixel((x_pos, y_pos))
                row.append([r, g, b])
            pixel_data.append(row)
        
        capture_info = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "position": {"x": x, "y": y},
            "region": {"left": left, "top": top, "width": adjusted_width, "height": adjusted_height},
            "pixel_data": pixel_data
        }
        
        return capture_info, screenshot
    except Exception as e:
        print(f"화면 캡처 오류: {e}")
        return None, None

# 픽셀 데이터에서 PIL 이미지로 변환
def pixel_data_to_image(pixel_data):
    try:
        if not pixel_data:
            return None
            
        height = len(pixel_data)
        width = len(pixel_data[0]) if height > 0 else 0
        
        if height == 0 or width == 0:
            return None
            
        # [최적화] numpy를 사용하여 고속 변환
        try:
            array = np.array(pixel_data, dtype=np.uint8)
            return Image.fromarray(array)
        except Exception:
            # numpy 변환 실패 시 기존 방식(느림) 사용
            img = Image.new('RGB', (width, height))
            for y in range(height):
                for x in range(width):
                    r, g, b = pixel_data[y][x]
                    img.putpixel((x, y), (r, g, b))
            return img
    except Exception as e:
        print(f"이미지 변환 오류: {e}")
        return None

# ========== 프로필 관리 함수 ==========
def reset_capture_state(app=None):
    global temp_trigger_data, temp_target_data, capturing_mode, capture_step
    temp_trigger_data = None
    temp_target_data = None
    capturing_mode = False
    capture_step = 0
    if app:
        app.capture_button.config(text="이미지 쌍 캡처 시작")
        app.hide_capture_preview()


def load_all_profiles():
    """모든 프로필을 파일에서 로드"""
    global all_profiles, current_profile_name, image_pairs, trigger_capture_multiplier, target_capture_multiplier
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # ========== 이전 버전 호환성 체크 ==========
                # 새 버전 형식인지 확인 (profiles 키가 있으면 새 버전)
                if "profiles" in data:
                    # 새 버전 형식
                    all_profiles = data.get("profiles", {})
                    current_profile_name = data.get("current_profile", "default")
                else:
                    # ========== 구버전 형식 감지 -> 자동 마이그레이션 ==========
                    print("구버전 설정 파일 감지 - default 프로필로 마이그레이션 중...")
                    old_multiplier = data.get("capture_size_multiplier", 1)
                    all_profiles = {
                        "default": {
                            "image_pairs": data.get("image_pairs", []),
                            "trigger_capture_multiplier": old_multiplier,
                            "target_capture_multiplier": old_multiplier
                        }
                    }
                    current_profile_name = "default"
                    print("마이그레이션 완료 - 기존 데이터가 'default' 프로필로 저장되었습니다.")
                
                # 기본 프로필이 없으면 생성
                if not all_profiles:
                    all_profiles["default"] = {
                        "image_pairs": [],
                        "trigger_capture_multiplier": 1,
                        "target_capture_multiplier": 1
                    }
                
                # 현재 프로필 로드
                load_profile(current_profile_name)
                return True
        else:
            # 파일이 없으면 기본 프로필 생성
            all_profiles["default"] = {
                "image_pairs": [],
                "trigger_capture_multiplier": 1,
                "target_capture_multiplier": 1
            }
            current_profile_name = "default"
            load_profile("default")
    except Exception as e:
        print(f"프로필 로드 오류: {e}")
    return False

def save_all_profiles():
    """모든 프로필을 파일에 저장"""
    try:
        # 현재 작업중인 데이터를 현재 프로필에 저장
        save_current_to_profile()
        
        data = {
            "current_profile": current_profile_name,
            "profiles": all_profiles
        }
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"프로필 저장 오류: {e}")
        return False

def save_current_to_profile():
    """현재 UI의 정밀도 및 간격 설정을 포함하여 프로필에 저장"""
    global all_profiles, current_profile_name, image_pairs, trigger_capture_multiplier, target_capture_multiplier
    
    # UI에서 현재 값 가져오기 (비어있거나 에러 시 기본값 사용)
    try:
        t_conf = float(app.trigger_conf_entry.get())
    except: t_conf = 0.8
    try:
        tar_conf = float(app.target_conf_entry.get())
    except: tar_conf = 0.9
    try:
        interval = float(app.interval_entry.get())
    except: interval = 5.0
    
    profile_data = {
        "trigger_capture_multiplier": trigger_capture_multiplier,
        "target_capture_multiplier": target_capture_multiplier,
        "trigger_confidence": t_conf,
        "target_confidence": tar_conf,
        "monitoring_interval": interval,
        "image_pairs": []
    }
    
    # 기존 image_pairs 저장 로직
    for pair in image_pairs:
        trigger = pair.get("trigger", {})
        target = pair.get("target", {})
        profile_data["image_pairs"].append({
            "trigger": trigger,
            "target": target,
            "timestamp": pair.get("timestamp", ""),
            "description": pair.get("description", "설명 없음"),
            "action_delay": pair.get("action_delay", 0)
        })
    
    all_profiles[current_profile_name] = profile_data

def load_profile(profile_name):
    """특정 프로필을 로드하고 UI 항목들을 업데이트"""
    global image_pairs, trigger_capture_multiplier, target_capture_multiplier, current_profile_name, all_profiles, capturing_mode, capture_step
    
    if profile_name not in all_profiles:
        return False
    
    # 프로필 로드 전에 캡처 상태 완전히 초기화
    capturing_mode = False
    capture_step = 0
    
    profile_data = all_profiles[profile_name]
    current_profile_name = profile_name
    
    image_pairs = profile_data.get("image_pairs", [])
    # 트리거/타겟 개별 배율 로드 (하위호환성: 기존 capture_size_multiplier 사용)
    trigger_capture_multiplier = profile_data.get("trigger_capture_multiplier", 
                                                    profile_data.get("capture_size_multiplier", 1))
    target_capture_multiplier = profile_data.get("target_capture_multiplier", 
                                                   profile_data.get("capture_size_multiplier", 1))
    
    # UI 엔트리 값 업데이트
    if app:
        app.trigger_conf_entry.delete(0, tk.END)
        app.trigger_conf_entry.insert(0, str(profile_data.get("trigger_confidence", 0.8)))
        
        app.target_conf_entry.delete(0, tk.END)
        app.target_conf_entry.insert(0, str(profile_data.get("target_confidence", 0.9)))
        
        app.interval_entry.delete(0, tk.END)
        app.interval_entry.insert(0, str(profile_data.get("monitoring_interval", 5.0)))
        
        # UI에 트리거/타겟 배율 업데이트
        app.update_capture_size_display()
    
    # 이미지 데이터 복원
    for pair in image_pairs:
        pair["_trigger_img"] = pixel_data_to_image(pair["trigger"]["pixel_data"])
        pair["_target_img"] = pixel_data_to_image(pair["target"]["pixel_data"])
    
    return True

def create_new_profile(profile_name):
    """새 프로필 생성"""
    global all_profiles
    
    if profile_name in all_profiles:
        return False  # 이미 존재
    
    all_profiles[profile_name] = {
        "image_pairs": [],
        "trigger_capture_multiplier": 1,
        "target_capture_multiplier": 1
    }
    return True

def delete_profile(profile_name):
    """프로필 삭제"""
    global all_profiles, current_profile_name
    
    if profile_name == "default":
        return False  # 기본 프로필은 삭제 불가
    
    if profile_name not in all_profiles:
        return False
    
    del all_profiles[profile_name]
    
    # 삭제한 프로필이 현재 프로필이면 default로 전환
    if current_profile_name == profile_name:
        load_profile("default")
    
    return True

def get_profile_names():
    """모든 프로필명 리스트 반환"""
    return list(all_profiles.keys())

# 설정 파일에서 로드 (호환성 유지)
def load_config():
    return load_all_profiles()

# === 수정된 save_config 함수 (호환성 유지) ===
def save_config():
    return save_all_profiles()

# === 수정된 save_captured_pair 함수 ===
#def save_captured_pair(app, description=None):
#    global temp_trigger_data, temp_target_data, image_pairs
#    
#    if temp_trigger_data and temp_target_data:
#        # 이미지 쌍 구성 (save_config에서 기대하는 구조로 전달)
#        image_pair = {
#            "trigger": temp_trigger_data,
#            "target": temp_target_data,
#            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#            "description": description or "설명 없음"
#        }
#        
#        # 내부 메모리용 이미지 객체 생성 (GUI 표시용)
#        image_pair["_trigger_img"] = pixel_data_to_image(temp_trigger_data["pixel_data"])
#        image_pair["_target_img"] = pixel_data_to_image(temp_target_data["pixel_data"])
#        
#        image_pairs.append(image_pair)
#        
#        # 임시 데이터 초기화 (다음 캡처를 위해)
#        temp_trigger_data = None
#        temp_target_data = None
#        
#        if save_config():
#            app.status_callback(f"이미지 쌍 #{len(image_pairs)} 저장 완료!")
#            app.update_image_list()
#            return True
#        else:
#            app.status_callback("JSON 파일 쓰기 실패 (권한 또는 데이터 오류)")
#    else:
#        app.status_callback("캡처 데이터가 불완전합니다.")
#    return False

# 기존 save_captured_pair 함수를 이 내용으로 교체하세요.
def save_captured_pair(app, description=None):
    global temp_trigger_data, temp_target_data, image_pairs
    
    if temp_trigger_data and temp_target_data:
        image_pair = {
            "trigger": temp_trigger_data,
            "target": temp_target_data,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": description or "설명 없음",
            "action_delay": 0  # 기본값: 0초 (즉시 동작)
        }
        
        # 이미지 객체 생성 (메모리용)
        image_pair["_trigger_img"] = pixel_data_to_image(temp_trigger_data["pixel_data"])
        image_pair["_target_img"] = pixel_data_to_image(temp_target_data["pixel_data"])
        
        image_pairs.append(image_pair)
        
        # 캡처 직후 즉시 파일 저장!
        if save_config():
            app.status_callback(f"이미지 쌍 #{len(image_pairs)} 저장 및 파일 기록 완료!")
        else:
            app.status_callback("이미지는 등록됐으나 파일 저장 실패 (구조 에러)")

        temp_trigger_data = None
        temp_target_data = None
        app.update_image_list()
        return True
    return False

# 메인 스레드에서 설명 입력 대화 상자 표시
def ask_description_in_main_thread(app):
    description = simpledialog.askstring("설명", "이 이미지 쌍에 대한 설명을 입력하세요:", parent=app.root)
    
    # 이미지 쌍 저장
    save_captured_pair(app, description)
    
    # 캡처 모드 종료
    global capturing_mode, capture_step
    capturing_mode = False
    capture_step = 0
    app.capture_button.config(text="이미지 쌍 캡처 시작")


# 화면에서 이미지 패턴 찾기
def find_pattern_on_screen(pixel_data, confidence=0.8):
    try:
        # 픽셀 데이터에서 PIL 이미지로 변환
        needle_img = pixel_data_to_image(pixel_data)
        
        if needle_img is None:
            return None
        
        # 화면에서 이미지 찾기
        location = pyautogui.locateCenterOnScreen(needle_img, confidence=confidence)
        return location
    except Exception as e:
        print(f"패턴 검색 오류: {e}")
        return None

def get_interval(entry, default=5, min_value=5):
    try:
        v = float(entry.get())
        return max(v, min_value)
    except ValueError:
        return default


def safe_sleep(seconds, event_to_wait):
    """event_to_wait가 set되어 있는 동안에만 sleep하며, 0.1초마다 중단 여부를 체크 (정밀도 향상)"""
    start_time = time.time()
    while (time.time() - start_time) < seconds:
        # 모니터링이 꺼지면 즉시 대기 중단
        if not event_to_wait.is_set() or shutdown_event.is_set():
            return False
        # 0.1초 단위로 대기하여 반응성 및 소수점 시간 정밀도 향상
        time.sleep(0.1)
    return True


# 캡처 모드 시작/중지 토글
def toggle_capture_mode(app):
    global capturing_mode, capture_step

    if monitoring_event.is_set():   
        app.status_callback("모니터링 중에는 캡처할 수 없습니다.")
        return

    
    if not capturing_mode:
        capturing_mode = True
        capture_step = 1  # 트리거 이미지 캡처 단계

        # (pynput 글로벌 리스너 사용으로 동적 핫키 등록 불필요)
        
        app.status_callback("캡처 모드 시작: 트리거 이미지 위치에서 F8를 누르세요.")
        app.capture_button.config(text="캡처 모드 취소")
        
        # 미리보기 창 표시
        app.show_capture_preview()
    else:
        capturing_mode = False
        capture_step = 0
        app.status_callback("캡처 모드가 취소되었습니다.")
        app.capture_button.config(text="이미지 쌍 캡처 시작")
        
        # 미리보기 창 숨기기
        app.hide_capture_preview()

# GUI 애플리케이션
class AutoClickerApp:

    def show_help(self):
            """프로그램 사용법 안내 창 표시 (메인 창 좌측에 배치 및 들여쓰기 적용)"""
            help_win = tk.Toplevel(self.root)
            help_win.title("도움말 및 사용법")
            
            # --- [1] GUI 위치 설정 (메인 창의 왼쪽 절반 지점) ---
            self.root.update_idletasks() # 최신 위치 정보를 위해 업데이트
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            
            help_width = 550
            help_height = 750 # 내용이 늘어날 것에 대비해 약간 키움
            
            # 메인창 왼쪽 끝에서 창 너비만큼 왼쪽으로 이동
            pos_x = main_x - help_width - 10 # 10픽셀 정도 여유 간격
            if pos_x < 0: pos_x = 0 # 화면 밖으로 나가지 않게 조절
            pos_y = main_y
            
            help_win.geometry(f"{help_width}x{help_height}+{pos_x}+{pos_y}")
            
            # --- [2] 텍스트 레이아웃 ---
            text_frame = tk.Frame(help_win)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            scrollbar = tk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # spacing1(줄 사이 간격), spacing2(줄 바꿈 간격), spacing3(문단 간격) 설정
            help_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, 
                                font=("맑은 고딕", 10), spacing1=4, spacing3=4)
            help_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=help_text.yview)
    
            # 모든 줄의 시작 부분에 공백 4칸을 추가하여 전체 들여쓰기 적용
            guide = """
        [ 프로그램 주요 기능 ]
        • 이미지 기반 자동 클릭 도구입니다.
        • 특정 '트리거' 이미지가 화면에 나타나면, 설정된 '타겟' 위치를 자동으로
          클릭합니다.
        • 여러 개의 이미지 쌍을 순차적으로 감시할 수 있습니다.
    
        [ 버튼별 상세 기능 ]
        1. 이미지 쌍 캡처 시작
        - 1단계: 트리거(감시할 이미지)에 마우스를 올리고, F8을 누른 뒤
          마우스를 살짝 옆으로 비켜 둡니다. 2초 후에 캡처합니다.
        - 2단계: 타겟(클릭할 대상 이미지)에 마우스를 올리고, F8을 누른 뒤
          마우스를 옆으로 비켜 둡니다. 역시 2초 후 캡처합니다.
        - 마우스를 비켜두는 이유는, 대상이미지의 색상변경에 대응하기 위해서 입니다.
        * 캡처 중 ESC를 누르면 취소됩니다.
    
        2. 모니터링 시작/중지
        - 설정된 간격(초)마다 화면을 스캔하여 작동을 시작합니다.
        - 켜진 상태에서는 설정된 정밀도로 이미지를 찾습니다.
    
        3. 정밀도 및 간격 설정
        - 트리거/타겟: 0.0 ~ 1.0 사이 값 (높을수록 엄격하게 검사)
        - 간격(초): 이미지 검사 사이의 대기 시간입니다. 기본은 5초 입니다.
        - 초기화: 설정을 기본값(0.8, 0.9, 5.0)으로 되돌립니다.
    
        4. 프로필 관리
        - 추가/삭제: 작업별 설정 리스트를 관리합니다.
        - 사용자 홈폴더에 설정파일이 있고, 저장됩니다. (click_config.json)
    
        [ 사용 순서 ]
        1. '프로필 추가'로 새 작업을 만듭니다. 
        2. '이미지 쌍 캡처 시작 버튼을 누릅니다' F8을 2회 눌러 이미지 쌍을
           등록합니다.
        3. 간격(초)을 설정합니다. (첫 검사 전에도 이 시간만큼 대기합니다.)
        4. '모니터링 시작'을 눌러 작동시킵니다.
    
        [ 주의 사항 ]
        - 창이 가려져 있으면 이미지를 찾을 수 없습니다.
        - 정밀도가 너무 높으면(1.0) 조금만 달라도 클릭하지 않습니다.
        - '검사 간격'은 최소 5초 이상을 권장합니다.
        - 프로그램 실행중에는 화면보호기를 비활성화 합니다. (종료시 복귀)
        - 등록된 이미지 쌍을 더블클릭하면 미리보기 창에서 확인가능합니다.

        [ 작성자 ]
        - sungkb04@khnp.co.kr
          """
            help_text.insert(tk.END, guide)
            help_text.config(state=tk.DISABLED) # 읽기 전용 모드
    
            tk.Button(help_win, text="닫기", command=help_win.destroy, width=15).pack(pady=10)
    
            
    def move_up(self):
        """선택된 항목을 위로 한 칸 이동"""
        selected = self.image_listbox.curselection()
        if not selected or selected[0] == 0:
            return
        
        idx = selected[0]
        # 리스트 내 위치 교환
        image_pairs[idx], image_pairs[idx-1] = image_pairs[idx-1], image_pairs[idx]
        self.refresh_after_reorder(idx - 1)

    def move_down(self):
        """선택된 항목을 아래로 한 칸 이동"""
        selected = self.image_listbox.curselection()
        if not selected or selected[0] == len(image_pairs) - 1:
            return
        
        idx = selected[0]
        # 리스트 내 위치 교환
        image_pairs[idx], image_pairs[idx+1] = image_pairs[idx+1], image_pairs[idx]
        self.refresh_after_reorder(idx + 1)

    def refresh_after_reorder(self, new_selection_idx):
        """순서 변경 후 UI 및 설정 파일 동기화"""
        save_config()
        self.update_image_list()
        self.image_listbox.selection_set(new_selection_idx)
        # 선택된 항목의 미리보기도 즉시 업데이트
        self.on_image_select(None) # [수정] 더블클릭(설정창) 대신 선택(미리보기) 함수 호출
        self.status_callback(f"항목 순서가 변경되었습니다 (현재 위치: {new_selection_idx + 1})")

    def resource_path(self, relative_path):
        """리소스 파일의 절대 경로를 반환하는 함수"""
        try:
            # PyInstaller가 만든 _MEIPASS 사용
            base_path = sys._MEIPASS
        except Exception:
            # 일반 Python 환경에서는 현재 디렉토리 사용
            base_path = os.path.abspath(".")
        
        return os.path.join(base_path, relative_path)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # 리눅스 환경에서 withdraw() 상태일 때 창 크기가 1x1로 계산되는 버그 방지
        if width < 100 or height < 100:
            width = 1000
            height = 800
            
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.root.title("Click_Click_v4.4 by sungkb04@khnp.co.kr")
        # 아이콘 설정
        try:
            icon_path = self.resource_path("click_click_auto.ico")
            if os.path.exists(icon_path):
                if sys.platform == "win32":
                    self.root.iconbitmap(icon_path)
                else:
                    self.root.iconphoto(True, ImageTk.PhotoImage(Image.open(icon_path)))
        except Exception as e:
            print(f"아이콘 로딩 오류: {e}")
            # 아이콘 파일이 없을 경우 무시
            pass     
        self.root.geometry("1000x800")
        self.root.resizable(True, True)
        
        # 전역 앱 인스턴스 저장
        global app
        app = self
        
        # [추가] 스레드 안전성을 위한 설정값 저장소
        self.thread_safe_config = {
            "interval": 5.0,
            "trigger_conf": 0.8,
            "target_conf": 0.9
        }
        
        # 글로벌 단축키 리스너 시작 (pynput)
        self.start_hotkey_listener()
        
        self.setup_ui()
    
        # 기존 설정 로드
        if load_config():
            self.status_callback(f"{len(image_pairs)}개의 저장된 이미지 쌍을 로드했습니다.")
            self.update_image_list()

            # 🔴 [추가] 현재 프로필명 UI 반영
            self.current_profile_label.config(
                text=f"현재 프로필: {current_profile_name}"
            )
            
            # 캡처 크기 설정 복원 (트리거/타겟 개별)
            self.update_capture_size_display()
            self.status_callback(f"캡처 배율 설정이 복원되었습니다.")
        else:
            self.status_callback("저장된 설정 파일이 없어 기본 설정으로 시작합니다. (첫 실행 시 정상)")


        # 2. 모든 설정이 끝난 후 창을 중앙에 배치하고 보여줍니다
        self.center_window()
        self.root.deiconify() 
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        
        # 이미지 쌍 미리보기 프레임 설정
        self.setup_preview_frame()
        
        # 더블 클릭 이벤트 바인딩
        self.image_listbox.bind('<<ListboxSelect>>', self.on_image_select)
        self.image_listbox.bind('<Double-1>', self.on_image_double_click)

        # 화면보호기 중지
        prevent_screen_saver()

        # 화면 활성 상태 유지 스레드 시작
        screen_active_thread = threading.Thread(target=keep_screen_active, daemon=True)
        screen_active_thread.start()

        # 메모리 정리 스레드 시작
        start_memory_cleaner()
        
        # [추가] GUI 설정값 동기화 루프 시작
        self.sync_config_loop()

    def start_hotkey_listener(self):
        """pynput을 이용한 OS 독립적인 글로벌 단축키 리스너 시작"""
        def on_f8():
            self.root.after(10, self.handle_f8_key)
        def on_esc():
            self.root.after(10, self.on_exit)
            
        self.hotkey_listener = pynput_keyboard.GlobalHotKeys({
            '<f8>': on_f8,
            '<esc>': on_esc
        })
        self.hotkey_listener.start()

    # [이동 및 수정] F8 키 핸들러 (이름 변경: f9 -> f8)
    def handle_f8_key(self):
        global capturing_mode, capture_step, profile_switching, monitoring_event
        
        # ✅ [변경] capturing_mode 여부 무관하게 무시 원인 로그 출력
        if profile_switching or monitoring_event.is_set():
            self.status_callback(
                f"[F8 무시] 프로필전환={profile_switching}, 모니터링={monitoring_event.is_set()}, 캡처모드={capturing_mode}"
            )
            return
        
        if not capturing_mode:
            # 캡처 모드 아닐 때는 조용히 무시 (기존 동작 유지)
            return
        
        x, y = pyautogui.position()
        
        if capture_step == 1:
            self.delayed_capture(x, y, "트리거")
        elif capture_step == 2:
            self.delayed_capture(x, y, "타겟")
    
    # [이동] 캡처 지연 함수
    def delayed_capture(self, x, y, capture_type):
        self.status_callback(f"마우스를 옮겨주세요. 2초 후 {capture_type} 캡처가 진행됩니다...")
        
        # 2초 후 캡처 진행
        def perform_capture():
            global trigger_capture_multiplier, target_capture_multiplier, temp_trigger_data, temp_target_data, capture_step, capturing_mode
            
            # 캡처 타입에 따라 적절한 배율 사용
            if capture_type == "트리거":
                multiplier = trigger_capture_multiplier
            else:  # 타겟
                multiplier = target_capture_multiplier
            
            capture_info, screenshot = capture_screen_region(x, y, multiplier=multiplier)
            
            if capture_info and screenshot:
                if capture_type == "트리거":
                    temp_trigger_data = capture_info
                    
                    self.status_callback(f"트리거 이미지 캡처 완료: 위치 ({x}, {y}), 배율 {multiplier}배")
                    self.update_capture_preview(screenshot, "트리거 이미지")
                    capture_step = 2
                elif capture_type == "타겟":
                    temp_target_data = capture_info
                    
                    self.status_callback(f"타겟 이미지 캡처 완료: 위치 ({x}, {y}), 배율 {multiplier}배")
                    self.update_capture_preview(screenshot, "타겟 이미지")
                    
                    # 메인 스레드에서 설명 대화 상자 표시
                    self.root.after(10, lambda: ask_description_in_main_thread(self))
            else:
                self.status_callback(f"{capture_type} 이미지 캡처 실패")
                capturing_mode = False
                capture_step = 0
        
        # 2초 후 실행
        self.root.after(2000, perform_capture)

    # [이동] 모니터링 루프
    def monitoring_loop(self):
        if not image_pairs:
            self.status_callback("등록된 이미지 쌍이 없습니다.")
            return

        self.status_callback("모니터링 스레드 시작 (순차 검사 모드)")

        while monitoring_event.is_set() and not shutdown_event.is_set():
            # (1) 인터벌 값 가져오기 (스레드 안전 변수 사용)
            interval = self.thread_safe_config.get("interval", 5.0)

            for idx, pair in enumerate(image_pairs):
                if not monitoring_event.is_set(): break

                # 첫 번째 항목부터 대기 적용
                self.status_callback(f"#{idx+1} 검사 전 {interval}초 대기...")
                if not safe_sleep(interval, monitoring_event): break

                try:
                    # GUI 정밀도 설정 로드 (스레드 안전 변수 사용)
                    t_conf = self.thread_safe_config.get("trigger_conf", 0.8)
                    tar_conf = self.thread_safe_config.get("target_conf", 0.9)

                    trigger_img = pair.get("_trigger_img")
                    target_img = pair.get("_target_img")

                    if not trigger_img or not target_img:
                        continue

                    # 트리거 탐색
                    trigger_pos = pyautogui.locateCenterOnScreen(trigger_img, confidence=t_conf)

                    if trigger_pos:
                        self.status_callback(f"#{idx+1} 트리거 발견!")
                        
                        # [추가] 트리거 발견 후 타겟 찾기 전 대기 (개별 설정)
                        action_delay = pair.get("action_delay", 0)
                        if action_delay > 0:
                            self.status_callback(f"  -> {action_delay}초 대기 (설정값)...")
                            if not safe_sleep(action_delay, monitoring_event): break
                            
                        target_pos = pyautogui.locateCenterOnScreen(target_img, confidence=tar_conf)

                        if target_pos:
                            pyautogui.click(target_pos)
                            self.status_callback(f"#{idx+1} 타겟 클릭 완료!")
                            pyautogui.moveRel(50, 50, duration=0.2)
                            time.sleep(2) # 클릭 후 최소한의 동작 안정화 대기
                        else:
                            self.status_callback(f"#{idx+1} 트리거는 찾았으나 타겟 미발견")
                    
                except Exception as e:
                    self.status_callback(f"#{idx+1} 검사 중 오류: {e}")

            if not monitoring_event.is_set():
                break

            self.status_callback(f"한 사이클 완료. 다음 사이클을 시작합니다.")

    # [이동] 모니터링 토글
    def toggle_monitoring(self):
        global monitoring_thread, capturing_mode, capture_step

        if not monitoring_event.is_set():
            # 모니터링 시작 시 캡처 모드 강제 해제
            if capturing_mode:
                capturing_mode = False
                capture_step = 0
                self.capture_button.config(text="이미지 쌍 캡처 시작")
                self.hide_capture_preview()
                self.status_callback("캡처 모드가 자동으로 해제되었습니다.")
            
            save_all_profiles()
            monitoring_event.set()
            self.status_callback("모니터링 시작 중...")
            self.start_button.config(text="모니터링 중지")

            if not monitoring_thread or not monitoring_thread.is_alive():
                monitoring_thread = threading.Thread(
                    target=self.monitoring_loop,
                    daemon=True
                )
                monitoring_thread.start()
        else:
            monitoring_event.clear()
            self.status_callback("모니터링이 중지되었습니다.")
            self.start_button.config(text="모니터링 시작")

            # 캡처 상태 초기화
            reset_capture_state(self)

    def reset_settings(self):
        """정밀도 및 간격을 기본값으로 초기화"""
        self.trigger_conf_entry.delete(0, tk.END)
        self.trigger_conf_entry.insert(0, "0.8")
        
        self.target_conf_entry.delete(0, tk.END)
        self.target_conf_entry.insert(0, "0.9")
        
        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, "5.0")
        
        self.status_callback("정밀도 및 간격 설정이 기본값으로 초기화되었습니다.")

    def sync_config_loop(self):
        """GUI 입력값을 주기적으로 스레드 안전 변수에 동기화"""
        try:
            # 인터벌
            try: self.thread_safe_config["interval"] = max(float(self.interval_entry.get()), 5.0)
            except: pass
            
            # 정밀도
            try: self.thread_safe_config["trigger_conf"] = float(self.trigger_conf_entry.get())
            except: pass
            try: self.thread_safe_config["target_conf"] = float(self.target_conf_entry.get())
            except: pass
            
        except Exception:
            pass
        finally:
            # 0.5초마다 반복
            self.root.after(500, self.sync_config_loop)

    def setup_ui(self):
        # ========== 프로필 관리 UI 추가 ==========
        profile_frame = tk.LabelFrame(self.root, text="프로필 관리", padx=10, pady=5)
        profile_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 현재 프로필 표시
        self.current_profile_label = tk.Label(profile_frame, text=f"현재 프로필: {current_profile_name}", 
                                               font=("Arial", 10, "bold"), fg="blue")
        self.current_profile_label.pack(side=tk.TOP, pady=5)
        
        # 프로필 버튼들
        profile_btn_frame = tk.Frame(profile_frame)
        profile_btn_frame.pack(side=tk.TOP, fill=tk.X)
        
        tk.Button(profile_btn_frame, text="새 프로필", command=self.new_profile, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(profile_btn_frame, text="프로필 불러오기", command=self.load_profile_dialog, width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(profile_btn_frame, text="다른 이름으로 저장", command=self.save_as_profile, width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(profile_btn_frame, text="프로필 삭제", command=self.delete_profile_dialog, width=12).pack(side=tk.LEFT, padx=2)
        # [추가] HELP 버튼 - 깔끔한 하늘색 톤
        tk.Button(profile_btn_frame, text="HELP", command=self.show_help, 
                  bg="#e3f2fd", fg="#1976d2", font=("돋움", 9, "bold"), width=8).pack(side=tk.LEFT, padx=10)        
        # 기존 프레임 레이아웃 코드...
        # 프레임 레이아웃
        self.top_frame = tk.Frame(self.root)
        self.top_frame.pack(fill=tk.X, pady=5)
        
        self.middle_frame = tk.Frame(self.root)
        self.middle_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.pack(fill=tk.X, pady=5)
        
        # 지시사항
        instruction = tk.Label(self.top_frame, text="F8 키를 사용하여 트리거 및 타겟 이미지를 캡처한 다음 모니터링을 시작하세요.", justify=tk.LEFT, padx=5)
        instruction.pack(fill=tk.X, pady=2)
        
        # 이미지 목록 프레임
        self.list_frame = tk.LabelFrame(self.middle_frame, text="등록된 이미지 쌍 (순서 조정 가능)")
        self.list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 목록과 화살표 버튼을 가로로 배치하기 위한 내부 컨테이너
        list_inner = tk.Frame(self.list_frame)
        list_inner.pack(fill=tk.BOTH, expand=True)

        # 리스트박스 (좌측)
        self.image_listbox = tk.Listbox(list_inner, font=("Consolas", 10))
        self.image_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        
        # 스크롤바
        list_scrollbar = tk.Scrollbar(list_inner)
        list_scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.image_listbox.config(yscrollcommand=list_scrollbar.set)
        list_scrollbar.config(command=self.image_listbox.yview)

        # 화살표 버튼 프레임 (우측)
        arrow_frame = tk.Frame(list_inner)
        arrow_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)

        tk.Button(arrow_frame, text="▲", width=3, command=self.move_up).pack(expand=True)
        tk.Label(arrow_frame, text="순서", font=("돋움", 8)).pack()
        tk.Button(arrow_frame, text="▼", width=3, command=self.move_down).pack(expand=True)

      
        
        # 로그 프레임
        self.log_frame = tk.LabelFrame(self.middle_frame, text="실행 로그")
        self.log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        global log_text
        log_text = tk.Text(self.log_frame, wrap=tk.WORD, height=10)
        log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        log_scrollbar = tk.Scrollbar(log_text)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        log_text.config(yscrollcommand=log_scrollbar.set)
        log_scrollbar.config(command=log_text.yview)

        # 버튼 프레임
        self.button_frame = tk.Frame(self.bottom_frame)
        self.button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 이미지 캡처 버튼
        self.capture_button = tk.Button(self.button_frame, text="이미지 쌍 캡처 시작", 
                                       command=lambda: toggle_capture_mode(self))
        self.capture_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # 캡처 크기 선택을 위한 새 프레임 추가
        self.capture_size_frame = tk.LabelFrame(self.bottom_frame, text="캡처 크기")
        self.capture_size_frame.pack(fill=tk.X, padx=5, pady=5)

        # --- 인식 정밀도(Confidence) 설정 프레임 추가 ---
        self.conf_frame = tk.LabelFrame(self.bottom_frame, text="인식 정밀도 (0.1 ~ 1.0)")
        self.conf_frame.pack(fill=tk.X, padx=5, pady=5)

        # 트리거 정밀도
        tk.Label(self.conf_frame, text="트리거:").pack(side=tk.LEFT, padx=5)
        self.trigger_conf_entry = tk.Entry(self.conf_frame, width=5)
        self.trigger_conf_entry.pack(side=tk.LEFT, padx=5)

        # 타겟 정밀도
        tk.Label(self.conf_frame, text="타겟:").pack(side=tk.LEFT, padx=5)
        self.target_conf_entry = tk.Entry(self.conf_frame, width=5)
        self.target_conf_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(self.conf_frame, text="(높을수록 정확, 낮을수록 유연, 기본 : 0.8 - 0.9)", font=("돋움", 8), fg="gray").pack(side=tk.LEFT, padx=10)

        # --- 모니터링 인터벌 설정 ---
        tk.Label(self.conf_frame, text="검사 간격(초):").pack(side=tk.LEFT, padx=5)
        self.interval_entry = tk.Entry(self.conf_frame, width=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        # 초기화 버튼 추가
        self.reset_btn = tk.Button(self.conf_frame, text="정밀도 및 간격 초기화", 
                                command=self.reset_settings, bg="#f0f0f0", fg="black", font=("돋움", 8))
        self.reset_btn.pack(side=tk.LEFT, padx=10)
        
        # === 🔴 [추가] 트리거/타겟 캡처 배율 별도 설정 ===
        # 트리거 이미지 캡처 배율
        trigger_size_label = tk.Label(self.capture_size_frame, text="트리거 배율:", font=("돋움", 9, "bold"))
        trigger_size_label.pack(side=tk.LEFT, padx=5)
        
        self.trigger_capture_var = tk.IntVar(value=1)
        
        self.trigger_size_1_radio = tk.Radiobutton(self.capture_size_frame, text="1배", 
                                                   variable=self.trigger_capture_var, value=1,
                                                   command=self.update_trigger_capture_size)
        self.trigger_size_1_radio.pack(side=tk.LEFT)
        
        self.trigger_size_2_radio = tk.Radiobutton(self.capture_size_frame, text="2배", 
                                                   variable=self.trigger_capture_var, value=2,
                                                   command=self.update_trigger_capture_size)
        self.trigger_size_2_radio.pack(side=tk.LEFT)
        
        self.trigger_size_3_radio = tk.Radiobutton(self.capture_size_frame, text="3배", 
                                                   variable=self.trigger_capture_var, value=3,
                                                   command=self.update_trigger_capture_size)
        self.trigger_size_3_radio.pack(side=tk.LEFT)
        
        # 구분선
        tk.Label(self.capture_size_frame, text=" | ").pack(side=tk.LEFT, padx=2)
        
        # 타겟 이미지 캡처 배율
        target_size_label = tk.Label(self.capture_size_frame, text="타겟 배율:", font=("돋움", 9, "bold"))
        target_size_label.pack(side=tk.LEFT, padx=5)
        
        self.target_capture_var = tk.IntVar(value=1)
        
        self.target_size_1_radio = tk.Radiobutton(self.capture_size_frame, text="1배", 
                                                  variable=self.target_capture_var, value=1,
                                                  command=self.update_target_capture_size)
        self.target_size_1_radio.pack(side=tk.LEFT)
        
        self.target_size_2_radio = tk.Radiobutton(self.capture_size_frame, text="2배", 
                                                  variable=self.target_capture_var, value=2,
                                                  command=self.update_target_capture_size)
        self.target_size_2_radio.pack(side=tk.LEFT)
        
        self.target_size_3_radio = tk.Radiobutton(self.capture_size_frame, text="3배", 
                                                  variable=self.target_capture_var, value=3,
                                                  command=self.update_target_capture_size)
        self.target_size_3_radio.pack(side=tk.LEFT)
        
        # 이미지 삭제 버튼
        self.delete_button = tk.Button(self.button_frame, text="선택한 이미지 쌍 삭제", command=self.delete_image_pair)
        self.delete_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # 설명 편집 버튼
        self.edit_description_button = tk.Button(self.button_frame, text="설명 편집", command=self.edit_description)
        self.edit_description_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # 모니터링 시작 버튼
        self.start_button = tk.Button(self.button_frame, text="모니터링 시작", 
                                      command=self.toggle_monitoring)
        self.start_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # 종료 버튼
        self.exit_button = tk.Button(self.button_frame, text="종료", command=self.on_exit)
        self.exit_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

    def update_trigger_capture_size(self):
        """트리거 이미지 캡처 배율 업데이트"""
        global trigger_capture_multiplier
        trigger_capture_multiplier = self.trigger_capture_var.get()
        self.status_callback(f"트리거 이미지 캡처 배율: {trigger_capture_multiplier}배로 설정됨")

    def update_target_capture_size(self):
        """타겟 이미지 캡처 배율 업데이트"""
        global target_capture_multiplier
        target_capture_multiplier = self.target_capture_var.get()
        self.status_callback(f"타겟 이미지 캡처 배율: {target_capture_multiplier}배로 설정됨")

    def update_capture_size_display(self):
        """프로필 로드 시 UI 배율 표시 업데이트"""
        global trigger_capture_multiplier, target_capture_multiplier
        self.trigger_capture_var.set(trigger_capture_multiplier)
        self.target_capture_var.set(target_capture_multiplier)

    def update_capture_size(self):
        """하위호환성용 (구버전용, 현재 미사용)"""
        pass  # 트리거/타겟 개별 배율 사용으로 인해 미사용

    def setup_preview_frame(self):
        # 미리보기 프레임 (메인 GUI에 통합)
        self.preview_frame = tk.LabelFrame(self.root, text="이미지 미리보기")
        self.preview_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 미리보기 영역을 위한 내부 프레임
        self.preview_inner_frame = tk.Frame(self.preview_frame)
        self.preview_inner_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 고정된 크기 설정 (픽셀 단위)
        preview_width = 150
        preview_height = 150
        
        # 트리거 이미지 프레임 - 고정 크기
        self.trigger_frame = tk.LabelFrame(self.preview_inner_frame, text="트리거 이미지")
        self.trigger_frame.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Canvas 사용하여 고정 크기의 프레임 만들기
        self.trigger_canvas = tk.Canvas(self.trigger_frame, width=preview_width, height=preview_height, 
                                      bg='white', highlightthickness=0)
        self.trigger_canvas.pack(padx=5, pady=5)
        
        # 트리거 이미지를 표시할 레이블
        self.trigger_preview = tk.Label(self.trigger_canvas, text="이미지 없음", bg='white')
        self.trigger_canvas.create_window(preview_width//2, preview_height//2, 
                                        window=self.trigger_preview, anchor=tk.CENTER)
        
        # 타겟 이미지 프레임 - 고정 크기
        self.target_frame = tk.LabelFrame(self.preview_inner_frame, text="타겟 이미지")
        self.target_frame.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Canvas 사용하여 고정 크기의 프레임 만들기
        self.target_canvas = tk.Canvas(self.target_frame, width=preview_width, height=preview_height, 
                                     bg='white', highlightthickness=0)
        self.target_canvas.pack(padx=5, pady=5)
        
        # 타겟 이미지를 표시할 레이블
        self.target_preview = tk.Label(self.target_canvas, text="이미지 없음", bg='white')
        self.target_canvas.create_window(preview_width//2, preview_height//2, 
                                       window=self.target_preview, anchor=tk.CENTER)
        
        # 설명 프레임
        self.description_frame = tk.LabelFrame(self.preview_inner_frame, text="설명")
        self.description_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 설명 레이블
        self.description_label = tk.Label(self.description_frame, text="선택된 이미지 쌍 없음", 
                                         wraplength=200, justify=tk.LEFT, height=8)
        self.description_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 미리보기 크기 정보 저장
        self.preview_size = (preview_width, preview_height)


    def update_image_list(self):
        self.image_listbox.delete(0, tk.END)
        for idx, pair in enumerate(image_pairs):
            timestamp = pair.get("timestamp", "시간 정보 없음")
            description = pair.get("description", "설명 없음")
            action_delay = pair.get("action_delay", 0)
            delay_str = f" [대기: {action_delay}s]" if action_delay > 0 else ""
            description_preview = description[:20] + "..." if len(description) > 20 else description
            self.image_listbox.insert(tk.END, f"#{idx+1}: {timestamp} - {description_preview}{delay_str}")

    def delete_image_pair(self):
        global image_pairs, capturing_mode, capture_step
        selected = self.image_listbox.curselection()
        if not selected:
            self.status_callback("삭제할 이미지 쌍을 선택하세요.")
            return
            
        idx = selected[0]
        if 0 <= idx < len(image_pairs):
            # 목록에서 제거
            del image_pairs[idx]
            save_config()
            self.status_callback(f"이미지 쌍 #{idx+1}이(가) 삭제되었습니다.")
            self.update_image_list()
            
            # 미리보기 지우기
            self.clear_preview()
            
            # 🔴 [추가] 캡처 모드 중이면 상태 초기화 (F8 키 정상 작동 보장)
            if capturing_mode or capture_step > 0:
                reset_capture_state(self)

    def edit_description(self):
        selected = self.image_listbox.curselection()
        if not selected:
            self.status_callback("설명을 편집할 이미지 쌍을 선택하세요.")
            return
            
        idx = selected[0]
        if 0 <= idx < len(image_pairs):
            current_desc = image_pairs[idx].get("description", "")
            
            # 메인 스레드에서 대화 상자 표시
            def show_edit_dialog():
                new_desc = simpledialog.askstring("설명 편집", "새 설명 입력:", 
                                               initialvalue=current_desc, parent=self.root)
                
                if new_desc is not None:  # 취소되지 않음
                    image_pairs[idx]["description"] = new_desc
                    save_config()
                    self.status_callback(f"이미지 쌍 #{idx+1}의 설명이 업데이트되었습니다.")
                    self.update_image_list()
                    
                    # 선택한 항목 유지
                    self.image_listbox.selection_set(idx)
                    
                    # 미리보기 업데이트
                    self.on_image_double_click(None)
            
            # 메인 스레드에서 실행
            self.root.after(10, show_edit_dialog)

    def status_callback(self, message):
        # [수정] 스레드 안전성 확보: 메인 스레드에서 GUI 업데이트 실행
        self.root.after(0, self._thread_safe_log, message)

    def _thread_safe_log(self, message):
        """실제 로그를 GUI에 출력하는 내부 함수 (메인 스레드 전용)"""
        global log_text
        if log_text:
            current_time = time.strftime("%H:%M:%S", time.localtime())
            log_text.insert(tk.END, f"[{current_time}] {message}\n")
            log_text.see(tk.END)  # 최신 로그를 표시하기 위해 스크롤
            print(message)  # 콘솔에도 출력

    def show_capture_preview(self):
        # 메인 GUI의 미리보기 영역 사용
        self.clear_preview()
        self.preview_frame.config(text="캡처 미리보기 - 트리거 이미지 위치에서 F8 누르기")

    def hide_capture_preview(self):
        self.preview_frame.config(text="이미지 미리보기")
        self.clear_preview()

    def clear_preview(self):
        # 미리보기 영역 지우기
        if hasattr(self, 'trigger_preview'):
            self.trigger_preview.config(image='', text="이미지 없음")
        if hasattr(self, 'target_preview'):
            self.target_preview.config(image='', text="이미지 없음")
        if hasattr(self, 'description_label'):
            self.description_label.config(text="선택된 이미지 쌍 없음")

    def update_capture_preview(self, pil_image, label_text):
        # 이미지를 고정된 크기에 맞게 조정
        preview_width, preview_height = self.preview_size
        
        # 이미지 비율 유지하면서 프레임에 맞추기
        img_width, img_height = pil_image.size
        
        # 가로세로 비율 계산
        aspect_ratio = img_width / img_height
        
        if aspect_ratio > 1:  # 가로가 더 긴 경우
            new_width = preview_width
            new_height = int(preview_width / aspect_ratio)
        else:  # 세로가 더 긴 경우 또는 정사각형
            new_height = preview_height
            new_width = int(preview_height * aspect_ratio)
        
        # 이미지 크기 조정 (비율 유지)
        pil_image_resized = pil_image.resize((new_width, new_height), Image.LANCZOS)
        
        # Tkinter 호환 형식으로 변환
        tk_image = ImageTk.PhotoImage(pil_image_resized)
        
        if label_text == "트리거 이미지":
            self.trigger_preview.config(image=tk_image, text="")
            self.trigger_preview.image = tk_image  # 참조 유지
            self.preview_frame.config(text="캡처 미리보기 - 타겟 이미지 위치에서 F8 누르기")
        else:
            self.target_preview.config(image=tk_image, text="")
            self.target_preview.image = tk_image  # 참조 유지
            self.preview_frame.config(text="캡처 미리보기 - 설명 입력")

    def on_image_double_click(self, event):
        """더블 클릭 시 지연 시간 설정"""
        selected = self.image_listbox.curselection()
        if not selected:
            return
            
        idx = selected[0]
        if 0 <= idx < len(image_pairs):
            current_delay = image_pairs[idx].get("action_delay", 0)
            
            new_delay = simpledialog.askfloat("동작 간격 설정", 
                                            f"트리거 발견 후 타겟 클릭 전 대기 시간(초)을 입력하세요.\n(현재: {current_delay}초)",
                                            parent=self.root,
                                            minvalue=0.0, maxvalue=300.0, initialvalue=current_delay)
            
            if new_delay is not None:
                image_pairs[idx]["action_delay"] = new_delay
                save_config()
                self.status_callback(f"이미지 쌍 #{idx+1} 대기 시간 설정: {new_delay}초")
                self.update_image_list()
                self.image_listbox.selection_set(idx)

    def on_image_select(self, event):
        selected = self.image_listbox.curselection()
        if not selected:
            return
            
        idx = selected[0]
        if 0 <= idx < len(image_pairs):
            pair = image_pairs[idx]
            
            # 트리거 이미지 데이터와 타겟 이미지 데이터 가져오기
            trigger_data = pair.get("trigger", {}).get("pixel_data")
            target_data = pair.get("target", {}).get("pixel_data")
            
            # 미리보기 크기 가져오기
            preview_width, preview_height = self.preview_size
            
            # 트리거 이미지 표시
            if trigger_data:
                try:
                    trigger_img = pixel_data_to_image(trigger_data)
                    if trigger_img:
                        # 이미지 비율 유지하면서 프레임에 맞추기
                        img_width, img_height = trigger_img.size
                        aspect_ratio = img_width / img_height
                        
                        if aspect_ratio > 1:  # 가로가 더 긴 경우
                            new_width = preview_width
                            new_height = int(preview_width / aspect_ratio)
                        else:  # 세로가 더 긴 경우 또는 정사각형
                            new_height = preview_height
                            new_width = int(preview_height * aspect_ratio)
                        
                        # 이미지 크기 조정 (비율 유지)
                        trigger_img_resized = trigger_img.resize((new_width, new_height), Image.LANCZOS)
                        
                        tk_trigger = ImageTk.PhotoImage(trigger_img_resized)
                        
                        self.trigger_preview.config(image=tk_trigger, text="")
                        self.trigger_preview.image = tk_trigger  # 참조 유지
                except Exception as e:
                    self.status_callback(f"트리거 이미지 변환 오류: {e}")
                    self.trigger_preview.config(image='', text="이미지 변환 오류")
            
            # 타겟 이미지 표시
            if target_data:
                try:
                    target_img = pixel_data_to_image(target_data)
                    if target_img:
                        # 이미지 비율 유지하면서 프레임에 맞추기
                        img_width, img_height = target_img.size
                        aspect_ratio = img_width / img_height
                        
                        if aspect_ratio > 1:  # 가로가 더 긴 경우
                            new_width = preview_width
                            new_height = int(preview_width / aspect_ratio)
                        else:  # 세로가 더 긴 경우 또는 정사각형
                            new_height = preview_height
                            new_width = int(preview_height * aspect_ratio)
                        
                        # 이미지 크기 조정 (비율 유지)
                        target_img_resized = target_img.resize((new_width, new_height), Image.LANCZOS)
                        
                        tk_target = ImageTk.PhotoImage(target_img_resized)
                        
                        self.target_preview.config(image=tk_target, text="")
                        self.target_preview.image = tk_target  # 참조 유지
                except Exception as e:
                    self.status_callback(f"타겟 이미지 변환 오류: {e}")
                    self.target_preview.config(image='', text="이미지 변환 오류")
            
            # 설명 업데이트
            description = pair.get("description", "설명 없음")
            self.description_label.config(text=description)
    
    # ========== 프로필 관리 메서드 ==========
    def new_profile(self):
        """새 프로필 생성"""
        global profile_switching
        
        # 프로필 전환 시작
        profile_switching = True
        
        try:
            # 모니터링 중이면 자동 중지
            if monitoring_event.is_set():
                monitoring_event.clear()
                self.status_callback("프로필 전환으로 인해 모니터링이 중지되었습니다.")
                time.sleep(0.5)  # 스레드 종료 대기

            from tkinter import messagebox
            profile_name = simpledialog.askstring("새 프로필", "새 프로필 이름을 입력하세요:", parent=self.root)
            
            if not profile_name or profile_name.strip() == "":
                return
            
            profile_name = profile_name.strip()

            # 먼저 프로필 생성 가능 여부 확인
            if profile_name in all_profiles:
                messagebox.showerror("오류", f"프로필 '{profile_name}'이(가) 이미 존재합니다.")
                return
            
            # 생성 가능하면 현재 작업 저장
            save_current_to_profile()
            
            if create_new_profile(profile_name):
                load_profile(profile_name)
                reset_capture_state(self)
                save_all_profiles()
                self.status_callback(f"새 프로필 '{profile_name}' 생성됨")
                self.current_profile_label.config(text=f"현재 프로필: {profile_name}")
                self.update_image_list()
        finally:
            # 프로필 전환 완료
            profile_switching = False
    
    def load_profile_dialog(self):
        """프로필 선택 대화상자"""
        global profile_switching
        
        # 프로필 전환 시작
        profile_switching = True
        
        try:
            # 모니터링 중이면 자동 중지
            if monitoring_event.is_set():
                monitoring_event.clear()
                self.status_callback("프로필 전환으로 인해 모니터링이 중지되었습니다.")
                time.sleep(0.5)  # 스레드 종료 대기
        
            from tkinter import messagebox
            profiles = get_profile_names()
            
            if not profiles:
                messagebox.showinfo("알림", "저장된 프로필이 없습니다.")
                return
            
            # 선택 대화상자
            dialog = tk.Toplevel(self.root)
            dialog.title("프로필 불러오기")
            dialog.geometry("300x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # 메인 GUI 중앙에 위치
            dialog.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            
            tk.Label(dialog, text="불러올 프로필을 선택하세요:", font=("Arial", 10)).pack(pady=10)
            
            # 리스트박스와 스크롤바를 담을 프레임
            list_frame = tk.Frame(dialog)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            scrollbar = tk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            for p in profiles:
                listbox.insert(tk.END, p)
            
            def on_select():
                global profile_switching
                selected = listbox.curselection()
                if selected:
                    try:
                        profile_name = listbox.get(selected[0])
                        
                        # 프로필 전환 전에 현재 작업 저장
                        save_current_to_profile()
                        
                        if load_profile(profile_name):
                            reset_capture_state(self)
                            save_all_profiles()
                            self.status_callback(f"프로필 '{profile_name}' 로드됨")
                            self.current_profile_label.config(text=f"현재 프로필: {profile_name}")
                            self.update_image_list()
                            self.clear_preview()
                            dialog.destroy()
                    finally:
                        profile_switching = False
            
            tk.Button(dialog, text="선택", command=on_select, width=10).pack(pady=5)
            def on_cancel():
                global profile_switching
                profile_switching = False
                dialog.destroy()
            tk.Button(dialog, text="취소", command=on_cancel, width=10).pack(pady=5)
            dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        except Exception as e:
            profile_switching = False
            self.status_callback(f"프로필 로드 중 오류: {e}")
    
    def save_as_profile(self):
        """다른 이름으로 저장"""
        from tkinter import messagebox
        profile_name = simpledialog.askstring("다른 이름으로 저장", "저장할 프로필 이름을 입력하세요:", parent=self.root)
        
        if not profile_name or profile_name.strip() == "":
            return
        
        profile_name = profile_name.strip()
        
        # 기존 프로필이면 덮어쓰기 확인
        if profile_name in all_profiles:
            if not messagebox.askyesno("확인", f"프로필 '{profile_name}'이(가) 이미 존재합니다. 덮어쓰시겠습니까?"):
                return
        
        # 현재 데이터 저장
        save_current_to_profile()
        
        # 새 이름으로 복사
        global current_profile_name
        all_profiles[profile_name] = copy.deepcopy(all_profiles[current_profile_name])
        current_profile_name = profile_name
        reset_capture_state(self)
        save_all_profiles()
        self.status_callback(f"프로필 '{profile_name}'(으)로 저장됨")
        self.current_profile_label.config(text=f"현재 프로필: {profile_name}")
    
    def delete_profile_dialog(self):
        """프로필 삭제"""
        from tkinter import messagebox
        profiles = [p for p in get_profile_names() if p != "default"]
        
        if not profiles:
            messagebox.showinfo("알림", "삭제할 수 있는 프로필이 없습니다. (default는 삭제 불가)")
            return
        
        # 선택 대화상자
        dialog = tk.Toplevel(self.root)
        dialog.title("프로필 삭제")
        dialog.geometry("300x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 메인 GUI 중앙에 위치
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="삭제할 프로필을 선택하세요:", font=("Arial", 10), fg="red").pack(pady=10)
        
        # 리스트박스와 스크롤바를 담을 프레임
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        for p in profiles:
            listbox.insert(tk.END, p)
        
        def on_delete():
            selected = listbox.curselection()
            if selected:
                profile_name = listbox.get(selected[0])
                if messagebox.askyesno("확인", f"프로필 '{profile_name}'을(를) 정말 삭제하시겠습니까?"):
                    if delete_profile(profile_name):
                        save_all_profiles()
                        self.status_callback(f"프로필 '{profile_name}' 삭제됨")
                        self.current_profile_label.config(text=f"현재 프로필: {current_profile_name}")
                        self.update_image_list()
                        self.clear_preview()
                        dialog.destroy()
        
        tk.Button(dialog, text="삭제", command=on_delete, bg="red", fg="white", width=10).pack(pady=5)
        tk.Button(dialog, text="취소", command=dialog.destroy, width=10).pack(pady=5)
        
    def on_exit(self):
        global running

        shutdown_event.set()
        monitoring_event.clear()
        
        running = False
        # 종료 시 화면보호기 복구
        restore_screen_saver() 
        # 종료 전 설정 저장
        save_config()
        
        # 키보드 리스너 종료
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        
        # 메인 윈도우 종료
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

# 메인 응용 프로그램 실행
def main():
    global app
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()