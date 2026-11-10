"""Basara 4 PC Launcher - by Timotius.



Next-Gen Sengoku Basara 4 Sumeragi (PS4, CUSA01159) Native PC Launcher.

Powered by Ponytail Wrapper Runtime & REA Engine.

Modernized Glassmorphism UI/UX with Flipped Dual-Column Layout.

"""

import ctypes

from ctypes import wintypes

import hashlib

import importlib.util

import json
import math

import os

import platform

import queue

import re

import runpy

import shutil

import ssl

import subprocess

import sys

import threading

import time

import traceback

import urllib.request

import webbrowser

import zipfile

from pathlib import Path



FROZEN = getattr(sys, "frozen", False)

ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent

try:

    os.chdir(str(ROOT))

except OSError:

    pass



BIN, OUT, USER, SCRIPTS = ROOT / "bin", ROOT / "out", ROOT / "user", ROOT / "scripts"

MODS = ROOT / "mods"

CONFIG = USER / "launcher.json"

INI = USER / "basara4.ini"

OLD_INI = USER / "spartanport.ini"

WINDOW_ICON = USER / "window_icon.bmp"

CORE = BIN / "basara4-core.exe"

VERSION = "1.0.0"

BRAND = "Basara 4 PC"

AUTHOR = "Timotius"

GITHUB_REPO = "timotius/basara4-native-pc"

CRIMSON_HEADER = "#D32F2F"        # Official Basara 4 Crimson Red accent



FATAL_PATTERNS = [

    r"(STOP: .*)",

    r"(Fault: .*)",

    r"(ASSERT_MSG.*)",

    r"(vk::Result=.*)",

    r"(VK_ERROR_\w+)",

    r"(GPU \[Render\.Vulkan\] <Error> .*)",

    r"(GPU \[Render\.Vulkan\] <Warning> .*)",

    r"(GPU \[Lib\.\w+\] <Error> .*)",

    r"(Runtime: open\(.*?\) -> not found)",

    r"(guest raised debug exception .*)",

    r"(cannot create \d+ MiB of guest memory .*)",

    r"(error 1455.*)",

    r"(ERROR_COMMITMENT_LIMIT.*)",

    r"(no rewrite table matches the image.*)",

    r"(missing MOVBE, BMI1, LZCNT.*)",

]





def extract_crash_summary(log_path, max_context_lines=10):

    """Parses log from bottom-up and extracts fatal signatures and tail context."""

    if not log_path.is_file():

        return {"detected_errors": ["File log tidak ditemukan (game belum sempat menulis log)."], "tail_context": ""}

    try:

        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()

    except Exception as e:

        return {"detected_errors": [f"Gagal membaca log: {e}"], "tail_context": ""}

    if not lines:

        return {"detected_errors": ["Log kosong (game berhenti sebelum inisialisasi)."], "tail_context": ""}



    tail_lines = lines[-max_context_lines:]

    detected = []

    for line in reversed(lines):

        for pat in FATAL_PATTERNS:

            m = re.search(pat, line)

            if m:

                matched_str = m.group(1).strip()

                if matched_str not in detected:

                    detected.append(matched_str)

        if len(detected) >= 4:

            break

    return {

        "detected_errors": detected if detected else ["Tidak ada fatal signature terdaftar (game keluar mendadak)."],

        "tail_context": "\n".join(tail_lines),

        "total_lines": len(lines)

    }





def parse_version(tag):

    nums = re.findall(r"\d+", str(tag))

    return tuple(int(n) for n in nums) if nums else (0,)





def check_latest_release(repo=GITHUB_REPO):

    """Checks the latest GitHub release. Returns dict of asset info or None."""

    try:

        url = f"https://api.github.com/repos/{repo}/releases/latest"

        req = urllib.request.Request(url, headers={"User-Agent": "Basara4-PC-Launcher"})

        ctx = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:

            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "")

        if parse_version(tag) > parse_version(VERSION):

            for a in data.get("assets", []):

                name = a.get("name", "")

                if name.endswith(".zip") and ("basara4" in name.lower() or "windows" in name.lower()):

                    return {

                        "tag": tag,

                        "url": a.get("browser_download_url"),

                        "name": name,

                        "size": a.get("size", 0),

                        "body": data.get("body", ""),

                    }

            for a in data.get("assets", []):

                if a.get("name", "").endswith(".zip"):

                    return {

                        "tag": tag,

                        "url": a.get("browser_download_url"),

                        "name": a.get("name", ""),

                        "size": a.get("size", 0),

                        "body": data.get("body", ""),

                    }

    except Exception:

        pass

    return None





LOG = USER / "last_run.log"

PREPARE_LOG = USER / "prepare.log"

MAPPING = USER / "gamepad_mapping.txt"

DEFAULT_XINPUT_MAPPING = (

    "0300fa675e0400008e02000010017801,Xbox 360 Controller,a:b0,b:b1,x:b2,y:b3,leftshoulder:b4,"

    "rightshoulder:b5,lefttrigger:a2,righttrigger:a5,back:b6,start:b7,leftstick:b8,rightstick:b9,"

    "guide:b10,dpup:h0.1,dpdown:h0.4,dpleft:h0.8,dpright:h0.2,leftx:a0,lefty:a1,rightx:a3~,righty:a4,platform:Windows,\n"

    "xinput,XInput Controller,a:b0,b:b1,x:b2,y:b3,leftshoulder:b4,rightshoulder:b5,lefttrigger:a2,"

    "righttrigger:a5,back:b6,start:b7,leftstick:b8,rightstick:b9,guide:b10,dpup:h0.1,dpdown:h0.4,"

    "dpleft:h0.8,dpright:h0.2,leftx:a0,lefty:a1,rightx:a3,righty:a4,platform:Windows,\n"

)

AUDIO_LOG = USER / "audio_debug.log"

DEBUG_LOG = USER / "debug_launch.log"

LAUNCH_DEBUG_LOG = USER / "launch_debug.log"

AUDIO_WAV = USER / "audio_wav"

STAMP = OUT / "prepared.json"

LOCALES_PATH = ROOT / "launcher" / "locales.json"

DLC_DIR = ROOT / "DLC"
DLC_DIR.mkdir(parents=True, exist_ok=True)
USER_DLC_DIR = USER / "dlc"
USER_DLC_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DLC_DIR = DLC_DIR
if (DLC_DIR / "DLC" / "CUSA01159").is_dir():
    DEFAULT_DLC_DIR = DLC_DIR / "DLC" / "CUSA01159"
else:
    try:
        if not any(DEFAULT_DLC_DIR.iterdir()) and any(USER_DLC_DIR.iterdir()):
            DEFAULT_DLC_DIR = USER_DLC_DIR
    except (OSError, StopIteration):
        pass



WAV_WARNING = (

    "WAV capture saves the final mix and every long voice as uncompressed audio in user\\audio_wav: "

    "about 70 MB per minute, up to 3 GB for one session.\n\n"

    "Use it only to find an audio problem, and delete the files afterwards.\n\n"

    "It applies to the next game start only and switches itself off after that. "

    "It also turns on the audio debug log. Turn it on?"

)



PIPELINE = [

    ("prepare.py", []),

    ("link_libc.py", []),

    ("link_modules.py", []),

    ("content_profile.py", ["--sku", "full"]),

    ("isa_rewrite.py", [])

]

NO_WINDOW = 0x08000000





def wav_captures():

    """The audio captures an earlier session left in user\audio_wav: (files, total bytes)."""

    files = sorted(AUDIO_WAV.glob("*.wav")) if AUDIO_WAV.is_dir() else []

    total = 0

    for f in files:

        try:

            total += f.stat().st_size

        except OSError:

            pass

    return files, total





def format_size(n):

    return f"{n / 2**30:.1f} GB" if n >= 2**30 else f"{n / 2**20:.0f} MB"





def quote_arg(arg):

    s = str(arg)

    if " " in s and not (s.startswith('"') and s.endswith('"')):

        return f'"{s}"'

    return s





def log_debug(msg):

    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{ts}] {msg}"

    print(line, file=sys.stderr, flush=True)

    try:

        USER.mkdir(parents=True, exist_ok=True)

        with open(DEBUG_LOG, "a", encoding="utf-8") as f:

            f.write(line + "\n")

    except Exception:

        pass





def log_launch(msg):

    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{ts}] [BOOT] {msg}"

    print(line, file=sys.stderr, flush=True)

    try:

        USER.mkdir(parents=True, exist_ok=True)

        with open(LAUNCH_DEBUG_LOG, "a", encoding="utf-8") as f:

            f.write(line + "\n")

        with open(DEBUG_LOG, "a", encoding="utf-8") as f:

            f.write(line + "\n")

    except Exception:

        pass





def get_resource_path(name):

    """Find a resource file prioritizing on-disk updates in ROOT/launcher and ROOT over stale _MEIPASS cache."""

    for folder in [ROOT / "launcher", ROOT, Path(__file__).resolve().parent]:

        p = folder / name

        if p.is_file():

            return p

    if hasattr(sys, "_MEIPASS"):

        p = Path(sys._MEIPASS) / name

        if p.is_file():

            return p

    return ROOT / "launcher" / name





def check_commit_limit_mb():

    """Returns available virtual memory (page file commit limit) in MB, or None if unavailable."""

    try:

        class MEMORYSTATUSEX(ctypes.Structure):

            _fields_ = [

                ("dwLength", wintypes.DWORD),

                ("dwMemoryLoad", wintypes.DWORD),

                ("ullTotalPhys", ctypes.c_uint64),

                ("ullAvailPhys", ctypes.c_uint64),

                ("ullTotalPageFile", ctypes.c_uint64),

                ("ullAvailPageFile", ctypes.c_uint64),

                ("ullTotalVirtual", ctypes.c_uint64),

                ("ullAvailVirtual", ctypes.c_uint64),

                ("ullAvailExtendedVirtual", ctypes.c_uint64),

            ]

        stat = MEMORYSTATUSEX()

        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)

        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):

            return stat.ullAvailPageFile // (1024 * 1024)

    except Exception:

        pass

    return None





def run_script_mode():

    """`launcher.exe --run-script NAME args...`: runs one of the preparation scripts in this process."""

    script = SCRIPTS / sys.argv[2]

    sys.path.insert(0, str(SCRIPTS))

    sys.argv = [str(script)] + sys.argv[3:]

    try:

        runpy.run_path(str(script), run_name="__main__")

    except SystemExit as exit_:

        code = exit_.code

        sys.exit(code if isinstance(code, int) else (0 if code is None else 1))





if len(sys.argv) > 2 and sys.argv[1] == "--run-script":

    run_script_mode()

    sys.exit(0)



import tkinter as tk  # noqa: E402

from tkinter import filedialog, messagebox, ttk  # noqa: E402



try:

    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk, ImageFont, ImageChops
    log_debug("Pillow (PIL) successfully imported")
except ImportError as e:
    Image = ImageDraw = ImageFont = None

    log_debug(f"Pillow (PIL) not available: {e}")



launcher_dir = ROOT / "launcher"

for p in (str(Path(__file__).resolve().parent), str(launcher_dir)):

    if p not in sys.path:

        sys.path.insert(0, p)



try:

    import basara4_patches  # noqa: E402

    log_debug("basara4_patches successfully imported")

except ImportError as e:

    basara4_patches = None

    log_debug(f"basara4_patches import failed: {e}")



try:

    import basara4_cheats  # noqa: E402

    log_debug("basara4_cheats successfully imported")

except ImportError as e:

    basara4_cheats = None

    log_debug(f"basara4_cheats import failed: {e}")



try:

    import basara4_dlc  # noqa: E402

    from basara4_dlc import scan_extracted_dlc  # noqa: E402

    log_debug("basara4_dlc successfully imported")

except ImportError as e:

    basara4_dlc = None

    scan_extracted_dlc = None

    log_debug(f"basara4_dlc import failed: {e}")



DEFAULT_PC_KEYMAP = {

    "square": "Mouse Left",       # Normal Attack (Serangan Biasa)

    "circle": "Mouse Right",      # Heavy / Special Attack / Basara Skill

    "triangle": "Q",              # Secondary Skill

    "cross": "Space",             # Jump / Lompat

    "l1": "Left Shift",           # Guard / Tangkis / Evade

    "r1": "E",                    # Special Skill 2

    "r2": "F",                    # Basara Attack (Ultimate Finisher)

    "l2": "R",                    # Sengoku Drive / Poise Boost (Rage/Burst)

    "touchpad": "Tab",            # Taunt / Provoke

    "options": "Escape",          # Pause / Menu

    "up": "Up",                   # D-Pad Up

    "down": "Down",               # D-Pad Down

    "left": "Left",               # D-Pad Left

    "right": "Right",             # D-Pad Right

    "l3": "Z",                    # L3

    "r3": "C",                    # R3 (Lock-On)

}



ACTION_DESCRIPTIONS = [

    ("square", "Normal Attack (Serangan Biasa)", "Kotak / Square"),

    ("triangle", "Special Skill 1 (Skill Utama)", "Segitiga / Triangle"),

    ("cross", "Jump (Lompat)", "Silang / Cross"),

    ("circle", "Basara Attack (Ultimate)", "Lingkaran / Circle"),

    ("l1", "Guard / Tangkis / Dash", "L1"),

    ("r1", "Special Skill 2 (Skill Tambahan)", "R1"),

    ("r2", "Special Skill 3 (Skill Karakter)", "R2"),

    ("l2", "Sengoku Drive / Boost", "L2"),

    ("touchpad", "Taunt / Provoke", "Touchpad / Tab"),

    ("options", "Pause / In-Game Menu", "Options / Enter"),

    ("up", "D-Pad Up (Navigasi / Perintah)", "D-Pad Atas"),

    ("down", "D-Pad Down (Navigasi / Perintah)", "D-Pad Bawah"),

    ("left", "D-Pad Left (Navigasi / Perintah)", "D-Pad Kiri"),

    ("right", "D-Pad Right (Navigasi / Perintah)", "D-Pad Kanan"),

    ("l3", "L3 Action", "L3"),

    ("r3", "R3 Action / Lock-on", "R3"),

]





def enumerate_gpus():

    """Enumerate system Vulkan GPUs using vulkan-1.dll. Returns list of (index, display_name, is_discrete)."""

    gpus = [(-1, "Auto (Prioritaskan GPU Diskrit)", True)]

    try:

        vulkan = ctypes.cdll.LoadLibrary("vulkan-1.dll")

        class VkApplicationInfo(ctypes.Structure):

            _fields_ = [

                ("sType", ctypes.c_uint32), ("pNext", ctypes.c_void_p),

                ("pApplicationName", ctypes.c_char_p), ("applicationVersion", ctypes.c_uint32),

                ("pEngineName", ctypes.c_char_p), ("engineVersion", ctypes.c_uint32),

                ("apiVersion", ctypes.c_uint32),

            ]

        class VkInstanceCreateInfo(ctypes.Structure):

            _fields_ = [

                ("sType", ctypes.c_uint32), ("pNext", ctypes.c_void_p),

                ("flags", ctypes.c_uint32), ("pApplicationInfo", ctypes.POINTER(VkApplicationInfo)),

                ("enabledLayerCount", ctypes.c_uint32), ("ppEnabledLayerNames", ctypes.c_void_p),

                ("enabledExtensionCount", ctypes.c_uint32), ("ppEnabledExtensionNames", ctypes.c_void_p),

            ]

        class VkPhysicalDeviceProperties(ctypes.Structure):

            _fields_ = [

                ("apiVersion", ctypes.c_uint32), ("driverVersion", ctypes.c_uint32),

                ("vendorID", ctypes.c_uint32), ("deviceID", ctypes.c_uint32),

                ("deviceType", ctypes.c_uint32), ("deviceName", ctypes.c_char * 256),

                ("pipelineCacheUUID", ctypes.c_ubyte * 16), ("limits", ctypes.c_byte * 504),

                ("sparseProperties", ctypes.c_byte * 20),

            ]

        app_info = VkApplicationInfo(sType=1, pApplicationName=b"Basara4Launcher", apiVersion=(1 << 22) | (2 << 12))

        ci = VkInstanceCreateInfo(sType=2, pApplicationInfo=ctypes.pointer(app_info))

        vulkan.vkCreateInstance.argtypes = [ctypes.POINTER(VkInstanceCreateInfo), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

        vulkan.vkCreateInstance.restype = ctypes.c_int32

        vulkan.vkDestroyInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        vulkan.vkEnumeratePhysicalDevices.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p)]

        vulkan.vkEnumeratePhysicalDevices.restype = ctypes.c_int32

        vulkan.vkGetPhysicalDeviceProperties.argtypes = [ctypes.c_void_p, ctypes.POINTER(VkPhysicalDeviceProperties)]



        inst = ctypes.c_void_p()

        if vulkan.vkCreateInstance(ctypes.byref(ci), None, ctypes.byref(inst)) == 0:

            count = ctypes.c_uint32(0)

            vulkan.vkEnumeratePhysicalDevices(inst, ctypes.byref(count), None)

            if count.value > 0:

                devs = (ctypes.c_void_p * count.value)()

                vulkan.vkEnumeratePhysicalDevices(inst, ctypes.byref(count), devs)

                for i in range(count.value):

                    p = VkPhysicalDeviceProperties()

                    vulkan.vkGetPhysicalDeviceProperties(devs[i], ctypes.byref(p))

                    name = p.deviceName.decode("utf-8", errors="replace").strip("\x00")

                    is_disc = (p.deviceType == 2)

                    kind_tag = "dGPU" if is_disc else ("iGPU" if p.deviceType == 1 else "GPU")

                    gpus.append((i, f"GPU {i}: {name} ({kind_tag})", is_disc))

            vulkan.vkDestroyInstance(inst, None)

    except Exception as e:

        log_debug(f"Vulkan GPU enumeration error: {e}")

    return gpus





SYSTEM_GPUS = enumerate_gpus()

DISPLAY_MODES = [("Windowed", "windowed"), ("Borderless fullscreen", "borderless"),

                 ("Exclusive fullscreen", "fullscreen")]

FPS_LIMITS = [("60 (game default)", 60), ("90", 90), ("120", 120), ("144", 144), ("165", 165),

              ("240", 240), ("Unlimited", 0)]

RESOLUTIONS = [

    ("1920 x 1080  (1080p Native)", "native"),

    ("1600 x 900  (900p)", "900p"),

    ("1280 x 720  (720p HD)", "720p"),

    ("960 x 540  (540p qHD - Spek Kentang)", "540p"),

    ("854 x 480  (480p SD - Super Kentang)", "480p"),

    ("640 x 360  (360p nHD - Ultra Kentang)", "360p"),

    ("2560 x 1440  (1440p 2K)", "1440p"),

    ("3200 x 1800  (1800p)", "1800p"),

    ("3840 x 2160  (4K UHD)", "4K"),

]

UPSCALERS = [("Off  (plain scaling)", "off"), ("FSR 1  (sharper)", "fsr1")]

ANISO = [("Off", 0), ("2x", 2), ("4x", 4), ("8x", 8), ("16x", 16)]



# Sengoku Basara Glassmorphism Luxury Dark Samurai Palette with Official Crimson Red & Glowing Blue Metallic
ROOT_BG = "#080F24"             # Deep Midnight Navy
CARD_BG = "#080F24"             # Translucent Dark Midnight Navy Glass
CARD_BORDER = "#1E88E5"         # Sleek Electric Neon Blue border (#1E88E5 / #3898FF)
CARD_BORDER_GLOW = "#1269D8"
CARD_BORDER_SUBTLE = "#0D3A73"
CYAN_HIGHLIGHT = "#58B8FF"      # Cyan highlights matching Masamune's aura
SAMURAI_GOLD = "#D6A63A"        # Subtle Samurai Gold accents
RED_PRIMARY = "#FF4242"         # Official Basara 4 Crimson Red (from logo '4')
RED_DARK = "#780B10"
RED_HOVER = "#FF5E5E"
RED_PRESSED = "#C81D25"
CRIMSON_HEADER = "#FF4242"        # Official Basara 4 Crimson Red accent
FG = "#F1F5F9"
MUTED = "#8A9BB0"
HEADER_BG = "#050917"
INNER_CARD_BG = "#060B1A"
INNER_CARD_BORDER = "#10325C"
STATUS_GREEN = "#22C55E"
STATUS_YELLOW = "#D32F2F"



DEFAULTS = {

    "game": "",

    "dlc_dir": str(DEFAULT_DLC_DIR),

    "display_mode": "borderless",

    "vsync": True,

    "fps_limit": 60,

    "rcas": False,

    "anisotropy": 0,

    "resolution": "native",

    "upscale": "off",

    "audio_log": False,

    "audio_wav": False,

    "gpu_index": -1,

    "keymap": {},

    "mouse_camera": True,

    "mouse_sens": 100,

    "cheats": [],

    "input_mode": "controller",

    "language": "id",

}





DEFAULT_LOCALES = {

    "en": {

        "app_title": "Sengoku Basara 4 Sumeragi",

        "app_subtitle": "戦国BASARA4 皇",

        "ready": "Ready to play",

        "starting": "Starting…",

        "running": "Running… (Insert opens in-game menu)",

        "running_audio": "Running, writing user\\audio_debug.log…",

        "closed": "Game closed.",

        "exited_with_code": "Game exited with code {code}. Check log.",

        "game_ready": "Game image ready.",

        "no_eboot": "No eboot.bin found in this folder.",

        "prep_notice": "Image will be created on first launch (~1 min).",

        "play_btn": "PLAY GAME",

        "stop_btn": "Stop Game",

        "credits_btn": "Credits & Community",

        "by_author": "by Timotius",

        "section_game": "GAME LOCATION",

        "game_folder": "Game Folder",

        "browse_btn": "Browse…",

        "section_display": "DISPLAY & GRAPHICS",

        "mode_windowed": "Windowed",

        "mode_borderless": "Borderless Fullscreen",

        "mode_fullscreen": "Exclusive Fullscreen",

        "gpu_select": "Graphics Card (GPU)",

        "window_size": "Window Size",

        "upscaling": "Upscaling (FSR)",

        "frame_limit": "Frame Limit",

        "anisotropic": "Anisotropic",

        "vsync": "VSync",

        "rcas": "Sharpening (RCAS)",

        "audio_log": "Audio Debug Log",

        "wav_capture": "+ WAV Debug Capture",

        "res_hint": "Game renders internally at 1080p. Window size scales the viewport; FSR 1 enhances clarity on higher resolutions.",

        "fps_hint": "FPS limits above 60 disable internal frame limiter. VSync caps rate at monitor refresh.",

        "ingame_menu": "In-game menu: Insert key, or R3 + L2 on gamepad.",

        "section_controller": "CONTROLLER & INPUT",

        "section_controller_config": "CONTROL CONFIGURATION",

        "section_utilities": "GAME UTILITIES",

        "input_mode": "Input Mode:",

        "input_mode_controller": "Primary Gamepad (P1 & P2)",

        "input_mode_kbm": "Keyboard & Mouse Co-Op",

        "kbm_controls_btn": "KBM Controls",

        "control_gamepad_btn": "Control Gamepad",

        "analog_sens_btn": "Analog Mode",

        "reset_map": "Reset Mapping",

        "cheats_btn": "Cheats & Mods",

        "open_log": "Open Log",

        "open_audio_log": "Audio Log",

        "open_saves": "Open Saves",

        "dlc_btn": "Manage DLC",

        "pad_custom": "Custom gamepad mapping is active.",

        "pad_default": "Standard mapping active (XInput and known gamepads work natively).",

        "pad_prompt": "Follow the prompts in the mapper window, then press PLAY.",

        "confirm_reset_map": "Delete saved controller mapping and restore defaults?",

        "reset_map_success": "Default XInput gamepad mapping restored successfully.",

        "confirm_close": "The game is currently running. Stop game and close launcher?"

    },

    "id": {

        "app_title": "Sengoku Basara 4 Sumeragi",

        "app_subtitle": "戦国BASARA4 皇",

        "ready": "Siap dimainkan",

        "starting": "Menyiapkan…",

        "running": "Berjalan… (Tekan Insert untuk menu in-game)",

        "running_audio": "Berjalan, menulis user\\audio_debug.log…",

        "closed": "Game ditutup.",

        "exited_with_code": "Game keluar dengan kode {code}. Periksa log.",

        "game_ready": "Image game siap.",

        "no_eboot": "eboot.bin tidak ditemukan di folder ini.",

        "prep_notice": "Image game dibuat pada start pertama (~1 menit).",

        "play_btn": "MAINKAN GAME",

        "stop_btn": "Hentikan Game",

        "credits_btn": "Kredit & Lisensi",

        "by_author": "oleh Timotius",

        "section_game": "LOKASI GAME",

        "game_folder": "Direktori Game",

        "browse_btn": "Pilih Folder…",

        "section_display": "TAMPILAN & GRAFIS",

        "mode_windowed": "Jendela (Windowed)",

        "mode_borderless": "Layar Penuh (Borderless)",

        "mode_fullscreen": "Layar Penuh Eksklusif",

        "gpu_select": "Kartu Grafis (GPU)",

        "window_size": "Ukuran Resolusi",

        "upscaling": "Upscaling (FSR)",

        "frame_limit": "Batas FPS",

        "anisotropic": "Anisotropik",

        "vsync": "VSync",

        "rcas": "Ketajaman (RCAS)",

        "audio_log": "Log Debug Audio",

        "wav_capture": "+ Rekam Debug WAV",

        "res_hint": "Game dirender internal pada 1080p. Resolusi jendela mengatur ukuran tampilan; FSR 1 mempertajam pada layar resolusi tinggi.",

        "fps_hint": "Batas FPS di atas 60 menonaktifkan limiter bawaan game. Matikan VSync agar tidak dibatasi layar.",

        "ingame_menu": "Menu in-game: Tombol Insert, atau R3 + L2 pada stik.",

        "section_controller": "KONTROLER & INPUT",

        "section_controller_config": "PENGATURAN KONTROL",

        "section_utilities": "UTILITAS & MODS",

        "input_mode": "Mode Input:",

        "input_mode_controller": "Stik / Gamepad Utama (P1 & P2)",

        "input_mode_kbm": "Keyboard & Mouse Co-Op",

        "kbm_controls_btn": "Pengaturan KBM",

        "control_gamepad_btn": "Atur Gamepad",

        "analog_sens_btn": "Mode Analog",

        "reset_map": "Reset Pemetaan",

        "cheats_btn": "Mod & Cheat",

        "open_log": "Buka Log",

        "open_audio_log": "Log Audio",

        "open_saves": "Data Save",

        "dlc_btn": "Kelola DLC",

        "pad_custom": "Mapping stik kustom sedang digunakan.",

        "pad_default": "Mapping standar aktif (XInput dan controller umum langsung terdeteksi).",

        "pad_prompt": "Ikuti petunjuk di jendela mapper, lalu tekan MAINKAN.",

        "confirm_reset_map": "Hapus pengaturan mapping stik dan kembalikan ke default?",

        "reset_map_success": "Mapping stik bawaan XInput berhasil dipulihkan.",

        "confirm_close": "Game sedang berjalan. Hentikan game dan tutup launcher?"

    }

}





def load_locales():

    """Load localization dictionary with built-in fallbacks and disk overrides."""

    import copy

    loc = copy.deepcopy(DEFAULT_LOCALES)

    path = get_resource_path("locales.json")

    if path and path.is_file():

        try:

            disk_loc = json.loads(path.read_text(encoding="utf-8"))

            for lang, vals in disk_loc.items():

                if lang not in loc:

                    loc[lang] = {}

                loc[lang].update(vals)

            log_debug(f"Loaded locales from {path}")

        except Exception as e:

            log_debug(f"Failed to parse locales.json: {e}")

    return loc





def find_game():

    r"""The first folder under game\ that holds an eboot.bin."""

    base = ROOT / "game"

    if (base / "eboot.bin").is_file():

        return str(base)

    for child in sorted(base.iterdir()) if base.is_dir() else []:

        if (child / "eboot.bin").is_file():

            return str(child)

    return ""





def load_config():

    cfg = dict(DEFAULTS)

    try:

        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8-sig")))

    except (OSError, ValueError):

        pass

    if not cfg["game"] or not (Path(cfg["game"]) / "eboot.bin").is_file():

        cfg["game"] = find_game()

    return cfg





def save_config(cfg):

    USER.mkdir(parents=True, exist_ok=True)

    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")





def read_ini(path):

    values = {}

    try:

        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():

            if line.strip() and not line.startswith("#") and "=" in line:

                key, value = line.strip().split("=", 1)

                values[key] = value

    except OSError:

        pass

    return values





def write_ini(path, updates):

    """Update only the given keys; every other line the runtime wrote stays as it was."""

    path = Path(path)

    lines, seen = [], set()

    try:

        for line in path.read_text(encoding="utf-8-sig").splitlines():

            key = line.split("=", 1)[0] if "=" in line else None

            if key in updates:

                lines.append(f"{key}={updates[key]}")

                seen.add(key)

            else:

                lines.append(line)

    except OSError:

        pass

    lines += [f"{k}={v}" for k, v in updates.items() if k not in seen]

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")





def file_sha256(path):

    digest = hashlib.sha256()

    with open(path, "rb") as f:

        for block in iter(lambda: f.read(1 << 20), b""):

            digest.update(block)

    return digest.hexdigest()





def image_ready(game):

    r"""Whether out\ holds an image made from this game's current eboot.bin."""

    try:

        stamp = json.loads(STAMP.read_text(encoding="utf-8-sig"))

        return (stamp.get("eboot_sha256") == file_sha256(Path(game) / "eboot.bin")

                and all((OUT / name).is_file() for name in ("boot-linked.bin", "content.bin", "eboot.elf")))

    except (OSError, ValueError):

        return False





def prepare_image(game, progress):

    """Runs the preparation scripts on the game's eboot.bin. Returns an error text or None."""

    OUT.mkdir(parents=True, exist_ok=True)

    USER.mkdir(parents=True, exist_ok=True)

    with open(PREPARE_LOG, "w", encoding="utf-8", errors="replace") as log:

        for index, (name, extra) in enumerate(PIPELINE, 1):

            progress(f"Preparing the game image ({index}/{len(PIPELINE)}): {name[:-3]}…")

            script = [sys.executable, "--run-script", name] if FROZEN else [sys.executable, str(SCRIPTS / name)]

            result = subprocess.run(script + [str(game), "--out", str(OUT)] + extra, stdin=subprocess.DEVNULL,

                                    stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)

            if result.returncode:

                return f"{name} failed (exit {result.returncode}). See user\\prepare.log"

    STAMP.write_text(json.dumps({"eboot_sha256": file_sha256(Path(game) / "eboot.bin"), "game": str(game)}),

                     encoding="utf-8")

    return None





def prepare_content_profile(game, dlc_dir):

    """Refresh AppContent metadata for every launch, even when the game image is cached."""

    script = [sys.executable, "--run-script", "content_profile.py"] if FROZEN else [

        sys.executable, str(SCRIPTS / "content_profile.py")]

    command = script + [str(game), "--out", str(OUT), "--sku", "full", "--dlc-dir", str(dlc_dir)]

    USER.mkdir(parents=True, exist_ok=True)

    with open(PREPARE_LOG, "a", encoding="utf-8", errors="replace") as log:

        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,

                                creationflags=NO_WINDOW)

    if result.returncode:

        return f"content_profile.py failed (exit {result.returncode}). See user\\prepare.log"

    return None





def apply_dark_titlebar(window):

    """Enforce native Windows 10/11 dark title bar for consistent visual presentation."""

    try:

        window.update()

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())

        if not hwnd:

            hwnd = window.winfo_id()

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20

        value = ctypes.c_int(1)

        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(

            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))

        if res != 0:

            DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19

            ctypes.windll.dwmapi.DwmSetWindowAttribute(

                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, ctypes.byref(value), ctypes.sizeof(value))

    except Exception as e:

        log_debug(f"Dark title bar apply warning: {e}")




def apply_window_native_icon(window, icon_path):
    """Set native Win32 window and taskbar icons via WM_SETICON and SetClassLongPtrW."""
    if not icon_path or not os.path.isfile(str(icon_path)):
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        top_hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2) or hwnd

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE = 0x00000040

        hicon_big = ctypes.windll.user32.LoadImageW(
            None, str(icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        hicon_sm = ctypes.windll.user32.LoadImageW(
            None, str(icon_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
        )
        if hicon_big:
            ctypes.windll.user32.SendMessageW(top_hwnd, 0x0080, 1, hicon_big)
            ctypes.windll.user32.SendMessageW(top_hwnd, 0x0080, 0, hicon_sm or hicon_big)
            GCLP_HICON = -14
            GCLP_HICONSM = -34
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                ctypes.windll.user32.SetClassLongPtrW(top_hwnd, GCLP_HICON, hicon_big)
                if hicon_sm:
                    ctypes.windll.user32.SetClassLongPtrW(top_hwnd, GCLP_HICONSM, hicon_sm)
            else:
                ctypes.windll.user32.SetClassLongW(top_hwnd, GCLP_HICON, hicon_big)
                if hicon_sm:
                    ctypes.windll.user32.SetClassLongW(top_hwnd, GCLP_HICONSM, hicon_sm)
    except Exception as e:
        log_debug(f"apply_window_native_icon error: {e}")






# Button Texture Cache to avoid redundant PIL image generation during motion

# =============================================================================
# Modern AAA Vector Icon & Button Texture Cache (2x SSAA Engine)
# =============================================================================

_BTN_CACHE = {}
_ICON_SET = {}
_PILL_TOP_CROP = None
_PILL_BOT_CROP = None
_BTN_FONT = None
_BTN_FONT_HAS_ANCHOR = True

def find_asset_file(*names):
    """Locate an asset file in assets/, launcher/assets, launcher/, or root directory."""
    search_dirs = [
        ROOT / "assets",
        ROOT / "launcher" / "assets",
        ROOT / "launcher",
        ROOT,
        Path(sys._MEIPASS) / "assets" if hasattr(sys, "_MEIPASS") else None,
        Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else None,
        Path(__file__).resolve().parent / "assets",
        Path(__file__).resolve().parent,
    ]
    for d in search_dirs:
        if d and d.is_dir():
            for name in names:
                p = d / name
                if p.is_file():
                    return p
    return None

def load_asset_transparent(path, target_size, bg_slice=None):
    """
    Load pre-rendered UI assets (logo_basara, btn_play_game, btn_pills) removing solid
    black/dark backgrounds via luminance alpha or rounded pill masking.
    All dimensions and coordinates are strictly wrapped in int().
    """
    if Image is None:
        return None
    p = Path(path)
    if not p.is_file():
        for ext in (".jpeg", ".jpg", ".png", ".webp"):
            alt = p.with_suffix(ext)
            if alt.is_file():
                p = alt
                break
    if not p.is_file():
        return None

    try:
        im = Image.open(p)
    except Exception as e:
        log_debug(f"Failed to open asset {path}: {e}")
        return None

    name = p.name.lower()
    tw, th = int(target_size[0]), int(target_size[1])

    if "logo" in name:
        r, g, b = im.split()
        max_c = ImageChops.lighter(ImageChops.lighter(r, g), b)
        thresh = max_c.point(lambda val: 255 if val > 15 else 0)
        bbox = thresh.getbbox()
        crop = im.crop(bbox) if bbox else im

        rc, gc, bc = crop.split()
        max_crop = ImageChops.lighter(ImageChops.lighter(rc, gc), bc)
        lut = []
        for i in range(256):
            if i < 18:
                lut.append(0)
            elif i < 60:
                t = (i - 18) / (60 - 18)
                lut.append(int(255 * (t ** 1.15)))
            else:
                lut.append(min(255, int(i * 1.15 + 28)))
        alpha = max_crop.point(lut)
        rgba = crop.convert("RGBA")
        rgba.putalpha(alpha)

        aspect = rgba.width / max(rgba.height, 1)
        if tw / max(th, 1) > aspect:
            fin_w = int(th * aspect)
            fin_h = int(th)
        else:
            fin_w = int(tw)
            fin_h = int(tw / max(aspect, 0.001))

        resized = rgba.resize((max(fin_w, 1), max(fin_h, 1)), Image.Resampling.LANCZOS)
        if bg_slice is not None:
            bg_copy = bg_slice.copy().convert("RGBA")
            bx = int((bg_copy.width - resized.width) // 2)
            by = int((bg_copy.height - resized.height) // 2)
            bg_copy.alpha_composite(resized, (bx, by))
            return bg_copy
        return resized

    elif "play" in name:
        crop_box = (252, 96, 3844, 932) if (im.width == 4128 and im.height == 1024) else (0, 0, im.width, im.height)
        crop = im.crop(crop_box)
        resized = crop.resize((tw, th), Image.Resampling.LANCZOS).convert("RGBA")
        mask = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (tw - 1, th - 1)], radius=int(th // 2), fill=255)
        resized.putalpha(mask)
        return resized

    return im.resize((tw, th), Image.Resampling.LANCZOS)

def get_pill_slice(is_primary):
    """Slice pill background texture from assets/btn_pills.jpeg."""
    global _PILL_TOP_CROP, _PILL_BOT_CROP
    if is_primary and _PILL_TOP_CROP is not None:
        return _PILL_TOP_CROP
    if not is_primary and _PILL_BOT_CROP is not None:
        return _PILL_BOT_CROP

    pills_path = find_asset_file("btn_pills.jpeg", "btn_pills.png", "btn_pills.jpg")
    if pills_path and pills_path.is_file():
        try:
            im = Image.open(pills_path)
            _PILL_TOP_CROP = im.crop((1250, 80, 2894, 427))
            _PILL_BOT_CROP = im.crop((1086, 512 + 76, 3041, 512 + 444))
            return _PILL_TOP_CROP if is_primary else _PILL_BOT_CROP
        except Exception as e:
            log_debug(f"Could not slice btn_pills: {e}")
    return None

def generate_icon_set():
    """Generate crisp uniform 16x16 vector RGBA PNG icons drawn at 64x64 and downsampled via LANCZOS."""
    global _ICON_SET
    if _ICON_SET or Image is None or ImageDraw is None:
        return _ICON_SET

    white = (255, 255, 255, 255)

    def make_icon(draw_fn):
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(im))
        return im.resize((16, 16), Image.Resampling.LANCZOS)

    def draw_gamepad(d):
        d.rounded_rectangle([(8, 16), (56, 48)], radius=12, outline=white, width=6)
        d.line([(18, 32), (28, 32)], fill=white, width=6)
        d.line([(23, 27), (23, 37)], fill=white, width=6)
        d.ellipse([(40, 24), (46, 30)], fill=white)
        d.ellipse([(46, 30), (52, 36)], fill=white)
        d.ellipse([(34, 30), (40, 36)], fill=white)
        d.ellipse([(40, 36), (46, 42)], fill=white)

    def draw_keyboard(d):
        d.rounded_rectangle([(8, 18), (56, 46)], radius=6, outline=white, width=5)
        for row_y in [25, 33]:
            for col_x in [15, 23, 31, 39, 47]:
                d.rectangle([(col_x, row_y), (col_x + 4, row_y + 4)], fill=white)
        d.rectangle([(23, 40), (39, 42)], fill=white)

    def draw_analog(d):
        d.arc([(12, 36), (52, 54)], start=0, end=180, fill=white, width=5)
        d.line([(32, 22), (32, 44)], fill=white, width=6)
        d.ellipse([(20, 10), (44, 26)], outline=white, width=5)
        d.ellipse([(27, 15), (37, 21)], fill=white)

    def draw_reset(d):
        d.arc([(12, 12), (52, 52)], start=40, end=320, fill=white, width=6)
        d.polygon([(46, 8), (46, 26), (34, 17)], fill=white)

    def draw_bolt(d):
        d.polygon([(36, 8), (20, 34), (32, 34), (26, 56), (46, 28), (34, 28)], fill=white)

    def draw_cube(d):
        top, left, right, center = (32, 12), (14, 22), (50, 22), (32, 32)
        bot_left, bot_right, bottom = (14, 46), (50, 46), (32, 56)
        d.line([top, left, bot_left, bottom, bot_right, right, top], fill=white, width=5)
        d.line([left, center, right], fill=white, width=5)
        d.line([center, bottom], fill=white, width=5)

    def draw_doc(d):
        d.rounded_rectangle([(14, 10), (50, 54)], radius=4, outline=white, width=5)
        d.line([(22, 24), (42, 24)], fill=white, width=5)
        d.line([(22, 34), (42, 34)], fill=white, width=5)
        d.line([(22, 44), (34, 44)], fill=white, width=5)

    def draw_music(d):
        d.ellipse([(12, 38), (24, 50)], fill=white)
        d.ellipse([(36, 32), (48, 44)], fill=white)
        d.line([(22, 20), (22, 44)], fill=white, width=5)
        d.line([(46, 14), (46, 38)], fill=white, width=5)
        d.polygon([(20, 16), (48, 10), (48, 20), (20, 26)], fill=white)

    def draw_save(d):
        d.rounded_rectangle([(12, 12), (52, 52)], radius=5, outline=white, width=5)
        d.rectangle([(20, 12), (44, 26)], fill=white)
        d.rectangle([(18, 34), (46, 52)], fill=white)
        d.rectangle([(22, 38), (32, 48)], fill=(0, 0, 0, 255))

    def draw_stop(d):
        d.rounded_rectangle([(16, 16), (48, 48)], radius=6, fill=white)

    def draw_credits(d):
        d.ellipse([(18, 14), (30, 26)], fill=white)
        d.ellipse([(34, 14), (46, 26)], fill=white)
        d.arc([(12, 30), (36, 52)], start=180, end=360, fill=white, width=5)
        d.arc([(28, 30), (52, 52)], start=180, end=360, fill=white, width=5)

    def draw_update(d):
        d.arc([(12, 12), (52, 52)], start=30, end=300, fill=white, width=6)
        d.polygon([(46, 10), (46, 26), (34, 18)], fill=white)

    def draw_folder(d):
        d.polygon([(10, 16), (24, 16), (30, 22), (54, 22), (54, 48), (10, 48)], outline=white, width=5)

    _ICON_SET = {
        "gamepad": make_icon(draw_gamepad),
        "keyboard": make_icon(draw_keyboard),
        "analog": make_icon(draw_analog),
        "reset": make_icon(draw_reset),
        "bolt": make_icon(draw_bolt),
        "cube": make_icon(draw_cube),
        "doc": make_icon(draw_doc),
        "music": make_icon(draw_music),
        "save": make_icon(draw_save),
        "stop": make_icon(draw_stop),
        "credits": make_icon(draw_credits),
        "update": make_icon(draw_update),
        "folder": make_icon(draw_folder),
    }
    return _ICON_SET

def detect_icon_and_clean_text(raw_text, explicit_icon=None):
    """Detect icon type from label text and strip leading Unicode symbols/emojis."""
    clean = str(raw_text).strip()
    icon = explicit_icon

    lower = clean.lower()
    if not icon:
        if "play" in lower or "mainkan" in lower:
            icon = "play_crest"
        elif "primary gamepad" in lower or "stik 1 = p1" in lower or "controller utama" in lower or "gamepad utama" in lower:
            icon = "gamepad"
        elif "kbm co-op" in lower or "kbm = p1" in lower or "coop" in lower or "co-op" in lower:
            icon = "keyboard"
        elif "kbm" in lower or "keyboard" in lower:
            icon = "keyboard"
        elif "control gamepad" in lower or "map gamepad" in lower or "map controller" in lower or "atur gamepad" in lower or "atur stik" in lower:
            icon = "gamepad"
        elif "analog" in lower or "sticks" in lower:
            icon = "analog"
        elif "reset" in lower:
            icon = "reset"
        elif "cheat" in lower or "mod" in lower:
            icon = "bolt"
        elif "dlc" in lower:
            icon = "cube"
        elif "audio log" in lower or "log audio" in lower:
            icon = "music"
        elif "log" in lower:
            icon = "doc"
        elif "save" in lower or "data save" in lower:
            icon = "save"
        elif "browse" in lower or "pilih folder" in lower:
            icon = "folder"
        elif "stop" in lower or "hentikan" in lower:
            icon = "stop"
        elif "credit" in lower or "komunitas" in lower or "community" in lower or "kredit" in lower:
            icon = "credits"
        elif "update" in lower or "cek update" in lower:
            icon = "update"

    import re
    clean = clean.replace("\u2026", "...")
    clean = re.sub(r"^[^a-zA-Z0-9_()[\].,\-\+\/]+", "", clean).strip()
    return icon, clean

def get_ui_font(size_px: int, bold: bool = True):
    """Bulletproof font resolver searching Windows fonts directory with safe fallback."""
    if ImageFont is None:
        return None
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates = (
        ["segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"]
        if bold else ["segoeui.ttf", "arial.ttf"]
    )
    for name in candidates:
        p = os.path.join(windir, "Fonts", name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, int(size_px))
            except Exception:
                continue
    return ImageFont.load_default()

def get_btn_font(size=10):
    """Compatibility wrapper returning TrueType font with anchor support."""
    f = get_ui_font(size, bold=True)
    has_anchor = hasattr(f, "getbbox") and not isinstance(f, ImageFont.ImageFont)
    return f, has_anchor

def measure_text_width(text, size_px=9, bold=False):
    """Bulletproof text width measurement without depending on tkinter.font."""
    if not text:
        return 0
    try:
        fnt = get_ui_font(size_px, bold=bold)
        if fnt and hasattr(fnt, "getbbox"):
            bbox = fnt.getbbox(str(text))
            return bbox[2] - bbox[0]
    except Exception:
        pass
    char_w = (size_px * 0.65) if bold else (size_px * 0.55)
    return int(len(str(text)) * char_w)

def render_btn_pil_base(btn_w, btn_h, is_primary, state, icon_name, clean_label_text):
    """Render high-fidelity button texture in PIL with 2x SSAA, gradients, borders, and typography."""
    if Image is None or ImageDraw is None:
        return None

    # 1. Primary Action Button ("PLAY GAME")
    if is_primary and btn_h >= 45:
        play_path = find_asset_file("btn_play_game.jpeg", "btn_play_game.png", "btn_play_game.jpg")
        if play_path:
            btn_im = load_asset_transparent(play_path, (btn_w, btn_h))
            if btn_im:
                draw = ImageDraw.Draw(btn_im)
                if state == "hover":
                    draw.rounded_rectangle(
                        [(1, 1), (btn_w - 2, btn_h - 2)],
                        radius=int(btn_h // 2), outline=(229, 193, 104, 220), width=2
                    )
                elif state == "pressed":
                    overlay = Image.new("RGBA", (btn_w, btn_h), (0, 0, 0, 50))
                    btn_im.alpha_composite(overlay)
                return btn_im

    # 2. Sliced Pill Background from btn_pills.jpeg or 2x SSAA procedural rendering
    pill_slice = get_pill_slice(is_primary)
    if pill_slice is not None:
        im = pill_slice.resize((btn_w, btn_h), Image.Resampling.LANCZOS).convert("RGBA")
        mask = Image.new("L", (btn_w, btn_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (btn_w - 1, btn_h - 1)], radius=int(btn_h // 2), fill=255)
        im.putalpha(mask)
    else:
        # Procedural 2x SSAA rendering
        sw, sh = btn_w * 2, btn_h * 2
        s_rad = sh // 2
        im_ssaa = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))

        if is_primary:
            c1, c2 = (214, 40, 40), (122, 12, 18)
        else:
            if state == "hover":
                c1, c2 = (28, 52, 98), (14, 26, 56)
            else:
                c1, c2 = (18, 32, 62), (9, 17, 36)

        grad = Image.new("RGBA", (sw, sh))
        d_g = ImageDraw.Draw(grad)
        for y in range(sh):
            t = y / max(sh - 1, 1)
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            d_g.line([(0, y), (sw, y)], fill=(r, g, b, 240))

        mask = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (sw - 1, sh - 1)], radius=s_rad, fill=255)
        im_ssaa.paste(grad, (0, 0), mask)

        # Border
        draw_s = ImageDraw.Draw(im_ssaa)
        if is_primary:
            b_col = (255, 133, 133, 240) if state != "hover" else (255, 180, 180, 255)
            draw_s.rounded_rectangle([(1, 1), (sw - 2, sh - 2)], radius=s_rad, outline=b_col, width=3)
        else:
            if state == "hover":
                b_col = (99, 179, 237, 255)
                draw_s.rounded_rectangle([(1, 1), (sw - 2, sh - 2)], radius=s_rad, outline=b_col, width=3)
            else:
                b_col = (72, 138, 210, 200)
                draw_s.rounded_rectangle([(1, 1), (sw - 2, sh - 2)], radius=s_rad, outline=b_col, width=2)
                draw_s.line([(s_rad, 2), (sw - s_rad, 2)], fill=(130, 195, 255, 120), width=2)

        im = im_ssaa.resize((btn_w, btn_h), Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(im)
    if state == "hover" and pill_slice is not None:
        glow_col = (255, 180, 180, 255) if is_primary else (99, 179, 237, 255)
        draw.rounded_rectangle([(0, 0), (btn_w - 1, btn_h - 1)], radius=int(btn_h // 2), outline=glow_col, width=2)
    elif state == "pressed":
        overlay = Image.new("RGBA", (btn_w, btn_h), (0, 0, 0, 50))
        im.alpha_composite(overlay)
    elif state == "disabled":
        overlay = Image.new("RGBA", (btn_w, btn_h), (12, 18, 32, 140))
        im.alpha_composite(overlay)

    # 3. Retrieve 16x16 icon
    icons = generate_icon_set()
    icon_img = icons.get(icon_name) if icon_name else None

    # 4. Typography & Layout Symmetrical Compositing
    font_size = 15 if (is_primary and btn_h >= 45) else 13
    font = get_ui_font(font_size, bold=True)
    has_anchor = True
    if font and clean_label_text:
        try:
            tw = int(draw.textlength(clean_label_text, font=font))
        except Exception:
            bbox = font.getbbox(clean_label_text)
            tw = int(bbox[2] - bbox[0])
    else:
        tw = int(len(clean_label_text) * 8)

    total_w = int((16 + 8 + tw) if icon_img else tw)
    start_x = int((btn_w - total_w) // 2)

    fg = (255, 255, 255, 255) if (is_primary or state == "hover") else ((160, 175, 195, 220) if state == "disabled" else (225, 235, 250, 245))
    shadow_col = (40, 5, 8, 220) if is_primary else (4, 8, 20, 220)

    if icon_img:
        icon_tint = Image.new("RGBA", (16, 16), fg)
        icon_tint.putalpha(icon_img.split()[3])
        im.paste(icon_tint, (start_x, int((btn_h - 16) // 2)), icon_tint)

        tx = int(start_x + 24)
        ty = int(btn_h // 2)
        if clean_label_text:
            if has_anchor:
                draw.text((tx + 1, ty + 1), clean_label_text, font=font, fill=shadow_col, anchor="lm")
                draw.text((tx, ty), clean_label_text, font=font, fill=fg, anchor="lm")
            else:
                draw.text((tx + 1, ty - 6 + 1), clean_label_text, font=font, fill=shadow_col)
                draw.text((tx, ty - 6), clean_label_text, font=font, fill=fg)
    elif clean_label_text:
        tx = int(btn_w // 2)
        ty = int(btn_h // 2)
        if has_anchor:
            draw.text((tx + 1, ty + 1), clean_label_text, font=font, fill=shadow_col, anchor="mm")
            draw.text((tx, ty), clean_label_text, font=font, fill=fg, anchor="mm")
        else:
            draw.text((tx - tw // 2 + 1, ty - 6 + 1), clean_label_text, font=font, fill=shadow_col)
            draw.text((tx - tw // 2, ty - 6), clean_label_text, font=font, fill=fg)

    return im

def get_cached_btn_frame(w, h, is_primary=False, state="normal", icon_name=None, clean_label_text="", step=0):
    """
    Generate and cache pre-rendered button frames with 60 FPS cross-fade hover states.
    step = 0 (100% normal) to 4 (100% hover).
    """
    btn_w, btn_h = int(w), int(h)
    cache_key = (btn_w, btn_h, is_primary, state, icon_name, clean_label_text, step)
    if cache_key in _BTN_CACHE:
        return _BTN_CACHE[cache_key]

    if state == "pressed":
        im = render_btn_pil_base(btn_w, btn_h, is_primary, "pressed", icon_name, clean_label_text)
        photo = ImageTk.PhotoImage(im) if im else None
        _BTN_CACHE[cache_key] = photo
        return photo

    if state == "disabled":
        im = render_btn_pil_base(btn_w, btn_h, is_primary, "disabled", icon_name, clean_label_text)
        photo = ImageTk.PhotoImage(im) if im else None
        _BTN_CACHE[cache_key] = photo
        return photo

    # Normal / Hover cross-fade frames
    norm_key = (btn_w, btn_h, is_primary, "raw_norm", icon_name, clean_label_text)
    hov_key = (btn_w, btn_h, is_primary, "raw_hov", icon_name, clean_label_text)

    if norm_key not in _BTN_CACHE:
        _BTN_CACHE[norm_key] = render_btn_pil_base(btn_w, btn_h, is_primary, "normal", icon_name, clean_label_text)
    if hov_key not in _BTN_CACHE:
        _BTN_CACHE[hov_key] = render_btn_pil_base(btn_w, btn_h, is_primary, "hover", icon_name, clean_label_text)

    im_norm = _BTN_CACHE[norm_key]
    im_hov = _BTN_CACHE[hov_key]

    if im_norm is None or im_hov is None:
        return None

    t = max(0.0, min(1.0, step / 4.0))
    if t == 0.0:
        final_im = im_norm
    elif t == 1.0:
        final_im = im_hov
    else:
        final_im = Image.blend(im_norm, im_hov, t)

    photo = ImageTk.PhotoImage(final_im)
    _BTN_CACHE[cache_key] = photo
    return photo

def get_cached_btn_img(w, h, is_primary=False, state="normal", icon_name=None, clean_label_text=""):
    """Compatibility wrapper returning frame at step 0 for normal, or step 4 for hover."""
    step = 4 if state == "hover" else 0
    return get_cached_btn_frame(w, h, is_primary, state, icon_name, clean_label_text, step)


class StatusCanvasProxy:
    """Proxy object so self.status.config(text=...) / self.status.configure(text=...) updates canvas text items."""
    def __init__(self, canvas, shadow_id, text_id):
        self.canvas = canvas
        self.shadow_id = shadow_id
        self.text_id = text_id
        self._text = ""

    def config(self, **kwargs):
        if "text" in kwargs:
            self._text = kwargs["text"]
            try:
                self.canvas.itemconfigure(self.shadow_id, text=self._text)
                self.canvas.itemconfigure(self.text_id, text=self._text)
            except Exception:
                pass

    def configure(self, **kwargs):
        self.config(**kwargs)

    def cget(self, key):
        if key == "text":
            return self._text
        return ""

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        if key == "text":
            self.config(text=value)


class ModernButton(tk.Canvas):
    """Modern AAA Gaming Button with gradient, glow, metallic borders, vector icons, and 60 FPS motion."""
    def __init__(self, parent, text="", command=None, width=120, height=36,
                 is_primary=False, state="normal", font=None, bg_color=CARD_BG, icon=None):
        super().__init__(parent, width=width, height=height, bg=bg_color,
                         highlightthickness=0, bd=0, cursor="hand2" if state == "normal" else "arrow")
        self.text = text
        self.icon = icon
        self.command = command
        self.w = width
        self.h = height
        self.is_primary = is_primary
        self.state_mode = state
        self.font = font
        self.bg_color = bg_color

        self.current_step = 0
        self.target_step = 0
        self.max_steps = 4
        self.hovered = False
        self.pressed = False
        self._animating = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_resize)
        self.render()

    def _on_resize(self, event):
        if event.width > 20 and (event.width != self.w or event.height != self.h):
            self.w = event.width
            self.h = event.height
            self.render()

    def _on_enter(self, event):
        if self.state_mode != "normal":
            return
        self.hovered = True
        self.target_step = 4
        self.config(cursor="hand2")
        if not self._animating:
            self._animate()

    def _on_leave(self, event):
        if self.state_mode != "normal":
            return
        self.hovered = False
        self.pressed = False
        self.target_step = 0
        self.config(cursor="arrow")
        if not self._animating:
            self._animate()

    def _on_press(self, event):
        if self.state_mode != "normal":
            return
        self.pressed = True
        self.render()

    def _on_release(self, event):
        if self.state_mode != "normal":
            return
        was_pressed = self.pressed
        self.pressed = False
        self.render()
        if was_pressed and 0 <= event.x <= self.w and 0 <= event.y <= self.h:
            if callable(self.command):
                self.command()

    def _animate(self):
        if self.current_step < self.target_step:
            self.current_step += 1
            self._animating = True
            self.render()
            self.after(28, self._animate)
        elif self.current_step > self.target_step:
            self.current_step -= 1
            self._animating = True
            self.render()
            self.after(28, self._animate)
        else:
            self._animating = False

    def config(self, **kwargs):
        if "state" in kwargs:
            self.state_mode = kwargs.pop("state")
            super().config(cursor="hand2" if self.state_mode == "normal" else "arrow")
        if "text" in kwargs:
            self.text = kwargs.pop("text")
        if "icon" in kwargs:
            self.icon = kwargs.pop("icon")
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        super().config(**kwargs)
        self.render()

    def configure(self, **kwargs):
        self.config(**kwargs)

    def pulse_tick(self, phase):
        pass

    def render(self):
        self.delete("all")
        y_offset = -1 if (self.hovered and not self.pressed) else (1 if self.pressed else 0)
        state_key = "disabled" if self.state_mode == "disabled" else ("pressed" if self.pressed else "normal")

        icon_name, clean_text = detect_icon_and_clean_text(self.text, self.icon)
        step = self.current_step if (state_key == "normal") else 0
        btn_img = get_cached_btn_frame(int(self.w), int(self.h), self.is_primary, state_key, icon_name, clean_text, step)
        if btn_img:
            self._img_ref = btn_img
            self.create_image(int(self.w // 2), int((self.h // 2) + y_offset), image=btn_img)
        else:
            self.create_rectangle(2, int(2 + y_offset), int(self.w - 2), int(self.h - 2 + y_offset),
                                  fill=RED_PRIMARY if self.is_primary else "#101726", outline=CARD_BORDER)
            self.create_text(int(self.w // 2), int((self.h // 2) + y_offset), text=clean_text, fill="#FFFFFF")



class StatusPill(tk.Canvas):
    """Modern live status pill with pulsing indicator dot and glowing outline."""
    def __init__(self, parent, bg_color=HEADER_BG, width=170, height=30):
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0, bd=0)
        self.w = width
        self.h = height
        self.state_mode = "ready"
        self.text = "Siap dimainkan"
        self.dot_id = None
        self.render()

    def set_status(self, state, text):
        self.state_mode = state
        self.text = text
        self.render()

    def pulse_tick(self, phase):
        dot_r = 4.0 + 0.6 * math.sin(phase)
        cx, cy = 18, self.h // 2
        if self.dot_id:
            try:
                self.coords(self.dot_id, cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r)
            except Exception:
                pass



    def render(self):

        self.delete("all")

        if self.state_mode == "ready":

            pill_bg, border_col, dot_col, text_col = "#112416", "#22C55E", "#22C55E", "#4ADE80"

        elif self.state_mode == "starting":

            pill_bg, border_col, dot_col, text_col = "#2A1216", "#D32F2F", "#D32F2F", "#F87171"

        elif self.state_mode == "running":

            pill_bg, border_col, dot_col, text_col = "#0D2036", "#008CFF", "#008CFF", "#60A5FA"

        else:

            pill_bg, border_col, dot_col, text_col = "#281216", "#EF4444", "#EF4444", "#F87171"



        r = 8

        x1, y1, x2, y2 = 2, 2, self.w - 2, self.h - 2

        pts = [

            x1 + r, y1, x1 + r, y1,

            x2 - r, y1, x2 - r, y1,

            x2, y1,

            x2, y1 + r, x2, y1 + r,

            x2, y2 - r, x2, y2 - r,

            x2, y2,

            x2 - r, y2, x2 - r, y2,

            x1 + r, y2, x1 + r, y2,

            x1, y2,

            x1, y2 - r, x1, y2 - r,

            x1, y1 + r, x1, y1 + r,

            x1, y1

        ]

        self.create_polygon(pts, fill=pill_bg, outline=border_col, width=1, smooth=True)



        # Bright indicator dot

        cy = self.h // 2

        self.create_oval(12, cy - 4, 20, cy + 4, fill=dot_col, outline="")

        self.create_text(

            (self.w // 2) + 5, cy,

            text=self.text, fill=text_col, font=("Segoe UI Semibold", 9)

        )





class LanguageToggle(tk.Canvas):

    """Pill-shaped toggle button for instant EN <-> ID language switching."""

    def __init__(self, parent, current_lang="id", on_change=None, bg_color=HEADER_BG):

        super().__init__(parent, width=96, height=32, bg=bg_color, highlightthickness=0, bd=0, cursor="hand2")

        self.current_lang = current_lang

        self.on_change = on_change

        self.bg_color = bg_color

        self.hovered_side = None



        self.bind("<Button-1>", self._on_click)

        self.bind("<Motion>", self._on_motion)

        self.bind("<Leave>", self._on_leave)

        self.render()



    def _on_click(self, event):

        new_lang = "en" if event.x < 48 else "id"

        if new_lang != self.current_lang:

            self.current_lang = new_lang

            self.render()

            if callable(self.on_change):

                self.on_change(new_lang)



    def _on_motion(self, event):

        side = "en" if event.x < 48 else "id"

        if side != self.hovered_side:

            self.hovered_side = side

            self.render()



    def _on_leave(self, event):

        self.hovered_side = None

        self.render()



    def set_language(self, lang):

        self.current_lang = lang

        self.render()



    def render(self):

        self.delete("all")

        self.create_polygon(

            6, 2, 90, 2, 94, 6, 94, 26, 90, 30, 6, 30, 2, 26, 2, 6,

            fill="#0E1422", outline=CARD_BORDER, width=1, smooth=True

        )



        if self.current_lang == "en":

            self.create_polygon(

                5, 4, 46, 4, 48, 6, 48, 26, 46, 28, 5, 28, 3, 26, 3, 6,

                fill=RED_PRIMARY, outline=RED_HOVER, width=1, smooth=True

            )

            en_color = "#FFFFFF"

            id_color = MUTED if self.hovered_side != "id" else FG

        else:

            self.create_polygon(

                48, 4, 91, 4, 93, 6, 93, 26, 91, 28, 48, 28, 46, 26, 46, 6,

                fill=RED_PRIMARY, outline=RED_HOVER, width=1, smooth=True

            )

            id_color = "#FFFFFF"

            en_color = MUTED if self.hovered_side != "en" else FG



        self.create_text(25, 16, text="EN", fill=en_color, font=("Segoe UI Bold", 9))

        self.create_text(71, 16, text="ID", fill=id_color, font=("Segoe UI Bold", 9))






# =============================================================================
# SINGLE-CANVAS ARCHITECTURE CORE CLASSES & RENDERING ENGINE
# =============================================================================

def get_ui_font(size_px: int, bold: bool = True):
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates = (
        ["segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"]
        if bold else ["segoeui.ttf", "arial.ttf"]
    )
    for name in candidates:
        p = os.path.join(windir, "Fonts", name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, int(size_px))
            except Exception:
                continue
    return ImageFont.load_default()

def compose_full_window_bg(win_w, win_h):
    """
    Composite 100% full-bleed Date Masamune wallpaper, 3 left unbroken translucent glass cards
    with horizontal alpha gradient fill, gradient border, and top-left specular flare,
    and right hero logo into ONE master PIL Image.
    NO solid dark fill and NO horizontal line on top header so Date Masamune's crescent
    helmet horn extends cleanly into the header space without being chopped!
    Cards 1 & 2 dissolve seamlessly into Masamune's armor and face with zero vertical seam!
    """
    art_path = ROOT / "assets" / "launcherbg.jpg"
    if not art_path.is_file():
        art_path = ROOT / "launcherbg.jpg"
    
    art = Image.open(art_path).convert("RGBA")
    scale = max(win_w / float(art.width), win_h / float(art.height))
    nw, nh = int(art.width * scale), int(art.height * scale)
    art_resized = art.resize((nw, nh), Image.Resampling.LANCZOS)
    
    # Anchor to preserve Masamune on the right 45% of canvas
    art_x = win_w - nw
    art_y = 0
    bg = Image.new("RGBA", (win_w, win_h), (8, 15, 36, 255))
    bg.alpha_composite(art_resized, (art_x, art_y))
    
    # Sakura petals & electric sparks
    import random, math
    random.seed(42)
    fx = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
    d_fx = ImageDraw.Draw(fx)
    for _ in range(35):
        px = random.randint(int(win_w * 0.25), win_w - 20)
        py = random.randint(20, win_h - 20)
        psize = random.randint(6, 13)
        pangle = random.uniform(0, 3.14159)
        pts = [
            (px + int(psize * math.cos(pangle)), py + int(psize * math.sin(pangle))),
            (px + int(psize * 0.5 * math.cos(pangle + 1.2)), py + int(psize * 0.5 * math.sin(pangle + 1.2))),
            (px + int(psize * 0.8 * math.cos(pangle + 3.14)), py + int(psize * 0.8 * math.sin(pangle + 3.14))),
            (px + int(psize * 0.5 * math.cos(pangle - 1.2)), py + int(psize * 0.5 * math.sin(pangle - 1.2)))
        ]
        d_fx.polygon(pts, fill=(255, 192, 208, random.randint(80, 160)))
    for _ in range(40):
        bx = random.randint(int(win_w * 0.4), win_w - 10)
        by = random.randint(30, win_h - 30)
        br = random.randint(1, 2)
        d_fx.ellipse([(bx - br, by - br), (bx + br, by + br)], fill=(88, 184, 255, random.randint(100, 220)))
    bg.alpha_composite(fx.filter(ImageFilter.GaussianBlur(1)))
    
    # 61.2% Left / 38.8% Right Proportional Split
    left_card_x1 = int(win_w * 0.015)
    left_card_x2 = int(win_w * 0.612)
    right_cx = int(win_w * 0.806)
    right_col_w = win_w - left_card_x2
    
    cards_y = [
        (62, int(win_h * 0.195)),                        # Card 1: GAME LOCATION
        (int(win_h * 0.21), int(win_h * 0.545)),         # Card 2: DISPLAY & GRAPHICS
        (int(win_h * 0.56), win_h - 14),                 # Card 3: CONTROLLER & INPUT
    ]
    
    blurred_bg = bg.filter(ImageFilter.GaussianBlur(2))
    
    # 1. Horizontal Alpha Gradient Fill (Left-to-Right Dissolve)
    cards_layer = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
    for idx, (cy1, cy2) in enumerate(cards_y):
        cw = left_card_x2 - left_card_x1
        ch = cy2 - cy1
        
        c_mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(c_mask).rounded_rectangle([(0, 0), (cw - 1, ch - 1)], radius=12, fill=255)
        
        card_fill = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d_cf = ImageDraw.Draw(card_fill)
        
        if idx in (0, 1): # Cards 1 & 2: Dissolve into transparency on right side (45% -> 88%)
            split_x = int(cw * 0.45)
            fade_end = int(cw * 0.88)
            for x in range(cw):
                if x <= split_x:
                    a = 170
                elif x < fade_end:
                    t = (x - split_x) / float(fade_end - split_x)
                    a = int(170 * 0.5 * (1.0 + math.cos(math.pi * t)))
                else:
                    a = 0
                if a > 0:
                    d_cf.line([(x, 0), (x, ch - 1)], fill=(5, 11, 26, a))
            
            # Fade blur mask on right 35% so Masamune's face is 100% crisp with zero blur seam!
            mask_fade_start = int(cw * 0.60)
            mask_fade_end = int(cw * 0.88)
            for px in range(mask_fade_start, cw):
                f = 0.0 if px >= mask_fade_end else 0.5 * (1.0 + math.cos(math.pi * (px - mask_fade_start) / float(mask_fade_end - mask_fade_start)))
                for py in range(ch):
                    c_mask.putpixel((px, py), int(c_mask.getpixel((px, py)) * f))
        else: # Card 3: fades smoothly from 185 to 95
            for x in range(cw):
                t = x / float(max(cw - 1, 1))
                a = int(185 - (185 - 95) * t)
                d_cf.line([(x, 0), (x, ch - 1)], fill=(5, 11, 26, a))
                
        bg_slice = blurred_bg.crop((left_card_x1, cy1, left_card_x2, cy2))
        card_comp = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        card_comp.paste(bg_slice, (0, 0), c_mask)
        card_comp.alpha_composite(card_fill)
        cards_layer.paste(card_comp, (left_card_x1, cy1), c_mask)
        
    bg = Image.alpha_composite(bg, cards_layer)
    
    # 2. Outer Glow & Border Lines (No right vertical border on Cards 1 & 2!)
    glow_layer = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
    d_glow = ImageDraw.Draw(glow_layer)
    for idx, (cy1, cy2) in enumerate(cards_y):
        if idx == 2:
            d_glow.rounded_rectangle([(left_card_x1 - 2, cy1 - 2), (left_card_x2 + 2, cy2 + 2)], radius=14, outline=(29, 111, 235, 120), width=5)
        else:
            cw = left_card_x2 - left_card_x1
            ch = cy2 - cy1
            g_im = Image.new("RGBA", (cw + 10, ch + 10), (0, 0, 0, 0))
            d_g = ImageDraw.Draw(g_im)
            fade_end = int(cw * 0.85)
            d_g.line([(12, 2), (fade_end, 2)], fill=(29, 111, 235, 120), width=5)
            d_g.line([(2, 12), (2, ch - 12 + 2)], fill=(29, 111, 235, 120), width=5)
            d_g.line([(12, ch + 2), (fade_end, ch + 2)], fill=(29, 111, 235, 120), width=5)
            d_g.arc([(2, 2), (26, 26)], start=180, end=270, fill=(29, 111, 235, 120), width=5)
            d_g.arc([(2, ch - 22), (26, ch + 2)], start=90, end=180, fill=(29, 111, 235, 120), width=5)
            glow_layer.paste(g_im, (left_card_x1 - 2, cy1 - 2), g_im)
    bg.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(5)))
    
    border_layer = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
    for idx, (cy1, cy2) in enumerate(cards_y):
        cw = left_card_x2 - left_card_x1
        ch = cy2 - cy1
        b_im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d_b = ImageDraw.Draw(b_im)
        
        if idx == 2:
            d_b.rounded_rectangle([(0, 0), (cw - 1, ch - 1)], radius=12, outline=(56, 152, 255, 235), width=2)
        else:
            fade_start = int(cw * 0.60)
            fade_end = int(cw * 0.88)
            d_b.line([(12, 0), (fade_start, 0)], fill=(56, 152, 255, 235), width=2)
            for px in range(fade_start, fade_end):
                t = (px - fade_start) / float(fade_end - fade_start)
                a = int(235 * 0.5 * (1.0 + math.cos(math.pi * t)))
                d_b.line([(px, 0), (px, 1)], fill=(56, 152, 255, a))
                
            d_b.line([(0, 12), (0, ch - 13)], fill=(56, 152, 255, 235), width=2)
            
            d_b.line([(12, ch - 1), (fade_start, ch - 1)], fill=(56, 152, 255, 235), width=2)
            for px in range(fade_start, fade_end):
                t = (px - fade_start) / float(fade_end - fade_start)
                a = int(235 * 0.5 * (1.0 + math.cos(math.pi * t)))
                d_b.line([(px, ch - 2), (px, ch - 1)], fill=(56, 152, 255, a))
                
            d_b.arc([(0, 0), (24, 24)], start=180, end=270, fill=(56, 152, 255, 235), width=2)
            d_b.arc([(0, ch - 25), (24, ch - 1)], start=90, end=180, fill=(56, 152, 255, 235), width=2)
        
        # Specular flare on top-left horizontal edge & vertical edge
        flare_im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d_flare = ImageDraw.Draw(flare_im)
        for fx in range(14, min(180, cw - 1)):
            t_f = (fx - 14) / (180.0 - 14.0)
            r_f = int(165 + (56 - 165) * t_f)
            g_f = int(243 + (152 - 243) * t_f)
            a_f = int(230 * (1.0 - t_f))
            d_flare.line([(fx, 0), (fx, 1)], fill=(r_f, g_f, 255, a_f))
        for fy in range(14, min(70, ch - 1)):
            t_f = (fy - 14) / (70.0 - 14.0)
            r_f = int(165 + (56 - 165) * t_f)
            g_f = int(243 + (152 - 243) * t_f)
            a_f = int(210 * (1.0 - t_f))
            d_flare.line([(0, fy), (1, fy)], fill=(r_f, g_f, 255, a_f))
        d_flare.arc([(0, 0), (24, 24)], start=180, end=270, fill=(200, 248, 255, 240), width=2)
        flare_glow = flare_im.filter(ImageFilter.GaussianBlur(2))
        b_im.alpha_composite(flare_glow)
        b_im.alpha_composite(flare_im)
        border_layer.paste(b_im, (left_card_x1, cy1), b_im)
        
    bg = Image.alpha_composite(bg, border_layer)
    
    # 3. Right Sidebar 100% Solid & Vibrant Logo
    logo_path = ROOT / "assets" / "logo_basara.png"
    if not logo_path.is_file():
        logo_path = ROOT / "assets" / "logo_basara.jpeg"
    if logo_path.is_file():
        if logo_path.suffix.lower() == ".png":
            l_rgba = Image.open(logo_path).convert("RGBA")
        else:
            l_im = Image.open(logo_path)
            rc, gc, bc = l_im.split()[:3]
            max_c = ImageChops.lighter(ImageChops.lighter(rc, gc), bc)
            lut = [0 if i < 18 else (min(255, int((i - 18) * 1.25))) for i in range(256)]
            alpha = max_c.point(lut)
            l_rgba = l_im.convert("RGBA")
            l_rgba.putalpha(alpha)
            
        logo_cy = int(win_h * 0.415)
        target_lw = int(right_col_w * 0.84)
        aspect = l_rgba.width / max(l_rgba.height, 1)
        target_lh = int(target_lw / aspect)
        max_lh = int(win_h * 0.22)
        if target_lh > max_lh:
            target_lh = max_lh
            target_lw = int(target_lh * aspect)
        l_resized = l_rgba.resize((target_lw, target_lh), Image.Resampling.LANCZOS)
        bg.alpha_composite(l_resized, (right_cx - target_lw // 2, logo_cy - target_lh // 2))

        # Dark Translucent Backing Vignette Behind the Right Text Stack
        y1_v = int(win_h * 0.565)
        y4_v = int(win_h * 0.662)
        vig_w = int(right_col_w * 0.86)
        vig_h = (y4_v - y1_v) + 42
        vig_layer = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
        d_vig = ImageDraw.Draw(vig_layer)
        d_vig.rounded_rectangle([(right_cx - vig_w // 2, y1_v - 12), (right_cx + vig_w // 2, y1_v - 12 + vig_h)],
                                radius=16, fill=(4, 8, 18, 175))
        bg = Image.alpha_composite(bg, vig_layer.filter(ImageFilter.GaussianBlur(12)))
        
    return bg

def create_control_sprites():
    sprites = {}
    im_r_off = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im_r_off)
    d.ellipse([(6, 6), (58, 58)], fill=(7, 14, 32, 255), outline=(120, 40, 50, 255), width=6)
    sprites["radio_off"] = im_r_off.resize((16, 16), Image.Resampling.LANCZOS)
    
    im_r_on = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im_r_on)
    d.ellipse([(4, 4), (60, 60)], outline=(255, 60, 60, 140), width=8)
    d.ellipse([(6, 6), (58, 58)], fill=(7, 14, 32, 255), outline=(255, 70, 70, 255), width=12)
    d.ellipse([(20, 20), (44, 44)], fill=(255, 75, 75, 255))
    sprites["radio_on"] = im_r_on.resize((16, 16), Image.Resampling.LANCZOS)
    
    im_c_off = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im_c_off)
    d.rounded_rectangle([(6, 6), (58, 58)], radius=16, fill=(8, 16, 36, 220), outline=(120, 40, 50, 255), width=6)
    sprites["check_off"] = im_c_off.resize((16, 16), Image.Resampling.LANCZOS)
    
    im_c_on = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im_c_on)
    d.rounded_rectangle([(6, 6), (58, 58)], radius=16, fill=(239, 68, 68, 255), outline=(255, 120, 120, 255), width=4)
    pts = [(16, 32), (26, 44), (48, 18)]
    d.line(pts, fill=(7, 14, 32, 255), width=8, joint="curve")
    sprites["check_on"] = im_c_on.resize((16, 16), Image.Resampling.LANCZOS)
    return sprites

def generate_vector_icons():
    """Generate crisp Samurai Crimson outline icons for section headers & 16x16 button icons."""
    icons = {}
    white = (255, 255, 255, 255)
    red_primary = (255, 59, 59, 255)
    
    def make_ic(draw_fn, col=white, size=16):
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(im), col)
        return im.resize((size, size), Image.Resampling.LANCZOS)
        
    def draw_folder_outline(d, c):
        pts = [(10, 20), (26, 20), (32, 26), (62, 26), (62, 54), (10, 54), (10, 20)]
        d.line(pts, fill=c, width=5, joint="curve")

    def draw_display_outline(d, c):
        d.rounded_rectangle([(10, 14), (62, 44)], radius=5, outline=c, width=5)
        d.line([(36, 44), (36, 54)], fill=c, width=6)
        d.line([(24, 54), (48, 54)], fill=c, width=6)

    def draw_gamepad_outline(d, c):
        d.rounded_rectangle([(8, 16), (64, 50)], radius=14, outline=c, width=5)
        d.line([(20, 33), (28, 33)], fill=c, width=5)
        d.line([(24, 29), (24, 37)], fill=c, width=5)
        d.ellipse([(44, 25), (48, 29)], fill=c)
        d.ellipse([(52, 25), (56, 29)], fill=c)
        d.ellipse([(44, 37), (48, 41)], fill=c)
        d.ellipse([(52, 37), (56, 41)], fill=c)

    def draw_keyboard(d, c):
        d.rounded_rectangle([(8, 18), (56, 46)], radius=6, outline=c, width=5)
        for row_y in [25, 33]:
            for col_x in [15, 23, 31, 39, 47]:
                d.rectangle([(col_x, row_y), (col_x + 4, row_y + 4)], fill=c)
        d.rectangle([(23, 40), (39, 42)], fill=c)
        
    def draw_analog(d, c):
        d.arc([(12, 36), (52, 54)], start=0, end=180, fill=c, width=5)
        d.line([(32, 22), (32, 44)], fill=c, width=6)
        d.ellipse([(20, 10), (44, 26)], outline=c, width=5)
        d.ellipse([(27, 15), (37, 21)], fill=c)
        
    def draw_reset(d, c):
        d.arc([(12, 12), (52, 52)], start=40, end=320, fill=c, width=6)
        d.polygon([(46, 8), (46, 26), (34, 17)], fill=c)
        
    def draw_bolt(d, c):
        d.polygon([(36, 8), (20, 34), (32, 34), (26, 56), (46, 28), (34, 28)], fill=c)
        
    def draw_box(d, c):
        top, left, right, center = (32, 12), (14, 22), (50, 22), (32, 32)
        bot_left, bot_right, bottom = (14, 46), (50, 46), (32, 56)
        d.line([top, left, bot_left, bottom, bot_right, right, top], fill=c, width=5)
        d.line([left, center, right], fill=c, width=5)
        d.line([center, bottom], fill=c, width=5)
        
    def draw_doc(d, c):
        d.rounded_rectangle([(14, 10), (50, 54)], radius=4, outline=c, width=5)
        d.line([(22, 24), (42, 24)], fill=c, width=5)
        d.line([(22, 34), (42, 34)], fill=c, width=5)
        d.line([(22, 44), (34, 44)], fill=c, width=5)
        
    def draw_music(d, c):
        d.ellipse([(12, 38), (24, 50)], fill=c)
        d.ellipse([(36, 32), (48, 44)], fill=c)
        d.line([(22, 20), (22, 44)], fill=c, width=5)
        d.line([(46, 14), (46, 38)], fill=c, width=5)
        d.polygon([(20, 16), (48, 10), (48, 20), (20, 26)], fill=c)
        
    def draw_save(d, c):
        d.rounded_rectangle([(12, 12), (52, 52)], radius=5, outline=c, width=5)
        d.rectangle([(20, 12), (44, 26)], fill=c)
        d.rectangle([(18, 34), (46, 52)], fill=c)
        d.rectangle([(22, 38), (32, 48)], fill=(0, 0, 0, 255))
        
    def draw_users(d, c):
        d.ellipse([(10, 16), (22, 28)], fill=c)
        d.arc([(4, 30), (28, 52)], start=180, end=360, fill=c, width=5)
        d.ellipse([(42, 16), (54, 28)], fill=c)
        d.arc([(36, 30), (60, 52)], start=180, end=360, fill=c, width=5)
        d.ellipse([(24, 10), (40, 26)], fill=c)
        d.arc([(16, 28), (48, 56)], start=180, end=360, fill=c, width=6)
        
    def draw_update(d, c):
        d.arc([(12, 12), (52, 52)], start=40, end=320, fill=c, width=6)
        d.polygon([(48, 8), (48, 26), (36, 17)], fill=c)

    icons["folder_gold"] = make_ic(draw_folder_outline, red_primary, size=18)
    icons["display_gold"] = make_ic(draw_display_outline, red_primary, size=18)
    icons["gamepad_gold"] = make_ic(draw_gamepad_outline, red_primary, size=18)
    icons["gamepad"] = make_ic(draw_gamepad_outline, white, size=16)
    icons["keyboard"] = make_ic(draw_keyboard, white, size=16)
    icons["analog"] = make_ic(draw_analog, white, size=16)
    icons["reset"] = make_ic(draw_reset, white, size=16)
    icons["bolt"] = make_ic(draw_bolt, white, size=16)
    icons["box"] = make_ic(draw_box, white, size=16)
    icons["doc"] = make_ic(draw_doc, white, size=16)
    icons["music"] = make_ic(draw_music, white, size=16)
    icons["save"] = make_ic(draw_save, white, size=16)
    icons["users"] = make_ic(draw_users, white, size=16)
    icons["update"] = make_ic(draw_update, white, size=16)
    return icons

def render_pill_frame(w, h, is_primary=False, state="normal", t_hover=0.0, icon_img=None, clean_text="", is_hero=False):
    """
    Render standard primary / secondary button at 2x SSAA downsampled with LANCZOS.
    """
    sw, sh = w * 2, h * 2
    r_pill = sh // 2
    
    im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    if is_primary:
        r1 = int(214 + (240 - 214) * t_hover)
        g1 = int(35 + (50 - 35) * t_hover)
        b1 = int(35 + (50 - 35) * t_hover)
        r2 = 120
        g2 = 12
        b2 = 18
    else:
        r1 = int(14 + (24 - 14) * t_hover)
        g1 = int(22 + (38 - 22) * t_hover)
        b1 = int(44 + (75 - 44) * t_hover)
        r2 = int(8 + (14 - 8) * t_hover)
        g2 = int(13 + (22 - 13) * t_hover)
        b2 = int(28 + (46 - 28) * t_hover)
        
    grad = Image.new("RGBA", (sw, sh))
    d_g = ImageDraw.Draw(grad)
    for y in range(sh):
        t = y / max(sh - 1, 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        d_g.line([(0, y), (sw, y)], fill=(r, g, b, 235 if not is_primary else 255))
        
    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (sw - 1, sh - 1)], radius=r_pill, fill=255)
    im.paste(grad, (0, 0), mask)
    
    draw_s = ImageDraw.Draw(im)
    if is_primary:
        b_col = (255, int(117 + 43 * t_hover), int(117 + 43 * t_hover), 240)
        draw_s.rounded_rectangle([(1, 1), (sw - 2, sh - 2)], radius=r_pill, outline=b_col, width=2)
    else:
        br = int(59 + (99 - 59) * t_hover)
        bg_c = int(105 + (179 - 105) * t_hover)
        bb = int(152 + (237 - 152) * t_hover)
        draw_s.rounded_rectangle([(1, 1), (sw - 2, sh - 2)], radius=r_pill, outline=(br, bg_c, bb, 220), width=2)
        
    if state == "pressed":
        overlay = Image.new("RGBA", (sw, sh), (0, 0, 0, 60))
        im.alpha_composite(overlay)
        
    btn_1x = im.resize((w, h), Image.Resampling.LANCZOS)
    draw_1x = ImageDraw.Draw(btn_1x)
    
    font_size = int(max(9, h * 0.36))
    font = get_ui_font(font_size, bold=True)
    
    for s in ["🎮", "⌨", "🕹", "✦", "⚙", "📁", "■", " "]:
        if clean_text.startswith(s):
            clean_text = clean_text[len(s):].strip()
            
    bbox = draw_1x.textbbox((0, 0), clean_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    has_icon = (icon_img is not None)
    total_w = (16 + 8 + tw) if has_icon else tw
    start_x = (w - total_w) // 2
    
    if is_primary:
        fg = (255, 255, 255, 255)
        sh_col = (40, 5, 8, 220)
    else:
        fg = (255, 140, 140, 255) if t_hover > 0.5 else (255, 107, 107, 255)
        sh_col = (4, 8, 20, 240)
    
    if has_icon:
        ic = icon_img if icon_img.size == (16, 16) else icon_img.resize((16, 16), Image.Resampling.LANCZOS)
        tint = Image.new("RGBA", (16, 16), fg)
        tint.putalpha(ic.split()[3])
        btn_1x.paste(tint, (start_x, (h - 16) // 2), tint)
        text_x = start_x + 24
    else:
        text_x = (w - tw) // 2
        
    text_y = (h - th) // 2 - bbox[1]
    draw_1x.text((text_x + 1, text_y + 1), clean_text, font=font, fill=sh_col)
    draw_1x.text((text_x, text_y), clean_text, font=font, fill=fg)
    return btn_1x

class CanvasTextProxy:
    def __init__(self, canvas, item_id, shadow_id=None):
        self.canvas = canvas
        self.item_id = item_id
        self.shadow_id = shadow_id

    def config(self, **kwargs):
        if "text" in kwargs:
            txt = kwargs["text"]
            self.canvas.itemconfigure(self.item_id, text=txt)
            if self.shadow_id:
                self.canvas.itemconfigure(self.shadow_id, text=txt)
        if "fill" in kwargs or "fg" in kwargs:
            col = kwargs.get("fill", kwargs.get("fg"))
            self.canvas.itemconfigure(self.item_id, fill=col)

    configure = config

    def pulse_tick(self, phase):
        pass

class CanvasButton:
    def __init__(self, canvas, x, y, w, h, text="", command=None, is_primary=False, icon_img=None, is_hero=False, lang="id"):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text
        self.command = command
        self.is_primary = is_primary
        self.icon_img = icon_img
        self.is_hero = is_hero
        self.lang = lang
        self.state = "normal"
        self.hovered = False
        self.pressed = False
        self.step = 0
        self.target_step = 0
        self._animating = False
        
        self.tag = f"btn_{id(self)}"
        self._cache_frames()
        self.item_id = self.canvas.create_image(self.x, self.y, image=self.frames[0], tags=self.tag)
        
        self.canvas.tag_bind(self.tag, "<Enter>", self._on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self._on_leave)
        self.canvas.tag_bind(self.tag, "<ButtonPress-1>", self._on_press)
        self.canvas.tag_bind(self.tag, "<ButtonRelease-1>", self._on_release)

    def _cache_frames(self):
        self.frames = []
        if self.is_hero:
            asset_name = "btn_play_id.png" if self.lang == "id" else "btn_play_en.png"
            asset_path = ROOT / "assets" / asset_name
            if not asset_path.is_file():
                asset_path = ROOT / "assets" / "btn_play_en.png"
            if asset_path.is_file():
                raw_im = Image.open(asset_path)
                # Automatically lock aspect ratio to prevent squishing / gepeng
                natural_aspect = raw_im.width / float(raw_im.height)
                self.h = int(round(self.w / natural_aspect))
                btn_im = raw_im.resize((self.w, self.h), Image.Resampling.LANCZOS)
                pad = 14
                pw, ph = self.w + pad * 2, self.h + pad * 2
                for i in range(5):
                    t = i / 4.0
                    glow_im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                    d_g = ImageDraw.Draw(glow_im)
                    if t > 0:
                        a20 = int(70 * t)
                        d_g.rounded_rectangle([(pad - 2, pad - 2), (pad + self.w + 1, pad + self.h + 1)],
                                              radius=(self.h // 2) + 2, fill=(245, 158, 11, a20))
                        g20 = glow_im.filter(ImageFilter.GaussianBlur(12))
                        
                        glow_mid = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                        a12 = int(110 * t)
                        ImageDraw.Draw(glow_mid).rounded_rectangle([(pad, pad), (pad + self.w - 1, pad + self.h - 1)],
                                                                   radius=self.h // 2, fill=(255, 215, 0, a12))
                        g12 = glow_mid.filter(ImageFilter.GaussianBlur(7))
                        
                        glow_in = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                        a6 = int(140 * t)
                        ImageDraw.Draw(glow_in).rounded_rectangle([(pad + 2, pad + 2), (pad + self.w - 3, pad + self.h - 3)],
                                                                  radius=(self.h // 2) - 2, fill=(254, 240, 138, a6))
                        g6 = glow_in.filter(ImageFilter.GaussianBlur(3))
                        
                        comp = Image.alpha_composite(g20, g12)
                        comp = Image.alpha_composite(comp, g6)
                        
                        rim = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                        ImageDraw.Draw(rim).rounded_rectangle([(pad, pad), (pad + self.w - 1, pad + self.h - 1)],
                                                              radius=self.h // 2, outline=(255, 240, 170, int(170 * t)), width=2)
                        comp = Image.alpha_composite(comp, rim)
                    else:
                        comp = glow_im
                    comp.alpha_composite(btn_im, (pad, pad))
                    self.frames.append(ImageTk.PhotoImage(comp))
                
                # Pressed frame
                dark = Image.new("RGBA", (pw, ph), (0, 0, 0, 50))
                comp_p = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                comp_p.alpha_composite(btn_im, (pad, pad))
                comp_p.alpha_composite(dark)
                self.pressed_frame = ImageTk.PhotoImage(comp_p)
                return

        # Standard button rendering
        for i in range(5):
            t = i / 4.0
            im = render_pill_frame(self.w, self.h, self.is_primary, "normal", t, self.icon_img, self.text, self.is_hero)
            self.frames.append(ImageTk.PhotoImage(im))
        im_p = render_pill_frame(self.w, self.h, self.is_primary, "pressed", 0.0, self.icon_img, self.text, self.is_hero)
        self.pressed_frame = ImageTk.PhotoImage(im_p)

    def set_lang(self, lang):
        if self.lang != lang:
            self.lang = lang
            self._cache_frames()
            self.canvas.itemconfigure(self.item_id, image=self.frames[self.step])

    def set_geometry(self, x, y, w, h):
        if self.is_hero:
            h = int(round(w / 4.32524))
        need_recache = (w != self.w or h != self.h)
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        if need_recache:
            self._cache_frames()
        self.canvas.coords(self.item_id, self.x, self.y)
        self.canvas.itemconfigure(self.item_id, image=self.frames[self.step])

    def _on_enter(self, event):
        if self.state == "disabled":
            return
        self.hovered = True
        self.target_step = 4
        self.canvas.config(cursor="hand2")
        self.canvas.coords(self.item_id, self.x, self.y - 1)
        if not self._animating:
            self._animate()

    def _on_leave(self, event):
        if self.state == "disabled":
            return
        self.hovered = False
        self.pressed = False
        self.target_step = 0
        self.canvas.config(cursor="arrow")
        self.canvas.coords(self.item_id, self.x, self.y)
        if not self._animating:
            self._animate()

    def _on_press(self, event):
        if self.state == "disabled":
            return
        self.pressed = True
        self.canvas.coords(self.item_id, self.x, self.y + 1)
        self.canvas.itemconfigure(self.item_id, image=self.pressed_frame)

    def _on_release(self, event):
        if self.state == "disabled":
            return
        was_pressed = self.pressed
        self.pressed = False
        y_off = -1 if self.hovered else 0
        self.canvas.coords(self.item_id, self.x, self.y + y_off)
        self.canvas.itemconfigure(self.item_id, image=self.frames[self.step])
        if was_pressed and callable(self.command):
            self.command()

    def _animate(self):
        # 60 FPS transition (16ms)
        if self.step < self.target_step:
            self.step += 1
            self._animating = True
            if not self.pressed:
                self.canvas.itemconfigure(self.item_id, image=self.frames[self.step])
            self.canvas.after(16, self._animate)
        elif self.step > self.target_step:
            self.step -= 1
            self._animating = True
            if not self.pressed:
                self.canvas.itemconfigure(self.item_id, image=self.frames[self.step])
            self.canvas.after(16, self._animate)
        else:
            self._animating = False

    def render(self):
        self._cache_frames()
        self.canvas.itemconfigure(self.item_id, image=self.frames[self.step])

    def config(self, **kwargs):
        need_recache = False
        if "text" in kwargs:
            self.text = kwargs.pop("text")
            need_recache = True
        if "is_primary" in kwargs:
            self.is_primary = kwargs.pop("is_primary")
            need_recache = True
        if "state" in kwargs:
            self.state = kwargs.pop("state")
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if need_recache:
            self.render()

    configure = config

    def pulse_tick(self, phase):
        if not self.is_hero or self.hovered or self.pressed or self.state == "disabled":
            return
        import math
        val = 0.5 * (1.0 + math.sin(phase))
        target_step = 1 if val > 0.65 else 0
        if target_step != self.step:
            self.step = target_step
            self.canvas.itemconfigure(self.item_id, image=self.frames[self.step])

class CanvasRadioButton:
    def __init__(self, canvas, x, y, text, value, variable, sprites, callback=None):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.text = text
        self.value = value
        self.variable = variable
        self.sprites = sprites
        self.callback = callback
        
        self.tag = f"rb_{id(self)}"
        self.icon_id = self.canvas.create_image(self.x + 8, self.y, tags=self.tag)
        self.text_id = self.canvas.create_text(self.x + 26, self.y, text=self.text, anchor="w",
                                             font=("Segoe UI", 9), fill="#FF5252", tags=self.tag)
        
        self.canvas.tag_bind(self.tag, "<Button-1>", self._on_click)
        self.canvas.tag_bind(self.tag, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(self.tag, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.update_state()

    def set_position(self, x, y):
        self.x = x
        self.y = y
        self.canvas.coords(self.icon_id, self.x + 8, self.y)
        self.canvas.coords(self.text_id, self.x + 26, self.y)

    def _on_click(self, event):
        self.variable.set(self.value)
        if callable(self.callback):
            self.callback()

    def update_state(self):
        is_selected = (self.variable.get() == self.value)
        spr = self.sprites["radio_on_tk"] if is_selected else self.sprites["radio_off_tk"]
        col = "#FF3B3B" if is_selected else "#FF5252"
        self.canvas.itemconfigure(self.icon_id, image=spr)
        self.canvas.itemconfigure(self.text_id, fill=col)

    def config(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs.pop("text")
            self.canvas.itemconfigure(self.text_id, text=self.text)
        self.update_state()
    configure = config

    def pulse_tick(self, phase):
        pass

class CanvasCheckbox:
    def __init__(self, canvas, x, y, text, variable, sprites, command=None):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.text = text
        self.variable = variable
        self.sprites = sprites
        self.command = command
        
        self.tag = f"chk_{id(self)}"
        self.icon_id = self.canvas.create_image(self.x + 8, self.y, tags=self.tag)
        self.text_id = self.canvas.create_text(self.x + 26, self.y, text=self.text, anchor="w",
                                             font=("Segoe UI", 9), fill="#FF5252", tags=self.tag)
        
        self.canvas.tag_bind(self.tag, "<Button-1>", self._on_click)
        self.canvas.tag_bind(self.tag, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(self.tag, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.update_state()

    def set_position(self, x, y):
        self.x = x
        self.y = y
        self.canvas.coords(self.icon_id, self.x + 8, self.y)
        self.canvas.coords(self.text_id, self.x + 26, self.y)

    def _on_click(self, event):
        self.variable.set(not self.variable.get())
        self.update_state()
        if callable(self.command):
            self.command()

    def update_state(self):
        is_checked = bool(self.variable.get())
        spr = self.sprites["check_on_tk"] if is_checked else self.sprites["check_off_tk"]
        col = "#FF3B3B" if is_checked else "#FF5252"
        self.canvas.itemconfigure(self.icon_id, image=spr)
        self.canvas.itemconfigure(self.text_id, fill=col)

    def config(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs.pop("text")
            self.canvas.itemconfigure(self.text_id, text=self.text)
        self.update_state()
    configure = config

    def pulse_tick(self, phase):
        pass

class StatusPillCanvas:
    def __init__(self, canvas, x, y, state="ready", text="Ready to play"):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.state = state
        self.text = text
        self._render()

    def _render(self):
        fnt = get_ui_font(10, bold=True)
        tmp_im = Image.new("RGBA", (1, 1))
        d_tmp = ImageDraw.Draw(tmp_im)
        t_bbox = d_tmp.textbbox((0, 0), self.text, font=fnt)
        tw = t_bbox[2] - t_bbox[0]
        th = t_bbox[3] - t_bbox[1]
        w = max(142, tw + 46)
        h = 28
        
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        
        if self.state == "ready":
            fill_c = (10, 42, 28, 210)
            border_c = (34, 197, 94, 240)
            dot_c = (74, 222, 128, 255)
            txt_c = (134, 239, 172, 255)
        elif self.state == "not_ready":
            fill_c = (55, 10, 16, 225)
            border_c = (239, 68, 68, 240)
            dot_c = (248, 113, 113, 255)
            txt_c = (252, 165, 165, 255)
        elif self.state == "running":
            fill_c = (12, 30, 55, 210)
            border_c = (59, 130, 246, 240)
            dot_c = (96, 165, 250, 255)
            txt_c = (191, 219, 254, 255)
        else: # starting
            fill_c = (45, 30, 10, 210)
            border_c = (234, 179, 8, 240)
            dot_c = (250, 204, 21, 255)
            txt_c = (254, 240, 138, 255)
            
        d.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=14, fill=fill_c, outline=border_c, width=1)
        d.ellipse([(12, 11), (18, 17)], fill=dot_c)
        ty = (h - th) // 2 - t_bbox[1]
        d.text((28, ty), self.text, font=fnt, fill=txt_c)
        
        self.photo = ImageTk.PhotoImage(im)
        if hasattr(self, "item_id"):
            self.canvas.itemconfigure(self.item_id, image=self.photo)
        else:
            self.item_id = self.canvas.create_image(self.x, self.y, image=self.photo, anchor="w")

    def set_position(self, x, y):
        self.x = x
        self.y = y
        if hasattr(self, "item_id"):
            self.canvas.coords(self.item_id, self.x, self.y)

    def set_status(self, state, text):
        if self.state != state or self.text != text:
            self.state = state
            self.text = text
            self._render()

    def pulse_tick(self, phase):
        pass

class LanguageToggleCanvas:
    def __init__(self, canvas, x, y, current_lang="id", on_change=None):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.lang = current_lang
        self.on_change = on_change
        self._render()

    def _render(self):
        w, h = 84, 28
        sw, sh = w * 2, h * 2
        im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([(0, 0), (sw - 1, sh - 1)], radius=16,
                            fill=(8, 15, 32, 200), outline=(72, 138, 210, 115), width=2)
                            
        pill_x = 4 if self.lang == "en" else 84
        pill_w = 80
        pill_h = 48
        pill_im = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
        d_p = ImageDraw.Draw(pill_im)
        for py in range(pill_h):
            t = py / float(max(pill_h - 1, 1))
            r = int(225 + (159 - 225) * t)
            g = int(29 + (18 - 29) * t)
            b = int(72 + (57 - 72) * t)
            d_p.line([(0, py), (pill_w, py)], fill=(r, g, b, 255))
        d_p.line([(6, 1), (pill_w - 7, 1)], fill=(253, 164, 175, 180), width=2)
        
        pill_mask = Image.new("L", (pill_w, pill_h), 0)
        ImageDraw.Draw(pill_mask).rounded_rectangle([(0, 0), (pill_w - 1, pill_h - 1)], radius=12, fill=255)
        im.paste(pill_im, (pill_x, 4), pill_mask)
        
        fnt = get_ui_font(22, bold=True)
        en_col = (255, 255, 255, 255) if self.lang == "en" else (148, 163, 184, 255)
        id_col = (255, 255, 255, 255) if self.lang == "id" else (148, 163, 184, 255)
        
        for txt, cx, col in [("EN", 44, en_col), ("ID", 124, id_col)]:
            bbox = d.textbbox((0, 0), txt, font=fnt)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = cx - tw // 2
            ty = (sh // 2) - th // 2 - bbox[1]
            d.text((tx, ty), txt, font=fnt, fill=col)
            
        final_1x = im.resize((w, h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(final_1x)
        if hasattr(self, "item_id"):
            self.canvas.itemconfigure(self.item_id, image=self.photo)
        else:
            self.item_id = self.canvas.create_image(self.x, self.y, image=self.photo, anchor="e")
            self.canvas.tag_bind(self.item_id, "<Button-1>", self._on_click)

    def set_position(self, x, y):
        self.x = x
        self.y = y
        self.canvas.coords(self.item_id, self.x, self.y)

    def _on_click(self, event):
        rx = event.x - (self.x - 84)
        new_lang = "en" if rx < 42 else "id"
        if new_lang != self.lang:
            self.lang = new_lang
            self._render()
            if callable(self.on_change):
                self.on_change(new_lang)

    def set_language(self, lang):
        self.lang = lang
        self._render()

class Launcher(tk.Tk):

    def __init__(self, play_now=False):

        log_debug("Launcher __init__ started")

        super().__init__()

        try:

            self.cfg = load_config()

            log_debug(f"Loaded config from {CONFIG}")

        except Exception as e:

            log_debug(f"Error loading config: {e}\n{traceback.format_exc()}")

            self.cfg = dict(DEFAULTS)



        self.locales = load_locales()

        self.lang = self.cfg.get("language", "id")

        self.proc = None

        self.busy = False

        self.pending = None

        self.play_now = play_now

        self.update_info = None

        self.update_btn = None

        self._ui_queue = queue.Queue()



        self.title(f"{self.t('app_title')} - {BRAND} by {AUTHOR}")

        self.configure(bg=ROOT_BG)

        self.geometry("1120x760")

        self.minsize(1040, 680)



        # Explicit Windows AppUserModelID for Taskbar icon grouping

        try:

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SengokuBasara4.Launcher.Timotius.1.0")

        except Exception:

            pass



        icon_path = get_resource_path("basara4.ico")
        self._icon_path = str(icon_path) if (icon_path and icon_path.is_file()) else None
        self._icon_photo = None
        self._icon_photos = []
        if self._icon_path:
            try:
                self.iconbitmap(self._icon_path)
                if Image and ImageTk:
                    raw_ico = Image.open(self._icon_path)
                    for sz in [16, 24, 32, 48, 64, 128, 256]:
                        im_sz = raw_ico.resize((sz, sz), Image.Resampling.LANCZOS)
                        self._icon_photos.append(ImageTk.PhotoImage(im_sz))
                    self._icon_photo = self._icon_photos[4]
                    self.iconphoto(True, *self._icon_photos)
                log_debug(f"Yukimura emblem icon loaded: {self._icon_path}")
            except Exception as e:
                log_debug(f"Could not load iconbitmap: {e}")



        try:

            self._style()

            log_debug("Styles initialized")

        except Exception as e:

            log_debug(f"Error initializing styles: {e}\n{traceback.format_exc()}")



        try:

            self._art()

            log_debug("Artwork initialized")

        except Exception as e:

            log_debug(f"Error initializing artwork: {e}\n{traceback.format_exc()}")



        try:

            self._build()

            log_debug("Flipped dual-column UI layout built successfully")

        except Exception as e:

            log_debug(f"Error building UI layout: {e}\n{traceback.format_exc()}")



        try:

            self._load_ini_into_ui()

            log_debug("INI loaded into UI successfully")

        except Exception as e:

            log_debug(f"Error loading INI into UI: {e}\n{traceback.format_exc()}")



        try:

            self._refresh_image_label()

        except Exception as e:

            log_debug(f"Error refreshing image label: {e}\n{traceback.format_exc()}")



        try:

            apply_dark_titlebar(self)

            self.deiconify()

            self.update_idletasks()

            self.lift()

            if hasattr(self, "_icon_path") and self._icon_path:

                apply_window_native_icon(self, self._icon_path)

            log_debug("Dark titlebar applied & window mapped")

        except Exception as e:

            log_debug(f"Error finalizing window setup: {e}\n{traceback.format_exc()}")



        self.bind("<Configure>", self._on_configure)

        self.protocol("WM_DELETE_WINDOW", self._close)

        self.after(50, self._process_ui_queue)

        self.after(500, self._poll)



        if play_now:

            self.iconify()

            self.after(300, self.on_play)

        else:

            self.after(700, self._check_wav_leftovers)

            self.after(1200, lambda: threading.Thread(target=self._check_update_thread, daemon=True).start())



    def dispatch_ui(self, func, *args, **kwargs):

        """Thread-safe dispatch of a function call to the Tkinter UI main thread."""

        self._ui_queue.put((func, args, kwargs))



    def _process_ui_queue(self):

        """Process pending callbacks on the main thread."""

        try:

            while not self._ui_queue.empty():

                try:

                    callback, args, kwargs = self._ui_queue.get_nowait()

                    callback(*args, **kwargs)

                except queue.Empty:

                    break

        except Exception as e:

            log_debug(f"UI Queue processing error: {e}")

        self.after(50, self._process_ui_queue)



    def t(self, key, **kwargs):

        """Retrieve localized string with format argument interpolation."""

        table = self.locales.get(self.lang, {})

        text = table.get(key, self.locales.get("id", {}).get(key, self.locales.get("en", {}).get(key, key)))

        if kwargs:

            try:

                return text.format(**kwargs)

            except Exception:

                return text

        return text



    def set_language(self, lang):
        self.lang = lang
        self.cfg["language"] = lang
        try:
            save_config(self.cfg)
        except Exception:
            pass
        log_debug(f"Language switched to: {lang}")

        self.title(f"{self.t('app_title')} - {BRAND} by {AUTHOR}")
        if hasattr(self, "lang_toggle"):
            self.lang_toggle.set_language(lang)
        if hasattr(self, "header_title"):
            self.header_title.config(text=f"{self.t('app_subtitle')} · {self.t('app_title').upper()}")
        if hasattr(self, "play"):
            self.play.set_lang(lang)
            self.play.config(text=self.t("play_btn"))
        if hasattr(self, "stop"):
            self.stop.config(text=self.t("stop_btn"))
        if hasattr(self, "credits_btn"):
            self.credits_btn.config(text=self.t("credits_btn"))
        if hasattr(self, "check_update_btn"):
            self.check_update_btn.config(text="Cek Update" if lang == "id" else "Check Update")
        if hasattr(self, "wm_sub"):
            self.wm_sub.config(text=f"{self.t('by_author')} - v{VERSION}")
            
        # Section titles
        if hasattr(self, "card_game_title"):
            self.card_game_title.config(text=self.t("section_game"))
        if hasattr(self, "game_folder_lbl"):
            self.game_folder_lbl.config(text=self.t("game_folder"))
        if hasattr(self, "browse_btn"):
            self.browse_btn.config(text=self.t("browse_btn"))
        if hasattr(self, "card_display_title"):
            self.card_display_title.config(text=self.t("section_display"))
        if hasattr(self, "card_ctrl_title"):
            self.card_ctrl_title.config(text=self.t("section_controller"))
        if hasattr(self, "lbl_input_mode"):
            self.lbl_input_mode.config(text=self.t("input_mode"))
        if hasattr(self, "btn_mode_pad"):
            self.btn_mode_pad.config(text=self.t("input_mode_controller"))
        if hasattr(self, "btn_mode_kbm"):
            self.btn_mode_kbm.config(text=self.t("input_mode_kbm"))
        if hasattr(self, "lbl_ctrl_config"):
            self.lbl_ctrl_config.config(text=f"✦ {self.t('section_controller_config')}")
        if hasattr(self, "lbl_utils"):
            self.lbl_utils.config(text=f"⚙ {self.t('section_utilities')}")
        if hasattr(self, "btn_kbm"):
            self.btn_kbm.config(text=self.t("kbm_controls_btn"))
        if hasattr(self, "btn_control_gamepad"):
            self.btn_control_gamepad.config(text=self.t("control_gamepad_btn"))
        if hasattr(self, "btn_analog_sens"):
            self.btn_analog_sens.config(text=self.t("analog_sens_btn"))
        if hasattr(self, "btn_reset_map"):
            self.btn_reset_map.config(text=self.t("reset_map"))
        if hasattr(self, "btn_cheats"):
            self.btn_cheats.config(text=self.t("cheats_btn"))
        if hasattr(self, "btn_dlc"):
            self.btn_dlc.config(text=self.t("dlc_btn"))
        if hasattr(self, "btn_open_log"):
            self.btn_open_log.config(text=self.t("open_log"))
        if hasattr(self, "btn_open_audio_log"):
            self.btn_open_audio_log.config(text=self.t("open_audio_log"))
        if hasattr(self, "btn_open_saves"):
            self.btn_open_saves.config(text=self.t("open_saves"))
        if hasattr(self, "lbl_gpu"):
            self.lbl_gpu.config(text=self.t("gpu_select"))
        if hasattr(self, "lbl_fps"):
            self.lbl_fps.config(text=self.t("frame_limit"))
        if hasattr(self, "lbl_aniso"):
            self.lbl_aniso.config(text=self.t("anisotropic"))
        if hasattr(self, "lbl_win_size"):
            self.lbl_win_size.config(text=self.t("window_size"))
        if hasattr(self, "lbl_upscale"):
            self.lbl_upscale.config(text=self.t("upscaling"))
        if hasattr(self, "chk_vsync"):
            self.chk_vsync.config(text=self.t("vsync"))
        if hasattr(self, "chk_rcas"):
            self.chk_rcas.config(text=self.t("rcas"))
        if hasattr(self, "chk_audio"):
            self.chk_audio.config(text=self.t("audio_log"))
        if hasattr(self, "chk_wav"):
            self.chk_wav.config(text=self.t("wav_capture"))
        if hasattr(self, "res_hint"):
            self.res_hint.config(text=self.t("res_hint"))
        if hasattr(self, "menu_hint"):
            self.menu_hint.config(text=self.t("ingame_menu"))
            
        if hasattr(self, "status"):
            self.status.config(text=self.t("pad_prompt"))
        self._pad_text()
        
        w = max(self.winfo_width(), 1040)
        h = max(self.winfo_height(), 680)
        self._reposition_elements(w, h)
        self._refresh_image_label()
    # ---- look & styles ----

    def _create_control_sprites(self):
        """Generate custom 16x16 PIL sprites for Radio Buttons, Checkboxes, and Combobox Chevrons."""
        if Image is None or ImageDraw is None:
            return

        # 1. Radiobutton sprites (16x16 drawn at 64x64 with 4x SSAA)
        # A. Unchecked (circle outline: 1.5px #4A6FA5, fill #070E20)
        r_un = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d_run = ImageDraw.Draw(r_un)
        d_run.ellipse([(6, 6), (58, 58)], fill=(7, 14, 32, 255), outline=(74, 111, 165, 255), width=6)
        self._radio_unsel = ImageTk.PhotoImage(r_un.resize((16, 16), Image.Resampling.LANCZOS))

        # B. Selected (Exclusive Fullscreen: glowing gold ring 3.5px #E5C168, #070E20 center dot)
        r_sel = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d_rsel = ImageDraw.Draw(r_sel)
        d_rsel.ellipse([(4, 4), (60, 60)], outline=(229, 193, 104, 120), width=8)
        d_rsel.ellipse([(6, 6), (58, 58)], fill=(7, 14, 32, 255), outline=(229, 193, 104, 255), width=12)
        d_rsel.ellipse([(20, 20), (44, 44)], fill=(229, 193, 104, 255))
        self._radio_sel = ImageTk.PhotoImage(r_sel.resize((16, 16), Image.Resampling.LANCZOS))

        # 2. Checkbutton sprites (16x16 drawn at 64x64 with 4x SSAA)
        # A. Unchecked (rounded square radius=4, fill (8,16,36,220), border 1.5px #3B6998)
        c_un = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d_cun = ImageDraw.Draw(c_un)
        d_cun.rounded_rectangle([(6, 6), (58, 58)], radius=16, fill=(8, 16, 36, 220), outline=(59, 105, 152, 255), width=6)
        self._check_unsel = ImageTk.PhotoImage(c_un.resize((16, 16), Image.Resampling.LANCZOS))

        # B. Checked (solid Samurai Gold #E5C168 with dark navy checkmark ✓)
        c_sel = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d_csel = ImageDraw.Draw(c_sel)
        d_csel.rounded_rectangle([(6, 6), (58, 58)], radius=16, fill=(229, 193, 104, 255), outline=(255, 225, 140, 255), width=4)
        pts = [(16, 32), (26, 44), (48, 18)]
        d_csel.line(pts, fill=(7, 14, 32, 255), width=8, joint="curve")
        self._check_sel = ImageTk.PhotoImage(c_sel.resize((16, 16), Image.Resampling.LANCZOS))

        # 3. Combobox chevron sprite (Samurai Gold downward chevron in #D6A63A)
        arr = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d_arr = ImageDraw.Draw(arr)
        d_arr.polygon([(16, 24), (48, 24), (32, 44)], fill=(214, 166, 58, 255))
        self._combo_arrow = ImageTk.PhotoImage(arr.resize((16, 16), Image.Resampling.LANCZOS))

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        self._create_control_sprites()
        try:
            if hasattr(self, "_radio_unsel") and hasattr(self, "_radio_sel"):
                s.element_create("Custom.Radiobutton.indicator", "image", self._radio_unsel, ("selected", self._radio_sel))
                s.layout("TRadiobutton", [("Radiobutton.padding", {"children": [("Custom.Radiobutton.indicator", {"side": "left"}), ("Radiobutton.label", {"side": "left", "expand": 1})], "sticky": "nswe"})])
            if hasattr(self, "_check_unsel") and hasattr(self, "_check_sel"):
                s.element_create("Custom.Checkbutton.indicator", "image", self._check_unsel, ("selected", self._check_sel))
                s.layout("TCheckbutton", [("Checkbutton.padding", {"children": [("Custom.Checkbutton.indicator", {"side": "left"}), ("Checkbutton.label", {"side": "left", "expand": 1})], "sticky": "nswe"})])
            if hasattr(self, "_combo_arrow"):
                s.element_create("Custom.Combobox.arrow", "image", self._combo_arrow)
                s.layout("TCombobox", [("Combobox.field", {"children": [("Custom.Combobox.arrow", {"side": "right", "sticky": ""}), ("Combobox.padding", {"children": [("Combobox.textarea", {"sticky": "nswe"})], "sticky": "nswe"})], "sticky": "nswe"})])
        except Exception as e:
            log_debug(f"Custom element create note: {e}")

        s.configure(".", background=CARD_BG, foreground=FG, fieldbackground=CARD_BG,
                    bordercolor=CARD_BORDER, lightcolor=CARD_BG, darkcolor=CARD_BG,
                    font=("Segoe UI", 9))
        s.configure("TFrame", background=ROOT_BG)
        s.configure("Card.TFrame", background=CARD_BG)
        s.configure("TLabel", background=ROOT_BG, foreground=FG)
        s.configure("Card.TLabel", background=CARD_BG, foreground=FG)
        s.configure("Muted.TLabel", background=CARD_BG, foreground=MUTED, font=("Segoe UI", 8))
        s.configure("Head.TLabel", background=ROOT_BG, foreground=RED_PRIMARY, font=("Segoe UI Bold", 11))
        s.configure("CardHead.TLabel", background=CARD_BG, foreground=RED_PRIMARY, font=("Segoe UI Bold", 10))

        s.configure("TRadiobutton", background=CARD_BG, foreground=FG, font=("Segoe UI", 9))
        s.map("TRadiobutton",
              background=[("active", CARD_BG)],
              foreground=[("selected", RED_PRIMARY), ("active", "#FFFFFF")])

        s.configure("TCheckbutton", background=CARD_BG, foreground=FG, font=("Segoe UI", 9))
        s.map("TCheckbutton",
              background=[("active", CARD_BG)],
              foreground=[("selected", RED_PRIMARY), ("active", "#FFFFFF")])

        # Active styles for Samurai Gold on checked/selected
        s.configure("Active.TRadiobutton", background=CARD_BG, foreground="#E5C168", font=("Segoe UI Semibold", 9))
        s.configure("Active.TCheckbutton", background=CARD_BG, foreground="#E5C168", font=("Segoe UI Semibold", 9))
        s.configure("Hover.TCombobox", bordercolor="#60A5FA", lightcolor="#60A5FA", darkcolor="#60A5FA")

        s.configure("TCombobox", background="#060B1A", fieldbackground="#060B1A",
                    foreground=FG, bordercolor="#2563EB", lightcolor="#2563EB", darkcolor="#2563EB",
                    padding=4)
        s.map("TCombobox",
              fieldbackground=[("readonly", "#060B1A")],
              foreground=[("readonly", FG)],
              selectbackground=[("readonly", RED_PRIMARY)],
              selectforeground=[("readonly", "#FFFFFF")])
        self.option_add("*TCombobox*Listbox.background", "#060B1A")
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", RED_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))

        s.configure("TEntry", fieldbackground="#050813", foreground=FG, bordercolor=CARD_BORDER,
                    lightcolor=CARD_BORDER, darkcolor=CARD_BORDER, padding=5)

        s.configure("Vertical.TScrollbar", background="#1A2840", troughcolor="#0E1422",
                    bordercolor=CARD_BORDER, arrowcolor=RED_PRIMARY)

        # Basara Custom Dark Treeview & Vertical Scrollbar
        s.configure("Basara.Treeview",
                    background="#070E20",
                    foreground="#FF5E5E",
                    fieldbackground="#070E20",
                    rowheight=28,
                    bordercolor="#2563EB",
                    font=("Segoe UI", 9))
        s.map("Basara.Treeview",
              background=[("selected", "#1E3A6E")],
              foreground=[("selected", "#FFFFFF")])
        s.configure("Basara.Treeview.Heading",
                    background="#0A142F",
                    foreground="#FF4242",
                    relief="flat",
                    font=("Segoe UI Bold", 9))
        s.map("Basara.Treeview.Heading",
              background=[("active", "#15244E")],
              foreground=[("active", "#FFFFFF")])
        s.configure("Basara.Vertical.TScrollbar",
                    troughcolor="#050A18",
                    background="#1E3A6E",
                    bordercolor="#050A18",
                    arrowcolor="#3898FF")
        s.map("Basara.Vertical.TScrollbar",
              background=[("active", "#3898FF"), ("pressed", "#2563EB")])

    def _find_launcher_bg(self):
        """Locate launcher background in assets, project root, launcher dir, or sys._MEIPASS."""
        candidates = [
            "launcherbackground.jpeg", "launcherbackground.jpg", "launcherbackground.png",
            "Launcherbg.png", "launcherbg.png", "Launcherbg.jpg", "launcherbg.jpg",
            "Launcherbg.webp", "launcherbg.webp"
        ]
        search_dirs = [
            ROOT / "assets",
            ROOT / "launcher" / "assets",
            ROOT,
            ROOT / "launcher",
            Path(sys._MEIPASS) / "assets" if hasattr(sys, "_MEIPASS") else None,
            Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else None,
            Path(__file__).resolve().parent / "assets",
            Path(__file__).resolve().parent
        ]
        for d in search_dirs:
            if d and d.is_dir():
                for name in candidates:
                    p = d / name
                    if p.is_file():
                        return p
        return None

    def _art(self):
        self.cover = self.bg_raw = self.bg_img = self.logo_raw = None
        if Image is None:
            return

        # Load transparent Anniversary Edition logo
        logo_path = find_asset_file("logo_basara.jpeg", "logo_basara.png", "logo_basara.jpg")
        if logo_path:
            try:
                self.logo_raw = load_asset_transparent(logo_path, (260, 140))
                if self.logo_raw:
                    log_debug(f"Loaded transparent Basara logo from {logo_path}: {self.logo_raw.size}")
            except Exception as e:
                log_debug(f"Could not load logo_basara: {e}")

        bg_path = self._find_launcher_bg()
        if bg_path and bg_path.is_file():
            try:
                self.bg_raw = Image.open(bg_path).convert("RGBA")
                log_debug(f"Loaded custom launcher background: {bg_path}")
            except Exception as e:
                log_debug(f"Could not load launcherbg from {bg_path}: {e}")

        if self.bg_raw is None and self.cfg.get("game"):
            try:
                pic_p = Path(self.cfg["game"]) / "sce_sys" / "pic1.png"
                if pic_p.is_file():
                    self.bg_raw = Image.open(pic_p).convert("RGBA")
            except Exception as e:
                log_debug(f"Could not load pic1.png: {e}")

        # Smooth Combobox border transition on hover
        if hasattr(self, "gpu_combo"):
            for cb in [self.gpu_combo, self.fps_combo, self.aniso_combo, self.res_combo, self.up_combo]:
                cb.bind("<Enter>", lambda e, c=cb: c.configure(style="Hover.TCombobox"))
                cb.bind("<Leave>", lambda e, c=cb: c.configure(style="TCombobox"))

        # Start 60 FPS Ambient Breathing Engine (50ms tick)
        self._breathe_phase = 0.0
        self._start_ambient_breathing()

        if self.bg_raw is not None and hasattr(self, "main_canvas"):
            self._update_bg(1100, 670)

    def _render_card_bg(self, w, h, card_attr):
        """Render frosted glass card texture with rounded corners (r=14), midnight-navy tint, outer neon glow (#1E6FD9), and specular highlight (#3B82F6)."""
        w = max(int(w), 60)
        h = max(int(h), 30)
        card = getattr(self, card_attr, None)
        cx, cy = 18, 66
        if card:
            try:
                cx = card.winfo_rootx() - self.winfo_rootx()
                cy = card.winfo_rooty() - self.winfo_rooty()
            except Exception:
                pass

        if not hasattr(self, "_master_bg_pil") or self._master_bg_pil is None:
            im = Image.new("RGBA", (w, h), (7, 14, 32, 235))
            draw = ImageDraw.Draw(im)
            draw.rounded_rectangle([(3, 3), (w - 4, h - 4)], radius=14, outline=(59, 130, 246, 220), width=2)
            return ImageTk.PhotoImage(im)

        cx = max(0, min(cx, self._master_bg_pil.width - w))
        cy = max(0, min(cy, self._master_bg_pil.height - h))

        slice_im = self._master_bg_pil.crop((cx, cy, cx + w, cy + h)).convert("RGBA")
        blurred = slice_im.filter(ImageFilter.GaussianBlur(3))

        # Translucent midnight navy rounded fill (7, 14, 32, 215)
        fill_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d_f = ImageDraw.Draw(fill_layer)
        d_f.rounded_rectangle([(3, 3), (w - 4, h - 4)], radius=14, fill=(7, 14, 32, 215))
        blurred.alpha_composite(fill_layer)

        # Soft outer electric-blue glow (#1E6FD9, alpha 110, blurred with radius=5)
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d_g = ImageDraw.Draw(glow)
        d_g.rounded_rectangle([(2, 2), (w - 3, h - 3)], radius=14, outline=(30, 111, 217, 110), width=6)
        glow = glow.filter(ImageFilter.GaussianBlur(5))
        blurred.alpha_composite(glow)

        # Crisp 1.5px rounded border in #3B82F6 with specular highlight
        draw = ImageDraw.Draw(blurred)
        draw.rounded_rectangle([(3, 3), (w - 4, h - 4)], radius=14, outline=(59, 130, 246, 220), width=2)
        draw.line([(3 + 14, 3), (w - 4 - 14, 3)], fill=(124, 196, 255, 180), width=1)

        # Outside radius 14, mask out with original slice
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=17, fill=255)
        final = slice_im.copy()
        final.paste(blurred, (0, 0), mask)

        return ImageTk.PhotoImage(final.convert("RGB"))

    def _update_card_bgs(self):
        """No-op: Glass cards are seamlessly baked into self._composited_bg with unbroken 1.5px glowing borders."""
        pass

    def _reposition_elements(self, w, h):
        """Precision responsive scaling maintaining 61.2% Left / 38.8% Right split and proportional Y spacing."""
        if not hasattr(self, "main_canvas"):
            return
        left_card_x1 = int(w * 0.015)
        left_card_x2 = int(w * 0.612)
        card_inner_w = (left_card_x2 - left_card_x1) - 36
        right_cx = int(w * 0.806)
        right_col_w = w - left_card_x2
        btn_play_w = max(260, min(310, int(right_col_w * 0.72)))
        btn_play_h = int(round(btn_play_w / 4.32524))
        sub_w = (btn_play_w - 10) // 2

        card1_y1 = 62
        card2_y1 = int(h * 0.21)
        card3_y1 = int(h * 0.56)
        card3_y2 = h - 14
        H3 = card3_y2 - card3_y1

        # Header Title and Status Pill (Dynamically spaced to prevent overlap)
        title_x = left_card_x1 + 6
        title_y = 28
        title_text = f"{self.t('app_subtitle')} · {self.t('app_title').upper()}"
        if hasattr(self, "_hdr_title_id"):
            self.main_canvas.coords(self._hdr_title_id, title_x, title_y)
            if hasattr(self, "_hdr_title_shadow_id"):
                self.main_canvas.coords(self._hdr_title_shadow_id, title_x + 1, title_y + 1)
            
            title_w = measure_text_width(title_text, 15, bold=True)
            badge_x1 = max(int(title_x + title_w + 22), 528)
            if hasattr(self, "header_status_pill"):
                self.header_status_pill.set_position(badge_x1, title_y)

        if hasattr(self, "lang_toggle") and hasattr(self.lang_toggle, "item_id"):
            self.lang_toggle.set_position(w - 18, title_y)

        # Card 1 (GAME LOCATION)
        browse_w = 104
        browse_h = 28
        browse_x = left_card_x2 - 18 - browse_w
        
        lbl_w = measure_text_width(self.t("game_folder"), 9, bold=False)
        entry_x = max(left_card_x1 + 122, left_card_x1 + 20 + lbl_w + 16)
        entry_w = browse_x - 12 - entry_x

        if hasattr(self, "_ic_fld_id"):
            self.main_canvas.coords(self._ic_fld_id, left_card_x1 + 22, 80)
            self.main_canvas.coords(self._card_game_title_id, left_card_x1 + 38, 80)
            self.main_canvas.coords(self._game_folder_lbl_id, left_card_x1 + 18, 108)

        if hasattr(self, "_game_entry_win"):
            self.main_canvas.coords(self._game_entry_win, entry_x, 94)
            self.main_canvas.itemconfigure(self._game_entry_win, width=entry_w, height=browse_h)

        if hasattr(self, "browse_btn") and hasattr(self.browse_btn, "item_id"):
            self.browse_btn.set_geometry(browse_x + browse_w // 2, 108, browse_w, browse_h)

        if hasattr(self, "_image_label_id"):
            self.main_canvas.coords(self._image_label_id, entry_x, 131)

        # Floating Crimson Warning Banner (Below Card 1 status text)
        if hasattr(self, "_toast_item_id"):
            toast_w = max(380, browse_x + browse_w - entry_x)
            self._toast_photo = self._render_floating_banner(toast_w)
            self.main_canvas.itemconfigure(self._toast_item_id, image=self._toast_photo)
            self.main_canvas.coords(self._toast_item_id, entry_x, 153)

        # Card 2 (DISPLAY & GRAPHICS)
        if hasattr(self, "_ic_disp_id"):
            self.main_canvas.coords(self._ic_disp_id, left_card_x1 + 22, card2_y1 + 18)
            self.main_canvas.coords(self._card_display_title_id, left_card_x1 + 38, card2_y1 + 18)

        # Proportional radio button placement
        card_inner_w = (left_card_x2 - left_card_x1) - 40
        rb_offsets = [0, int(card_inner_w * 0.28), int(card_inner_w * 0.64)]
        if hasattr(self, "radio_buttons"):
            for idx, (rb, key) in enumerate(self.radio_buttons):
                txt = self.t(f"mode_{key}")
                rb.config(text=txt)
                rb.set_position(left_card_x1 + 18 + rb_offsets[idx], card2_y1 + 42)

        if hasattr(self, "_lbl_gpu_id"):
            self.main_canvas.coords(self._lbl_gpu_id, left_card_x1 + 18, card2_y1 + 76)
            self.main_canvas.coords(self._gpu_combo_win, left_card_x1 + 160, card2_y1 + 63)
            self.main_canvas.itemconfigure(self._gpu_combo_win, width=(left_card_x2 - 18) - (left_card_x1 + 160))

        col1_w = int(card_inner_w * 0.52)
        col2_start = left_card_x1 + 18 + int(card_inner_w * 0.55)

        if hasattr(self, "_lbl_fps_id"):
            self.main_canvas.coords(self._lbl_fps_id, left_card_x1 + 18, card2_y1 + 108)
            self.main_canvas.coords(self._fps_combo_win, left_card_x1 + 105, card2_y1 + 95)
            self.main_canvas.itemconfigure(self._fps_combo_win, width=col1_w - 95)

            self.main_canvas.coords(self._lbl_aniso_id, col2_start, card2_y1 + 108)
            self.main_canvas.coords(self._aniso_combo_win, col2_start + 85, card2_y1 + 95)
            self.main_canvas.itemconfigure(self._aniso_combo_win, width=(left_card_x2 - 18) - (col2_start + 85))

            self.main_canvas.coords(self._lbl_win_size_id, left_card_x1 + 18, card2_y1 + 140)
            self.main_canvas.coords(self._res_combo_win, left_card_x1 + 105, card2_y1 + 127)
            self.main_canvas.itemconfigure(self._res_combo_win, width=col1_w - 95)

            self.main_canvas.coords(self._lbl_upscale_id, col2_start, card2_y1 + 140)
            self.main_canvas.coords(self._up_combo_win, col2_start + 98, card2_y1 + 127)
            self.main_canvas.itemconfigure(self._up_combo_win, width=(left_card_x2 - 18) - (col2_start + 98))

        # Proportional checkboxes placement
        chk_offsets = [0, int(card_inner_w * 0.16), int(card_inner_w * 0.41), int(card_inner_w * 0.67)]
        if hasattr(self, "chk_vsync"):
            chk_items = [
                (self.chk_vsync, self.t("vsync")),
                (self.chk_rcas, self.t("rcas")),
                (self.chk_audio, self.t("audio_log")),
                (self.chk_wav, self.t("wav_capture"))
            ]
            for idx, (chk, txt) in enumerate(chk_items):
                chk.config(text=txt)
                chk.set_position(left_card_x1 + 18 + chk_offsets[idx], card2_y1 + 176)

        max_hint_w = (left_card_x2 - left_card_x1) - 40
        if hasattr(self, "_res_hint_id"):
            self.main_canvas.coords(self._res_hint_id, left_card_x1 + 18, card2_y1 + 208)
            self.main_canvas.itemconfigure(self._res_hint_id, width=max_hint_w)
            self.main_canvas.coords(self._menu_hint_id, left_card_x1 + 18, card2_y1 + 228)
            self.main_canvas.itemconfigure(self._menu_hint_id, width=max_hint_w)

        # Card 3 (CONTROLLER & INPUT): Proportional Y-Spacing
        y_c3_hdr = card3_y1 + int(H3 * 0.08)
        y_c3_mode_lbl = card3_y1 + int(H3 * 0.17)
        y_c3_row1 = card3_y1 + int(H3 * 0.27)
        y_c3_cfg_lbl = card3_y1 + int(H3 * 0.39)
        y_c3_row2 = card3_y1 + int(H3 * 0.49)
        y_c3_row3 = card3_y1 + int(H3 * 0.61)
        y_c3_util_lbl = card3_y1 + int(H3 * 0.73)
        y_c3_row4 = card3_y1 + int(H3 * 0.83)
        y_c3_footer = card3_y1 + int(H3 * 0.94)

        if hasattr(self, "_ic_pad_id"):
            self.main_canvas.coords(self._ic_pad_id, left_card_x1 + 22, y_c3_hdr)
            self.main_canvas.coords(self._card_ctrl_title_id, left_card_x1 + 38, y_c3_hdr)
            self.main_canvas.coords(self._lbl_input_mode_id, left_card_x1 + 18, y_c3_mode_lbl)

        col_btn_w = (card_inner_w - 14) // 2
        btn_p1_x = left_card_x1 + 18 + col_btn_w // 2
        btn_p2_x = left_card_x1 + 18 + col_btn_w + 14 + col_btn_w // 2

        if hasattr(self, "btn_mode_pad"):
            self.btn_mode_pad.set_geometry(btn_p1_x, y_c3_row1, col_btn_w, 32)
            self.btn_mode_kbm.set_geometry(btn_p2_x, y_c3_row1, col_btn_w, 32)

        if hasattr(self, "_lbl_ctrl_config_id"):
            self.main_canvas.coords(self._lbl_ctrl_config_id, left_card_x1 + 18, y_c3_cfg_lbl)
            self.btn_kbm.set_geometry(btn_p1_x, y_c3_row2, col_btn_w, 30)
            self.btn_control_gamepad.set_geometry(btn_p2_x, y_c3_row2, col_btn_w, 30)
            self.btn_analog_sens.set_geometry(btn_p1_x, y_c3_row3, col_btn_w, 30)
            self.btn_reset_map.set_geometry(btn_p2_x, y_c3_row3, col_btn_w, 30)

        if hasattr(self, "_lbl_utils_id"):
            self.main_canvas.coords(self._lbl_utils_id, left_card_x1 + 18, y_c3_util_lbl)
            util_btn_w = (card_inner_w - (4 * 10)) // 5
            u_btns = [self.btn_cheats, self.btn_dlc, self.btn_open_log, self.btn_open_audio_log, self.btn_open_saves]
            for i, ub in enumerate(u_btns):
                ux = left_card_x1 + 18 + i * (util_btn_w + 10) + util_btn_w // 2
                ub.set_geometry(ux, y_c3_row4, util_btn_w, 28)

        if hasattr(self, "_pad_label_id"):
            self.main_canvas.coords(self._pad_label_id, left_card_x1 + 18, y_c3_footer)

        # Right Sidebar Stack
        if hasattr(self, "_hero_title_ids"):
            for tid, dx, dy, rel_y in self._hero_title_ids:
                target_y = int(h * rel_y)
                self.main_canvas.coords(tid, right_cx + dx, target_y + dy)

        y4 = int(h * 0.662)
        if hasattr(self, "_status_id"):
            self.main_canvas.coords(self._status_id, right_cx, y4)
            self.main_canvas.itemconfigure(self._status_id, width=int(right_col_w * 0.82))
            self.main_canvas.coords(self._status_shadow_id, right_cx + 1, y4 + 1)
            self.main_canvas.itemconfigure(self._status_shadow_id, width=int(right_col_w * 0.82))

        y_play = int(h * 0.745)
        y_stop = int(h * 0.835)
        y_util_r = int(h * 0.900)
        y_footer_r = int(h * 0.960)

        if hasattr(self, "play") and hasattr(self.play, "item_id"):
            self.play.set_geometry(right_cx, y_play, btn_play_w, btn_play_h)

        if hasattr(self, "stop") and hasattr(self.stop, "item_id"):
            self.stop.set_geometry(right_cx, y_stop, btn_play_w, 34)

        if hasattr(self, "credits_btn") and hasattr(self.credits_btn, "item_id"):
            self.credits_btn.set_geometry(right_cx - 5 - sub_w // 2, y_util_r, sub_w, 30)

        if hasattr(self, "check_update_btn") and hasattr(self.check_update_btn, "item_id"):
            self.check_update_btn.set_geometry(right_cx + 5 + sub_w // 2, y_util_r, sub_w, 30)

        if hasattr(self, "_wm_title"):
            self.main_canvas.coords(self._wm_title, right_cx, y_footer_r - 8)
            self.main_canvas.coords(self._wm_title_shadow, right_cx + 1, y_footer_r - 7)
            self.main_canvas.coords(self._wm_sub, right_cx, y_footer_r + 8)
            self.main_canvas.coords(self._wm_sub_shadow, right_cx + 1, y_footer_r + 9)

        # Clear combobox selection highlights
        for cb in [self.gpu_combo, self.fps_combo, self.aniso_combo, self.res_combo, self.up_combo]:
            cb.selection_clear()

    def _update_bg(self, w=None, h=None):
        """Update full-bleed canvas composite background on window resize or state change."""
        if not hasattr(self, "main_canvas"):
            return
        w = max(w or self.winfo_width(), 1040)
        h = max(h or self.winfo_height(), 680)
        try:
            self._composited_bg = compose_full_window_bg(w, h)
            self._bg_photo = ImageTk.PhotoImage(self._composited_bg)
            self.bg_photo = self._bg_photo
            bg_id = getattr(self, "_bg_item", getattr(self, "bg_id", None))
            if bg_id is not None:
                self.main_canvas.itemconfigure(bg_id, image=self._bg_photo)
                self.main_canvas.tag_lower(bg_id)
            self._reposition_elements(w, h)
            self._last_size = (w, h)
        except Exception as e:
            log_debug(f"Error updating full canvas background: {e}")

    def _on_configure(self, event):
        if event.widget != self:
            return
        w, h = event.width, event.height
        if getattr(self, "_last_size", None) == (w, h):
            return
        self._last_size = (w, h)
        if hasattr(self, "_bg_timer") and self._bg_timer:
            try:
                self.after_cancel(self._bg_timer)
            except Exception:
                pass
        self._bg_timer = self.after(40, lambda: self._update_bg(w, h))

    def _build(self):
        """Construct the single-canvas layout without nested opaque Tk frames or labels."""
        log_debug("Building Single-Canvas UI layout...")
        win_w, win_h = 1120, 760

        self.main_canvas = tk.Canvas(self, width=win_w, height=win_h, bd=0, highlightthickness=0)
        self.main_canvas.pack(fill="both", expand=True)

        self._composited_bg = compose_full_window_bg(win_w, win_h)
        self._bg_photo = ImageTk.PhotoImage(self._composited_bg)
        self._bg_item = self.main_canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")
        self.bg_id = self._bg_item

        self.card_display = self.main_canvas
        self._sprites = create_control_sprites()
        self._sprites["radio_off_tk"] = ImageTk.PhotoImage(self._sprites["radio_off"])
        self._sprites["radio_on_tk"] = ImageTk.PhotoImage(self._sprites["radio_on"])
        self._sprites["check_off_tk"] = ImageTk.PhotoImage(self._sprites["check_off"])
        self._sprites["check_on_tk"] = ImageTk.PhotoImage(self._sprites["check_on"])

        self._icons = generate_vector_icons()
        self._ic_fld_photo = ImageTk.PhotoImage(self._icons["folder_gold"])
        self._ic_disp_photo = ImageTk.PhotoImage(self._icons["display_gold"])
        self._ic_pad_photo = ImageTk.PhotoImage(self._icons["gamepad_gold"])

        left_card_x1 = int(win_w * 0.015)
        left_card_x2 = int(win_w * 0.612)
        card_inner_w = (left_card_x2 - left_card_x1) - 36
        right_cx = int(win_w * 0.806)
        right_col_w = win_w - left_card_x2

        card1_y1 = 62
        card2_y1 = int(win_h * 0.21)
        card3_y1 = int(win_h * 0.56)
        card3_y2 = win_h - 14
        H3 = card3_y2 - card3_y1

        # 1. TOP HEADER BAR
        title_x = left_card_x1 + 6
        title_y = 28
        title_text = f"{self.t('app_subtitle')} · {self.t('app_title').upper()}"
        self._hdr_title_shadow_id = self.main_canvas.create_text(
            title_x + 1, title_y + 1, text=title_text, font=("Segoe UI Bold", 15), fill="#040812", anchor="w"
        )
        self._hdr_title_id = self.main_canvas.create_text(
            title_x, title_y, text=title_text, font=("Segoe UI Bold", 15), fill="#FF4242", anchor="w"
        )
        self.header_title = CanvasTextProxy(self.main_canvas, self._hdr_title_id, self._hdr_title_shadow_id)

        title_w = measure_text_width(title_text, 15, bold=True)
        badge_x1 = max(int(title_x + title_w + 22), 528)

        self.header_status_pill = StatusPillCanvas(self.main_canvas, badge_x1, title_y, state="ready", text=self.t("ready"))
        self.lang_toggle = LanguageToggleCanvas(self.main_canvas, win_w - 18, title_y, self.lang, on_change=self.set_language)

        # 2. CARD 1: GAME LOCATION
        self._ic_fld_id = self.main_canvas.create_image(left_card_x1 + 22, 80, image=self._ic_fld_photo)
        self._card_game_title_id = self.main_canvas.create_text(
            left_card_x1 + 38, 80, text=f"{self.t('section_game')}", font=("Segoe UI Bold", 10), fill="#FF4242", anchor="w"
        )
        self.card_game_title = CanvasTextProxy(self.main_canvas, self._card_game_title_id)

        self._game_folder_lbl_id = self.main_canvas.create_text(
            left_card_x1 + 18, 108, text=self.t("game_folder"), font=("Segoe UI", 9), fill="#FF5E5E", anchor="w"
        )
        self.game_folder_lbl = CanvasTextProxy(self.main_canvas, self._game_folder_lbl_id)

        self.game_var = tk.StringVar(value=self.cfg.get("game", ""))
        self.game_var.trace_add("write", lambda *_: self._refresh_image_label())

        browse_w = 104
        browse_h = 28
        browse_x = left_card_x2 - 18 - browse_w
        
        lbl_w = measure_text_width(self.t("game_folder"), 9, bold=False)
        entry_x = max(left_card_x1 + 122, left_card_x1 + 20 + lbl_w + 16)
        entry_w = browse_x - 12 - entry_x

        self.game_entry = tk.Entry(self.main_canvas, textvariable=self.game_var, bg="#060D1E", fg="#FFFFFF",
                                  insertbackground="#FF5E5E", relief="flat", highlightbackground="#2563EB",
                                  highlightcolor="#60A5FA", highlightthickness=1, font=("Segoe UI", 9))
        self._game_entry_win = self.main_canvas.create_window(entry_x, 94, window=self.game_entry, width=entry_w, height=browse_h, anchor="nw")

        self.browse_btn = CanvasButton(self.main_canvas, browse_x + browse_w // 2, 108, browse_w, browse_h,
                                      text=self.t("browse_btn"), command=self._browse, icon_img=self._icons["folder_gold"], lang=self.lang)

        self._image_label_id = self.main_canvas.create_text(entry_x, 131, text="", font=("Segoe UI", 8),
                                                            fill="#4ADE80", anchor="w")
        self.image_label = CanvasTextProxy(self.main_canvas, self._image_label_id)

        # Floating Crimson Warning Banner
        toast_w = max(380, browse_x + browse_w - entry_x)
        self._toast_photo = self._render_floating_banner(toast_w)
        self._toast_item_id = self.main_canvas.create_image(entry_x, 153, image=self._toast_photo, anchor="nw")
        self.main_canvas.itemconfigure(self._toast_item_id, state="hidden")

        # 3. CARD 2: DISPLAY & GRAPHICS
        self._ic_disp_id = self.main_canvas.create_image(left_card_x1 + 22, card2_y1 + 18, image=self._ic_disp_photo)
        self._card_display_title_id = self.main_canvas.create_text(
            left_card_x1 + 38, card2_y1 + 18, text=f"{self.t('section_display')}", font=("Segoe UI Bold", 10), fill="#FF4242", anchor="w"
        )
        self.card_display_title = CanvasTextProxy(self.main_canvas, self._card_display_title_id)

        self.mode_var = tk.StringVar(value=self.cfg.get("display_mode", "exclusive"))
        card_inner_w = (left_card_x2 - left_card_x1) - 40
        rb_offsets = [0, int(card_inner_w * 0.28), int(card_inner_w * 0.64)]
        self.radio_buttons = []
        for idx, (label_text, key) in enumerate(DISPLAY_MODES):
            txt = self.t(f"mode_{key}")
            x_pos = left_card_x1 + 18 + rb_offsets[idx]
            rb = CanvasRadioButton(self.main_canvas, x_pos, card2_y1 + 42, txt, key,
                                   self.mode_var, self._sprites, callback=self._update_radio_styles)
            self.radio_buttons.append((rb, key))

        self._lbl_gpu_id = self.main_canvas.create_text(left_card_x1 + 18, card2_y1 + 76, text=self.t("gpu_select"), font=("Segoe UI", 9), fill="#FF5E5E", anchor="w")
        self.lbl_gpu = CanvasTextProxy(self.main_canvas, self._lbl_gpu_id)

        self.gpu_names = [name for _, name, _ in SYSTEM_GPUS]
        cur_gpu_idx = self.cfg.get("gpu_index", -1)
        cur_gpu_name = next((name for idx, name, _ in SYSTEM_GPUS if idx == cur_gpu_idx), self.gpu_names[0])
        self.gpu_var = tk.StringVar(value=cur_gpu_name)
        self.gpu_combo = ttk.Combobox(self.main_canvas, textvariable=self.gpu_var, state="readonly", values=self.gpu_names)
        self._gpu_combo_win = self.main_canvas.create_window(left_card_x1 + 160, card2_y1 + 63, window=self.gpu_combo,
                                                             width=(left_card_x2 - 18) - (left_card_x1 + 160), height=26, anchor="nw")

        col1_w = int(card_inner_w * 0.52)
        col2_start = left_card_x1 + 18 + int(card_inner_w * 0.55)

        self._lbl_fps_id = self.main_canvas.create_text(left_card_x1 + 18, card2_y1 + 108, text=self.t("frame_limit"), font=("Segoe UI", 9), fill="#FF5E5E", anchor="w")
        self.lbl_fps = CanvasTextProxy(self.main_canvas, self._lbl_fps_id)
        self.fps_var = tk.StringVar()
        self.fps_combo = ttk.Combobox(self.main_canvas, textvariable=self.fps_var, state="readonly", values=[n for n, _ in FPS_LIMITS])
        self._fps_combo_win = self.main_canvas.create_window(left_card_x1 + 105, card2_y1 + 95, window=self.fps_combo,
                                                             width=col1_w - 95, height=26, anchor="nw")

        self._lbl_aniso_id = self.main_canvas.create_text(col2_start, card2_y1 + 108, text=self.t("anisotropic"), font=("Segoe UI", 9), fill="#FF5E5E", anchor="w")
        self.lbl_aniso = CanvasTextProxy(self.main_canvas, self._lbl_aniso_id)
        self.aniso_var = tk.StringVar()
        self.aniso_combo = ttk.Combobox(self.main_canvas, textvariable=self.aniso_var, state="readonly", values=[n for n, _ in ANISO])
        self._aniso_combo_win = self.main_canvas.create_window(col2_start + 85, card2_y1 + 95, window=self.aniso_combo,
                                                               width=(left_card_x2 - 18) - (col2_start + 85), height=26, anchor="nw")

        self._lbl_win_size_id = self.main_canvas.create_text(left_card_x1 + 18, card2_y1 + 140, text=self.t("window_size"), font=("Segoe UI", 9), fill="#FF5E5E", anchor="w")
        self.lbl_win_size = CanvasTextProxy(self.main_canvas, self._lbl_win_size_id)
        self.res_var = tk.StringVar()
        self.res_combo = ttk.Combobox(self.main_canvas, textvariable=self.res_var, state="readonly", values=[n for n, _ in RESOLUTIONS])
        self._res_combo_win = self.main_canvas.create_window(left_card_x1 + 105, card2_y1 + 127, window=self.res_combo,
                                                             width=col1_w - 95, height=26, anchor="nw")

        self._lbl_upscale_id = self.main_canvas.create_text(col2_start, card2_y1 + 140, text=self.t("upscaling"), font=("Segoe UI", 9), fill="#FF5E5E", anchor="w")
        self.lbl_upscale = CanvasTextProxy(self.main_canvas, self._lbl_upscale_id)
        self.up_var = tk.StringVar()
        self.up_combo = ttk.Combobox(self.main_canvas, textvariable=self.up_var, state="readonly", values=[n for n, _ in UPSCALERS])
        self._up_combo_win = self.main_canvas.create_window(col2_start + 98, card2_y1 + 127, window=self.up_combo,
                                                            width=(left_card_x2 - 18) - (col2_start + 98), height=26, anchor="nw")

        self.vsync_var = tk.BooleanVar(value=self.cfg.get("vsync", False))
        self.rcas_var = tk.BooleanVar(value=self.cfg.get("rcas", True))
        self.audio_var = tk.BooleanVar(value=self.cfg.get("audio_log", False))
        self.wav_var = tk.BooleanVar(value=False)

        chk_offsets = [0, int(card_inner_w * 0.16), int(card_inner_w * 0.41), int(card_inner_w * 0.67)]
        self.chk_vsync = CanvasCheckbox(self.main_canvas, left_card_x1 + 18 + chk_offsets[0], card2_y1 + 176, self.t("vsync"), self.vsync_var, self._sprites)
        self.chk_rcas = CanvasCheckbox(self.main_canvas, left_card_x1 + 18 + chk_offsets[1], card2_y1 + 176, self.t("rcas"), self.rcas_var, self._sprites)
        self.chk_audio = CanvasCheckbox(self.main_canvas, left_card_x1 + 18 + chk_offsets[2], card2_y1 + 176, self.t("audio_log"), self.audio_var, self._sprites, command=self._audio_toggled)
        self.chk_wav = CanvasCheckbox(self.main_canvas, left_card_x1 + 18 + chk_offsets[3], card2_y1 + 176, self.t("wav_capture"), self.wav_var, self._sprites, command=self._wav_toggled)

        max_hint_w = (left_card_x2 - left_card_x1) - 40
        self._res_hint_id = self.main_canvas.create_text(
            left_card_x1 + 18, card2_y1 + 208, text=self.t("res_hint"), font=("Segoe UI", 8),
            fill="#FF6B6B", anchor="w", width=max_hint_w
        )
        self.res_hint = CanvasTextProxy(self.main_canvas, self._res_hint_id)

        self._menu_hint_id = self.main_canvas.create_text(
            left_card_x1 + 18, card2_y1 + 228, text=self.t("ingame_menu"), font=("Segoe UI", 8),
            fill="#FF6B6B", anchor="w", width=max_hint_w
        )
        self.menu_hint = CanvasTextProxy(self.main_canvas, self._menu_hint_id)

        # 4. CARD 3: CONTROLLER & INPUT
        y_c3_hdr = card3_y1 + int(H3 * 0.08)
        y_c3_mode_lbl = card3_y1 + int(H3 * 0.17)
        y_c3_row1 = card3_y1 + int(H3 * 0.27)
        y_c3_cfg_lbl = card3_y1 + int(H3 * 0.39)
        y_c3_row2 = card3_y1 + int(H3 * 0.49)
        y_c3_row3 = card3_y1 + int(H3 * 0.61)
        y_c3_util_lbl = card3_y1 + int(H3 * 0.73)
        y_c3_row4 = card3_y1 + int(H3 * 0.83)
        y_c3_footer = card3_y1 + int(H3 * 0.94)

        self._ic_pad_id = self.main_canvas.create_image(left_card_x1 + 22, y_c3_hdr, image=self._ic_pad_photo)
        self._card_ctrl_title_id = self.main_canvas.create_text(
            left_card_x1 + 38, y_c3_hdr, text=f"{self.t('section_controller')}", font=("Segoe UI Bold", 10), fill="#FF4242", anchor="w"
        )
        self.card_ctrl_title = CanvasTextProxy(self.main_canvas, self._card_ctrl_title_id)

        self._lbl_input_mode_id = self.main_canvas.create_text(
            left_card_x1 + 18, y_c3_mode_lbl, text=f"{self.t('input_mode')}", font=("Segoe UI Bold", 8), fill="#FF5E5E", anchor="w"
        )
        self.lbl_input_mode = CanvasTextProxy(self.main_canvas, self._lbl_input_mode_id)

        col_btn_w = (card_inner_w - 14) // 2
        btn_p1_x = left_card_x1 + 18 + col_btn_w // 2
        btn_p2_x = left_card_x1 + 18 + col_btn_w + 14 + col_btn_w // 2

        self.input_mode_var = tk.StringVar(value=self.cfg.get("input_mode", "controller"))
        self.btn_mode_pad = CanvasButton(
            self.main_canvas, btn_p1_x, y_c3_row1, col_btn_w, 32, text=self.t("input_mode_controller"),
            is_primary=(self.input_mode_var.get() == "controller"), icon_img=self._icons["gamepad"],
            command=lambda: self._select_input_mode("controller"), lang=self.lang
        )
        self.btn_mode_kbm = CanvasButton(
            self.main_canvas, btn_p2_x, y_c3_row1, col_btn_w, 32, text=self.t("input_mode_kbm"),
            is_primary=(self.input_mode_var.get() == "kbm_coop"), icon_img=self._icons["keyboard"],
            command=lambda: self._select_input_mode("kbm_coop"), lang=self.lang
        )

        self._lbl_ctrl_config_id = self.main_canvas.create_text(
            left_card_x1 + 18, y_c3_cfg_lbl, text=f"✦ {self.t('section_controller_config')}", font=("Segoe UI Bold", 8), fill="#FF5E5E", anchor="w"
        )
        self.lbl_ctrl_config = CanvasTextProxy(self.main_canvas, self._lbl_ctrl_config_id)

        self.btn_kbm = CanvasButton(self.main_canvas, btn_p1_x, y_c3_row2, col_btn_w, 30,
                                    text=self.t("kbm_controls_btn"), command=self.open_keymap_ui, icon_img=self._icons["keyboard"], lang=self.lang)
        self.btn_control_gamepad = CanvasButton(self.main_canvas, btn_p2_x, y_c3_row2, col_btn_w, 30,
                                                text=self.t("control_gamepad_btn"), command=self.open_gamepad_control_ui, icon_img=self._icons["gamepad"], lang=self.lang)
        self.btn_map_pad = self.btn_control_gamepad

        self.btn_analog_sens = CanvasButton(self.main_canvas, btn_p1_x, y_c3_row3, col_btn_w, 30,
                                            text=self.t("analog_sens_btn"), command=self.open_analog_sensitivity_ui, icon_img=self._icons["analog"], lang=self.lang)
        self.btn_map_sticks = self.btn_analog_sens

        self.btn_reset_map = CanvasButton(self.main_canvas, btn_p2_x, y_c3_row3, col_btn_w, 30,
                                          text=self.t("reset_map"), command=self.reset_map, icon_img=self._icons["reset"], lang=self.lang)

        self._lbl_utils_id = self.main_canvas.create_text(
            left_card_x1 + 18, y_c3_util_lbl, text=f"⚙ {self.t('section_utilities')}", font=("Segoe UI Bold", 8), fill="#FF5E5E", anchor="w"
        )
        self.lbl_utils = CanvasTextProxy(self.main_canvas, self._lbl_utils_id)

        util_btn_w = (card_inner_w - (4 * 10)) // 5
        self.btn_cheats = CanvasButton(self.main_canvas, left_card_x1 + 18 + 0 * (util_btn_w + 10) + util_btn_w // 2, y_c3_row4, util_btn_w, 28,
                                       text=self.t("cheats_btn"), command=self.open_cheats_manager, icon_img=self._icons["bolt"], lang=self.lang)
        self.btn_dlc = CanvasButton(self.main_canvas, left_card_x1 + 18 + 1 * (util_btn_w + 10) + util_btn_w // 2, y_c3_row4, util_btn_w, 28,
                                    text=self.t("dlc_btn"), command=self.open_dlc_manager, icon_img=self._icons["box"], lang=self.lang)
        self.btn_open_log = CanvasButton(self.main_canvas, left_card_x1 + 18 + 2 * (util_btn_w + 10) + util_btn_w // 2, y_c3_row4, util_btn_w, 28,
                                         text=self.t("open_log"), command=self.open_log, icon_img=self._icons["doc"], lang=self.lang)
        self.btn_open_audio_log = CanvasButton(self.main_canvas, left_card_x1 + 18 + 3 * (util_btn_w + 10) + util_btn_w // 2, y_c3_row4, util_btn_w, 28,
                                               text=self.t("open_audio_log"), command=self.open_audio_log, icon_img=self._icons["music"], lang=self.lang)
        self.btn_open_saves = CanvasButton(self.main_canvas, left_card_x1 + 18 + 4 * (util_btn_w + 10) + util_btn_w // 2, y_c3_row4, util_btn_w, 28,
                                           text=self.t("open_saves"), command=self.open_saves, icon_img=self._icons["save"], lang=self.lang)

        self._pad_label_id = self.main_canvas.create_text(left_card_x1 + 18, y_c3_footer, text="", font=("Segoe UI", 8), fill="#FF6B6B", anchor="w")
        self.pad_label = CanvasTextProxy(self.main_canvas, self._pad_label_id)
        self._pad_text()

        # 5. RIGHT SIDEBAR STACK
        y1 = int(win_h * 0.565)
        y2 = int(win_h * 0.598)
        y3 = int(win_h * 0.626)
        y4 = int(win_h * 0.662)

        self._hero_title_ids = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1), (-2, 0), (2, 0), (0, -2), (0, 2)]:
            tid = self.main_canvas.create_text(right_cx + dx, y1 + dy, text="戦国BASARA4 皇", fill="#03060F", font=("Segoe UI Bold", 13))
            self._hero_title_ids.append((tid, dx, dy, 0.565))
        tid0 = self.main_canvas.create_text(right_cx, y1, text="戦国BASARA4 皇", fill="#FF4242", font=("Segoe UI Bold", 13))
        self._hero_title_ids.append((tid0, 0, 0, 0.565))

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
            tid = self.main_canvas.create_text(right_cx + dx, y2 + dy, text="Sengoku Basara 4 Sumeragi", fill="#040812", font=("Segoe UI Semibold", 10))
            self._hero_title_ids.append((tid, dx, dy, 0.598))
        tid1 = self.main_canvas.create_text(right_cx, y2, text="Sengoku Basara 4 Sumeragi", fill="#FF5E5E", font=("Segoe UI Semibold", 10))
        self._hero_title_ids.append((tid1, 0, 0, 0.598))

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
            tid = self.main_canvas.create_text(right_cx + dx, y3 + dy, text="CUSA01159 · Native PS4 PC Port", fill="#040812", font=("Segoe UI", 9))
            self._hero_title_ids.append((tid, dx, dy, 0.626))
        tid2 = self.main_canvas.create_text(right_cx, y3, text="CUSA01159 · Native PS4 PC Port", fill="#FF5E5E", font=("Segoe UI", 9))
        self._hero_title_ids.append((tid2, 0, 0, 0.626))

        prompt_txt = self.t("pad_prompt")
        max_prompt_w = int(right_col_w * 0.82)
        self._status_shadow_id = self.main_canvas.create_text(
            right_cx + 1, y4 + 1, text=prompt_txt, fill="#040812", font=("Segoe UI", 8),
            width=max_prompt_w, justify="center"
        )
        self._status_id = self.main_canvas.create_text(
            right_cx, y4, text=prompt_txt, fill="#FF6B6B", font=("Segoe UI", 8),
            width=max_prompt_w, justify="center"
        )
        self.status = CanvasTextProxy(self.main_canvas, self._status_id, self._status_shadow_id)

        # Action Buttons
        y_play = int(win_h * 0.745)
        y_stop = int(win_h * 0.835)
        y_util_r = int(win_h * 0.900)
        y_footer_r = int(win_h * 0.960)

        btn_play_w = max(260, min(310, int(right_col_w * 0.72)))
        btn_play_h = int(round(btn_play_w / 4.32524))
        sub_w = (btn_play_w - 10) // 2

        self.play = CanvasButton(self.main_canvas, right_cx, y_play, btn_play_w, btn_play_h,
                                 text=self.t("play_btn"), command=self.on_play, is_primary=True, is_hero=True, lang=self.lang)

        self.stop = CanvasButton(self.main_canvas, right_cx, y_stop, btn_play_w, 34,
                                 text=self.t("stop_btn"), command=self.on_stop, is_primary=False, lang=self.lang)
        self.stop.config(state="disabled")

        self.credits_btn = CanvasButton(self.main_canvas, right_cx - 5 - sub_w // 2, y_util_r, sub_w, 30,
                                        text=self.t("credits_btn"), command=self.show_credits, icon_img=self._icons["users"], lang=self.lang)
        self.check_update_btn = CanvasButton(self.main_canvas, right_cx + 5 + sub_w // 2, y_util_r, sub_w, 30,
                                            text="Cek Update" if self.lang == "id" else "Check Update", command=self.check_update_manual, icon_img=self._icons["update"], lang=self.lang)

        self._wm_title_shadow = self.main_canvas.create_text(right_cx + 1, y_footer_r - 7, text=BRAND.upper(), fill="#040812", font=("Georgia", 10, "bold"))
        self._wm_title = self.main_canvas.create_text(right_cx, y_footer_r - 8, text=BRAND.upper(), fill="#FF4242", font=("Georgia", 10, "bold"))
        self._wm_sub_shadow = self.main_canvas.create_text(right_cx + 1, y_footer_r + 9, text=f"{self.t('by_author')} - v{VERSION}", fill="#040812", font=("Segoe UI", 8))
        self._wm_sub = self.main_canvas.create_text(right_cx, y_footer_r + 8, text=f"{self.t('by_author')} - v{VERSION}", fill="#FF6B6B", font=("Segoe UI", 8))
        self.wm_title = CanvasTextProxy(self.main_canvas, self._wm_title, self._wm_title_shadow)
        self.wm_sub = CanvasTextProxy(self.main_canvas, self._wm_sub, self._wm_sub_shadow)

        self.mode_var.trace_add("write", lambda *_: self._update_radio_styles())
        self.vsync_var.trace_add("write", lambda *_: self._update_radio_styles())
        self.rcas_var.trace_add("write", lambda *_: self._update_radio_styles())
        self.audio_var.trace_add("write", lambda *_: self._update_radio_styles())
        self.wav_var.trace_add("write", lambda *_: self._update_radio_styles())
        self._update_radio_styles()
        self._refresh_image_label()

        # Fix Combobox red/blue highlight bug
        for cb in [self.gpu_combo, self.fps_combo, self.aniso_combo, self.res_combo, self.up_combo]:
            cb.selection_clear()
            cb.bind("<Enter>", lambda e, c=cb: c.configure(style="Hover.TCombobox"))
            cb.bind("<Leave>", lambda e, c=cb: c.configure(style="TCombobox"))
            cb.bind("<<ComboboxSelected>>", lambda e: e.widget.selection_clear())
            cb.bind("<FocusIn>", lambda e: e.widget.selection_clear())
            cb.bind("<Button-1>", lambda e: e.widget.after(10, e.widget.selection_clear))

        self._breathe_phase = 0.0
        self._start_ambient_breathing()
        self.bind("<Configure>", self._on_configure)

    def _start_ambient_breathing(self):
        """Low-cost ambient breathing timer (50ms) gently pulsing status dot and Play Game aura."""
        self._ambient_breathe_tick()

    def _ambient_breathe_tick(self):
        self._breathe_phase = (self._breathe_phase + 0.08) % (2 * 3.14159)
        if hasattr(self, "header_status_pill") and self.header_status_pill:
            self.header_status_pill.pulse_tick(self._breathe_phase)
        if hasattr(self, "play") and self.play and not self.play.hovered and not self.play.pressed:
            self.play.pulse_tick(self._breathe_phase)
        self._breathe_timer = self.after(50, self._ambient_breathe_tick)

    # ---- helpers ----

    def _browse(self):
        path = filedialog.askdirectory(initialdir=self.game_var.get() or str(ROOT / "game"), mustexist=True)
        if path:
            self.game_var.set(os.path.normpath(path))
            self._refresh_image_label()

    def validate_game_directory(self, path_str=None):
        """
        Validate whether the game path exists, points to or is inside <launcher_root>/game,
        and contains valid game executables or param files.
        """
        if path_str is None:
            path_str = self.game_var.get().strip() if hasattr(self, "game_var") else ""
        if not path_str:
            return False
        try:
            p = Path(path_str).resolve()
        except Exception:
            return False
        if not p.is_dir():
            return False
        if (p / "eboot.bin").is_file() or (p / "sce_sys" / "param.sfo").is_file():
            return True
        try:
            for sub in p.iterdir():
                if sub.is_dir() and ((sub / "eboot.bin").is_file() or (sub / "sce_sys" / "param.sfo").is_file()):
                    return True
        except Exception:
            pass
        return False

    def _render_floating_banner(self, banner_w=480):
        bh = 28
        im = Image.new("RGBA", (banner_w, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([(0, 0), (banner_w - 1, bh - 1)], radius=8,
                            fill=(45, 8, 14, 235), outline=(239, 68, 68, 230), width=1)
        d.polygon([(18, 6), (10, 22), (26, 22)], fill=(251, 191, 36, 255))
        d.line([(18, 11), (18, 16)], fill=(45, 8, 14, 255), width=2)
        d.ellipse([(17, 18), (19, 20)], fill=(45, 8, 14, 255))
        msg = "Pastikan folder game berada di dalam direktori /game pada launcher!" if self.lang == "id" else "Please ensure the game is located inside the launcher's /game folder!"
        fnt = get_ui_font(8, bold=True)
        t_bbox = d.textbbox((0, 0), msg, font=fnt)
        th = t_bbox[3] - t_bbox[1]
        ty = (bh - th) // 2 - t_bbox[1]
        d.text((34, ty), msg, font=fnt, fill=(252, 165, 165, 255))
        return ImageTk.PhotoImage(im)

    def _refresh_image_label(self):
        game = self.game_var.get().strip() if hasattr(self, "game_var") else ""
        is_valid = self.validate_game_directory(game)
        if is_valid:
            text = "✓ Image game siap." if self.lang == "id" else "✓ Game image ready."
            if hasattr(self, "image_label"):
                self.image_label.config(text=text, fill="#4ADE80")
            if hasattr(self, "header_status_pill"):
                state = "running" if (self.proc and self.proc.poll() is None) else ("starting" if self.busy else "ready")
                pill_txt = self.t("running") if state == "running" else (self.t("starting") if state == "starting" else ("Siap dimainkan" if self.lang == "id" else "Ready to play"))
                self.header_status_pill.set_status(state, pill_txt)
            if hasattr(self, "_toast_item_id"):
                self.main_canvas.itemconfigure(self._toast_item_id, state="hidden")
        else:
            text = "✕ Game belum siap" if self.lang == "id" else "✕ Game not ready"
            if hasattr(self, "image_label"):
                self.image_label.config(text=text, fill="#FF4D4D")
            if hasattr(self, "header_status_pill"):
                self.header_status_pill.set_status("not_ready", "Game belum siap" if self.lang == "id" else "Game not ready")
            if hasattr(self, "_toast_item_id"):
                self.main_canvas.itemconfigure(self._toast_item_id, state="normal")
                self.main_canvas.tag_raise(self._toast_item_id)
    def _ini(self):

        if OLD_INI.exists() and not INI.exists():

            os.replace(OLD_INI, INI)

        return INI



    def _load_ini_into_ui(self):

        ini = read_ini(self._ini())

        mode = ini.get("display_mode", self.cfg["display_mode"])

        if mode in {k for _, k in DISPLAY_MODES}:

            self.mode_var.set(mode)

        if "vsync" in ini:

            self.vsync_var.set(ini["vsync"] == "1")

        if "rcas" in ini:

            self.rcas_var.set(ini["rcas"] == "1")

        res = ini.get("render_resolution", self.cfg["resolution"])

        self.res_var.set(next((n for n, v in RESOLUTIONS if v == res), RESOLUTIONS[0][0]))

        fsr = ini.get("fsr1")

        up = ("fsr1" if fsr == "1" else "off") if fsr is not None else self.cfg["upscale"]

        self.up_var.set(next((n for n, v in UPSCALERS if v == up), UPSCALERS[0][0]))

        fps = int(self.cfg["fps_limit"])

        self.fps_var.set(next((n for n, v in FPS_LIMITS if v == fps), FPS_LIMITS[0][0]))

        an = int(ini["anisotropy"]) if ini.get("anisotropy", "").isdigit() else self.cfg["anisotropy"]

        self.aniso_var.set(next((n for n, v in ANISO if v == an), "Off"))

        saved_gpu = self.cfg.get("gpu_index", -1)

        self.gpu_var.set(next((name for idx, name, _ in SYSTEM_GPUS if idx == saved_gpu), SYSTEM_GPUS[0][1]))

        self.input_mode_var.set(self.cfg.get("input_mode", "controller"))

        self.audio_var.set(self.cfg.get("audio_log", False))

        self.wav_var.set(False)



    def _update_radio_styles(self):
        """Ensure active radio selection labels and checkmarks reflect Crimson Red."""
        cur_mode = getattr(self, "mode_var", None)
        if cur_mode:
            m = cur_mode.get()
            for rb, key in getattr(self, "radio_buttons", []):
                try:
                    rb.configure(style="Active.TRadiobutton" if key == m else "TRadiobutton")
                except Exception:
                    pass

        cur_inp = getattr(self, "input_mode_var", None)
        if cur_inp and hasattr(self, "rb_controller") and hasattr(self, "rb_kbm"):
            val = cur_inp.get()
            try:
                self.rb_controller.configure(style="Active.TRadiobutton" if val == "controller" else "TRadiobutton")
                self.rb_kbm.configure(style="Active.TRadiobutton" if val == "kbm_coop" else "TRadiobutton")
            except Exception:
                pass

        for chk, var in [(getattr(self, "chk_vsync", None), getattr(self, "vsync_var", None)),
                         (getattr(self, "chk_rcas", None), getattr(self, "rcas_var", None)),
                         (getattr(self, "chk_audio", None), getattr(self, "audio_var", None)),
                         (getattr(self, "chk_wav", None), getattr(self, "wav_var", None))]:
            if chk and var:
                try:
                    chk.configure(style="Active.TCheckbutton" if var.get() else "TCheckbutton")
                except Exception:
                    pass

    def _select_input_mode(self, mode):
        self.input_mode_var.set(mode)
        self.cfg["input_mode"] = mode
        save_config(self.cfg)
        if hasattr(self, "btn_mode_pad") and hasattr(self, "btn_mode_kbm"):
            self.btn_mode_pad.is_primary = (mode == "controller")
            self.btn_mode_pad.render()
            self.btn_mode_kbm.is_primary = (mode == "kbm_coop")
            self.btn_mode_kbm.render()
        self._pad_text()

    def _pad_text(self):

        has_custom = False

        if MAPPING.exists() and MAPPING.stat().st_size > 0:

            try:

                content = MAPPING.read_text(encoding="utf-8", errors="ignore").strip()

                has_custom = (content != DEFAULT_XINPUT_MAPPING.strip())

            except Exception:

                has_custom = True

        text_val = self.t("pad_custom") if has_custom else self.t("pad_default")
        if not text_val.startswith("ⓘ"):
            text_val = f"ⓘ  {text_val}"
        self.pad_label.config(text=text_val)

    def _apply_window_icon(self, win):
        """Standardize Yukimura application icon across all Toplevel and modal windows."""
        if hasattr(self, "_icon_path") and self._icon_path and os.path.isfile(self._icon_path):
            try:
                win.iconbitmap(self._icon_path)
            except Exception:
                pass
            try:
                apply_window_native_icon(win, self._icon_path)
            except Exception:
                pass
        if hasattr(self, "_icon_photos") and self._icon_photos:
            try:
                win.iconphoto(False, *self._icon_photos)
            except Exception:
                pass
        elif hasattr(self, "_icon_photo") and self._icon_photo:
            try:
                win.iconphoto(False, self._icon_photo)
            except Exception:
                pass

    def _audio_toggled(self):

        if not self.audio_var.get():

            self.wav_var.set(False)



    def _wav_toggled(self):

        if not self.wav_var.get():

            return

        if messagebox.askyesno(self.t("wav_capture"), WAV_WARNING, icon="warning", default="no", parent=self):

            self.audio_var.set(True)

        else:

            self.wav_var.set(False)



    def _check_wav_leftovers(self):

        files, total = wav_captures()

        if not files or total < 50 * 2**20:

            return

        if messagebox.askyesno("Audio captures", f"user\\audio_wav holds {format_size(total)} of audio captures "

                               f"({len(files)} files) from an earlier session.\n\nDelete them to free the space?",

                               default="no", parent=self):

            for f in files:

                try:

                    f.unlink()

                except OSError:

                    pass



    def _collect(self):

        selected_gpu_name = self.gpu_var.get()

        selected_gpu_idx = next((idx for idx, name, _ in SYSTEM_GPUS if name == selected_gpu_name), -1)

        self.cfg.update(

            game=self.game_var.get().strip(), display_mode=self.mode_var.get(), vsync=self.vsync_var.get(),

            rcas=self.rcas_var.get(), fps_limit=dict(FPS_LIMITS)[self.fps_var.get()],

            resolution=dict(RESOLUTIONS)[self.res_var.get()], upscale=dict(UPSCALERS)[self.up_var.get()],

            anisotropy=dict(ANISO)[self.aniso_var.get()], audio_log=self.audio_var.get(),

            audio_wav=self.audio_var.get() and self.wav_var.get(),

            gpu_index=selected_gpu_idx,

            input_mode=self.input_mode_var.get(),

            language=self.lang)

        save_config(self.cfg)

        write_ini(self._ini(), {

            "display_mode": self.cfg["display_mode"], "vsync": int(self.cfg["vsync"]),

            "fps_limit": self.cfg["fps_limit"], "rcas": int(self.cfg["rcas"]),

            "anisotropy": self.cfg["anisotropy"], "render_resolution": self.cfg["resolution"],

            "fsr1": int(self.cfg["upscale"] == "fsr1"),

            "gpu_id": self.cfg.get("gpu_index", -1),

            "async_shaders": 1, "deferred_readback": 1, "stale_readback": 1, "frames_queued": 2})



    def _sync_language_assets(self):

        """Ponytail & REA Asset Swapper: Route active translation bundle."""

        lang_dir = MODS / f"lang_{self.lang}"

        lang_dir.mkdir(parents=True, exist_ok=True)

        mount_args = ["--mount", f"/app0/mods={lang_dir}"]



        patch_dir = lang_dir / "patches"

        if patch_dir.is_dir():

            user_patches = USER / "patches"

            user_patches.mkdir(parents=True, exist_ok=True)

            for p in patch_dir.glob("*.bin"):

                try:

                    shutil.copy2(p, user_patches / p.name)

                except Exception as e:

                    log_debug(f"Patch sync error: {e}")

        return mount_args



    def _env(self):

        env = os.environ.copy()

        env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")

        env["SPARTAN_GPU_USER_DIR"] = str(USER)

        env["SPARTAN_CONFIG"] = str(self._ini())

        env["SPARTAN_WINDOW_TITLE"] = f"{self.t('app_title')} - {BRAND} by {AUTHOR}"

        env["PONYTAIL_ACTIVE_LANG"] = str(self.lang)

        env["PONYTAIL_MODS_DIR"] = str(MODS / f"lang_{self.lang}")

        env["DISABLE_LAYER_AMD_SWITCHABLE_GRAPHICS_1"] = "1"



        gpu_idx = self.cfg.get("gpu_index", -1)

        if gpu_idx != -1:

            env["SPARTAN_GPU_ID"] = str(gpu_idx)

        else:

            disc_idx = next((idx for idx, _, is_disc in SYSTEM_GPUS if is_disc and idx >= 0), None)

            if disc_idx is not None:

                env["SPARTAN_GPU_ID"] = str(disc_idx)

            else:

                env.pop("SPARTAN_GPU_ID", None)



        avail_mb = check_commit_limit_mb()

        if avail_mb is not None and avail_mb < 3200:

            env["SPARTAN_DMEM_MB"] = "2048"

        elif avail_mb is not None and avail_mb < 4608:

            env["SPARTAN_DMEM_MB"] = "2560"



        mode = self.cfg.get("display_mode", "borderless")

        if mode in ("fullscreen", "borderless"):

            env["SPARTAN_FULLSCREEN"] = "1"

        else:

            env["SPARTAN_FULLSCREEN"] = "0"



        # Decoupled Vulkan presentation & multi-threaded async graphics pipeline

        env["SPARTAN_PRESENT_THREAD"] = "1"

        env["SPARTAN_ASYNC_SHADERS"] = "1"

        env["SPARTAN_ASYNC_FENCES"] = "1"

        env["SPARTAN_BACKGROUND_WARMUP"] = "1"

        env["SPARTAN_PARALLEL_WARMUP"] = "1"

        env["SPARTAN_PIPELINE_CACHE"] = "1"

        env["SPARTAN_COPY_THREADS"] = "4"

        env["SPARTAN_PREP_WORKERS"] = "4"

        env["SPARTAN_DEFERRED_READBACK"] = "1"

        env["SPARTAN_STALE_READBACK"] = "1"

        env["SPARTAN_GC_BUDGET_MB"] = "1024"

        env["SPARTAN_DIRECT_MEMORY_ACCESS"] = "1"



        # Decoupled low-latency audio driver configuration

        env["SPARTAN_AUDIO"] = "default"

        env["SDL_AUDIO_DRIVER"] = "wasapi"

        if self.cfg.get("audio_log", False):

            env["SPARTAN_AUDIO_DEBUG"] = str(AUDIO_LOG)

        if self.cfg.get("audio_log") and self.cfg.get("audio_wav"):

            env["SPARTAN_AUDIO_WAV_DIR"] = str(AUDIO_WAV)



        if WINDOW_ICON.exists():

            env["SPARTAN_WINDOW_ICON"] = str(WINDOW_ICON)

        if MAPPING.exists():

            env["SDL_GAMECONTROLLERCONFIG_FILE"] = str(MAPPING)

        if self.cfg["fps_limit"] != 60:

            env["SPARTAN_VBLANK_HZ"] = "0"

            env["SPARTAN_FPS_LIMIT"] = str(self.cfg["fps_limit"])



        user_keymap = dict(DEFAULT_PC_KEYMAP)

        user_keymap.update(self.cfg.get("keymap", {}))

        spec_parts = [f"{btn}={src}" for btn, src in user_keymap.items() if src]

        if spec_parts:

            env["SPARTAN_KEY_MAP"] = ",".join(spec_parts)



        if self.cfg.get("mouse_camera", True):

            env["SPARTAN_MOUSE_LOCK"] = "1"

            env["SPARTAN_MOUSE_AIM_STYLE"] = "0"

            sens = int(self.cfg.get("mouse_sens", 100))

            env["SPARTAN_MOUSE_AIM_SENSITIVITY"] = str(sens)



        env["SPARTAN_INPUT_MODE"] = str(self.cfg.get("input_mode", "controller"))



        res = self.cfg.get("resolution", "native")

        sub_1080p_map = {

            "360p": "640x360",

            "480p": "854x480",

            "540p": "960x540",

            "720p": "1280x720",

            "900p": "1600x900",

        }

        if res in sub_1080p_map:

            env["SPARTAN_RENDER_RES"] = sub_1080p_map[res]

        else:

            env.pop("SPARTAN_RENDER_RES", None)



        return env



    # ---- starting the game ----

    def on_play(self):

        if self.busy or self.proc:

            return

        self._collect()

        game = Path(self.cfg["game"]) if self.cfg["game"] else None

        exe = CORE

        if not game or not (game / "eboot.bin").is_file():

            self._deiconify()

            messagebox.showerror(self.t("err_cannot_start"), self.t("err_choose_game"))

            return

        if not exe.is_file():

            self._deiconify()

            messagebox.showerror(self.t("err_cannot_start"), f"{self.t('err_runtime_missing')}\n{exe}")

            return



        avail_mb = check_commit_limit_mb()

        if avail_mb is not None and avail_mb < 2560:

            if not messagebox.askyesno(

                "Virtual Memory Sangat Rendah",

                f"Sisa alokasi memori virtual Windows Anda hanya ~{avail_mb} MB.\n"

                "Game membutuhkan setidaknya ~3584 MB (3.5 GB) virtual memory.\n\n"

                "Jika game crash dengan Error 1455, pastikan Virtual Memory (Paging File) aktif di Windows.\n\n"

                "Tetap jalankan game?"):

                return



        self.busy = True

        self._stopped_by_user = False

        self.play.config(state="disabled")

        self.stop.config(state="disabled")

        self.status.config(text=self.t("starting"))

        if hasattr(self, "header_status_pill"):

            self.header_status_pill.set_status("starting", self.t("starting"))



        threading.Thread(target=self._boot_worker, args=(game, exe), daemon=True).start()



    def _set_status(self, text):

        if hasattr(self, "status"):

            self.status.config(text=text)



    def _read_log_tail(self, max_lines=12):

        try:

            if LOG.exists():

                text = LOG.read_text(encoding="latin-1", errors="replace").strip()

                lines = text.splitlines()

                return "\n".join(lines[-max_lines:])

        except Exception as e:

            return f"(Could not read log tail: {e})"

        return ""



    def _boot_worker(self, game, exe):

        log_launch(f"Starting boot sequence: game='{game}', exe='{exe}'")

        try:

            # 1. Image preparation

            if not image_ready(game):

                log_launch("Game image not ready. Starting preparation pipeline...")

                err = prepare_image(game, lambda msg: self.dispatch_ui(self._set_status, msg))

                if err:

                    log_launch(f"Game image preparation failed: {err}")

                    self.dispatch_ui(self._on_launch_failed, err)

                    return

                log_launch("Game image preparation completed successfully.")



            # 2. DLC Content Profile Refresh

            dlc_dir = self.cfg.get("dlc_dir", str(DEFAULT_DLC_DIR))

            if dlc_dir and Path(dlc_dir).is_dir():

                log_launch(f"Refreshing content profile with DLC directory: {dlc_dir}")

                err = prepare_content_profile(game, dlc_dir)

                if err:

                    log_launch(f"Content profile error: {err}")



            # 3. Audio runtime binary patches (D & E)

            if basara4_patches and hasattr(basara4_patches, "patch_audio_runtime"):

                try:

                    ok, note = basara4_patches.patch_audio_runtime(exe)

                    log_launch(f"Audio runtime patch: {note}")

                except Exception as e:

                    log_launch(f"Audio patch warning: {e}\n{traceback.format_exc()}")



            # 4. Patches: Frame limiter & GoldHEN Cheats

            selected_cheats = self.cfg.get("cheats", [])

            patch_args, notice = [], ""

            if (self.cfg["fps_limit"] != 60 or selected_cheats) and basara4_patches:

                try:

                    version = basara4_cheats.game_version(game) if (selected_cheats and basara4_cheats) else None

                    writes, notes = basara4_patches.build(

                        OUT / "eboot.elf", OUT / "patches.bin", self.cfg["fps_limit"] != 60,

                        core_path=exe, cheats=selected_cheats, game_version=version)

                    if writes:

                        patch_args = ["--patches", str(OUT / "patches.bin")]

                    if self.cfg["fps_limit"] != 60 and "unlimited fps" not in notes:

                        self.cfg["fps_limit"] = 60

                        notice = "Frame limiter not found in this eboot.bin: staying at 60.  "

                except Exception as e:

                    log_launch(f"Patch build warning: {e}\n{traceback.format_exc()}")

                    self.cfg["fps_limit"] = 60

                    notice = "Frame limiter disabled due to patch error.  "



            # 5. Window icon & Audio logs

            USER.mkdir(parents=True, exist_ok=True)

            self._make_window_icon(game)

            if AUDIO_LOG.exists():

                try:

                    os.replace(AUDIO_LOG, AUDIO_LOG.with_name("audio_debug.previous.log"))

                except OSError:

                    pass



            if self.cfg.get("audio_log") and self.cfg.get("audio_wav"):

                AUDIO_WAV.mkdir(parents=True, exist_ok=True)

                for old in AUDIO_WAV.glob("*.wav"):

                    try:

                        old.unlink()

                    except OSError:

                        pass



            # 6. Language assets & extra arguments

            mount_args = self._sync_language_assets()

            extra_args = []

            isa_table = OUT / "isa-rewrite.bin"

            if isa_table.is_file():

                extra_args += ["--isa-rewrite", str(isa_table)]

            if dlc_dir and Path(dlc_dir).is_dir():

                extra_args += ["--dlc-dir", str(dlc_dir)]



            # 7. Open log file

            try:

                log_file = open(LOG, "wb")

            except OSError as e:

                log_launch(f"Could not open standard log {LOG}: {e}. Creating alternative log.")

                alt_log = USER / f"last_run_{int(time.time())}.log"

                log_file = open(alt_log, "wb")



            # 8. Construct command and spawn process

            cmd = [

                str(exe),

                str(OUT / "boot-linked.bin"),

                "--content-profile", str(OUT / "content.bin"),

                "--app0", str(game),

                "--user", str(USER),

                "--no-game-hooks"

            ] + extra_args + mount_args + patch_args



            log_launch(f"Spawning game process: {' '.join(quote_arg(c) for c in cmd)}")

            creationflags = 0x00008000  # ABOVE_NORMAL_PRIORITY_CLASS

            proc = subprocess.Popen(

                cmd,

                env=self._env(),

                cwd=str(USER),

                stdout=log_file,

                stderr=subprocess.STDOUT,

                creationflags=creationflags

            )



            try:

                log_file.close()

            except Exception:

                pass



            self.proc = proc

            log_launch(f"Game process spawned successfully with PID {proc.pid}")



            if self.cfg.get("audio_wav"):

                self.cfg["audio_wav"] = False

                save_config(self.cfg)

                self.dispatch_ui(lambda: self.wav_var.set(False))



            self.dispatch_ui(self._on_process_spawned, notice)



            # 9. Active 8-second watchdog monitor

            watchdog_deadline = time.time() + 8.0

            died_early = False

            exit_code = None



            while time.time() < watchdog_deadline:

                code = proc.poll()

                if code is not None:

                    died_early = True

                    exit_code = code

                    break

                time.sleep(0.2)



            if died_early and not getattr(self, "_stopped_by_user", False):

                log_launch(f"Watchdog alert: Process {proc.pid} terminated early with exit code {exit_code:#x}")

                tail = self._read_log_tail()

                self.dispatch_ui(self._on_launch_crashed_early, exit_code, tail)

            elif not died_early:

                log_launch(f"Watchdog confirmed: Process {proc.pid} is running stably after 8s.")

                self.dispatch_ui(self._on_watchdog_passed)



        except Exception as e:

            tb = traceback.format_exc()

            log_launch(f"Unhandled exception during game boot sequence: {e}\n{tb}")

            self.dispatch_ui(self._on_launch_failed, str(e))



    def _on_process_spawned(self, notice):

        self.stop.config(state="normal")

        self.status.config(text=notice + (self.t("running_audio") if self.cfg.get("audio_log") else self.t("running")))

        if hasattr(self, "header_status_pill"):

            self.header_status_pill.set_status("running", self.t("running"))

        self._refresh_image_label()



    def _on_watchdog_passed(self):

        self.busy = False



    def _on_launch_failed(self, error):

        self.busy = False

        self.play.config(state="normal")

        self.stop.config(state="disabled")

        self._deiconify()

        self.status.config(text=f"Error: {error}")

        if hasattr(self, "header_status_pill"):

            self.header_status_pill.set_status("error", "Error")

        messagebox.showerror(self.t("err_cannot_start"), f"{self.t('err_boot_failed', default='Gagal memulai proses game:')}\n\n{error}")



    def _on_launch_crashed_early(self, code, tail):

        self.busy = False

        self.play.config(state="normal")

        self.stop.config(state="disabled")

        self._deiconify()

        self.status.config(text=self.t("exited_with_code", code=f"{code & 0xFFFFFFFF:#x}"))

        if hasattr(self, "header_status_pill"):

            self.header_status_pill.set_status("error", "Crash")

        self._show_crash_dialog(code)



    def _make_window_icon(self, game):

        if Image is None or WINDOW_ICON.exists():

            return

        try:

            Image.open(Path(game) / "sce_sys" / "icon0.png").convert("RGBA").resize((128, 128)).save(

                WINDOW_ICON, format="BMP")

        except OSError:

            pass



    # ---- DLC Manager Dialog ----

    def open_dlc_manager(self):
        window = tk.Toplevel(self)
        window.title("Extracted Basara 4 DLC" if self.lang != "id" else "Manajer DLC Sengoku Basara 4")
        self._apply_window_icon(window)
        apply_dark_titlebar(window)
        window.configure(bg="#070E20")
        window.geometry("980x530")
        window.minsize(760, 400)
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

        frame = tk.Frame(window, bg="#070E20", padx=16, pady=16)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        dlc_lbl = "DLC folder" if self.lang != "id" else "Folder DLC"
        tk.Label(frame, text=dlc_lbl, bg="#070E20", fg="#FF4242", font=("Segoe UI Bold", 11)).grid(row=0, column=0, sticky="w")
        path_var = tk.StringVar(value=self.cfg.get("dlc_dir", str(DEFAULT_DLC_DIR)))
        path_entry = tk.Entry(frame, textvariable=path_var, state="readonly", readonlybackground="#040814",
                              fg="#FF5E5E", bd=1, relief="solid", highlightcolor="#2563EB", highlightbackground="#2563EB",
                              font=("Segoe UI", 9))
        path_entry.grid(row=1, column=0, sticky="ew", pady=(8, 12))

        table_frame = tk.Frame(frame, bg="#070E20", bd=1, relief="solid", highlightbackground="#2563EB", highlightthickness=1)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("folder", "title", "content_id", "status")
        table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", style="Basara.Treeview")
        table.tag_configure("even", background="#081126", foreground="#FF5E5E")
        table.tag_configure("odd", background="#0B1733", foreground="#FF5E5E")
        table.tag_configure("warning", background="#2A0A10", foreground="#FF4D4D")
        table.tag_configure("info", background="#0E1B38", foreground="#60A5FA")
        table.tag_configure("ready", background="#07261C", foreground="#4ADE80")

        headers = (
            ("folder", "FOLDER / NAMA", 240),
            ("title", "DLC / TIPE", 180),
            ("content_id", "CONTENT ID", 240),
            ("status", "STATUS", 300)
        ) if self.lang == "id" else (
            ("folder", "FOLDER / NAME", 240),
            ("title", "DLC / TYPE", 180),
            ("content_id", "CONTENT ID", 240),
            ("status", "STATUS", 300)
        )
        for column, heading, width in headers:
            table.heading(column, text=heading)
            table.column(column, width=width, minwidth=100, stretch=column in ("folder", "title", "status"))

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview, style="Basara.Vertical.TScrollbar")
        table.configure(yscrollcommand=scrollbar.set)
        table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        summary = tk.Label(frame, text="", bg="#070E20", fg="#FF5E5E", font=("Segoe UI", 9))
        summary.grid(row=3, column=0, sticky="w", pady=(8, 2))

        info_note = tk.Label(frame, text=(
            "💡 Flexible DLC Scanner: Folder add-on di bawah DLC/ atau user/dlc/ terdeteksi secara dinamis dari param.sfo internal, meskipun nama folder berbeda dari label 16-karakter Sony. File .PKG mentah harus diekstrak dahulu."
            if self.lang == "id" else
            "💡 Flexible DLC Scanner: Add-on folders under DLC/ or user/dlc/ are detected dynamically by parsing internal param.sfo metadata, even if the folder name differs from the raw 16-char label. Raw .PKG files must be extracted first."
        ), bg="#070E20", fg="#64748B", font=("Segoe UI", 8), justify="left")
        info_note.grid(row=4, column=0, sticky="w", pady=(0, 4))

        def choose_folder():
            initial_dir = Path(path_var.get())
            if not initial_dir.is_dir():
                initial_dir = ROOT if ROOT.is_dir() else Path.home()
            try:
                selected = filedialog.askdirectory(
                    parent=self, title="Select the parent folder of extracted Basara 4 DLC" if self.lang != "id" else "Pilih folder induk DLC Basara 4 hasil ekstrak",
                    initialdir=str(initial_dir), mustexist=True)
            except (OSError, tk.TclError) as error:
                messagebox.showerror("Cannot open folder picker", str(error), parent=self)
                return
            if not selected:
                return

            try:
                selected_path = Path(selected).resolve(strict=True)
                if (selected_path / "sce_sys" / "param.sfo").is_file():
                    selected_path = selected_path.parent
                if not selected_path.is_dir():
                    raise NotADirectoryError(selected_path)
                previous = self.cfg.get("dlc_dir")
                self.cfg["dlc_dir"] = str(selected_path)
                try:
                    save_config(self.cfg)
                except OSError:
                    if previous is None:
                        self.cfg.pop("dlc_dir", None)
                    else:
                        self.cfg["dlc_dir"] = previous
                    raise
            except (OSError, RuntimeError) as error:
                messagebox.showerror("Cannot select DLC folder", str(error), parent=window)
                return

            path_var.set(self.cfg["dlc_dir"])
            refresh()

        def refresh():
            table.delete(*table.get_children())
            if not scan_extracted_dlc:
                summary.configure(text="DLC scanner module (basara4_dlc) not available.")
                return

            cur_dir = path_var.get()
            if not cur_dir or not Path(cur_dir).is_dir():
                cur_dir = str(DEFAULT_DLC_DIR)
                path_var.set(cur_dir)

            try:
                records = scan_extracted_dlc(cur_dir, lang=self.lang)
                # Flexible fallback: If current folder has no valid DLCs and is not DLC_DIR, try DLC_DIR, user/dlc, or game
                if not records or not any(info is not None for _p, info, _e in records):
                    for fallback in [DLC_DIR, USER_DLC_DIR, ROOT / "game"]:
                        if fallback.is_dir() and str(fallback) != cur_dir:
                            fallback_recs = scan_extracted_dlc(str(fallback), lang=self.lang)
                            if any(info is not None for _p, info, _e in fallback_recs):
                                records = fallback_recs
                                path_var.set(str(fallback))
                                self.cfg["dlc_dir"] = str(fallback)
                                save_config(self.cfg)
                                break
            except OSError as error:
                messagebox.showerror("Cannot scan DLC folder", str(error), parent=window)
                return

            ready = 0
            pkgs = 0
            invalid = 0

            for path, info, error in records:
                err_lower = (error or "").lower()
                if info:
                    ready += 1
                    table.insert("", "end", values=(path.name, info["title"], info["content_id"], "READY"), tags=("ready",))
                elif ".pkg" in err_lower:
                    pkgs += 1
                    table.insert("", "end", values=(path.name, "Package File (.PKG)", "-", error), tags=("info",))
                else:
                    invalid += 1
                    table.insert("", "end", values=(path.name, "-", "-", f"CHECK: {error}"), tags=("warning",))

            if not records:
                summary.configure(text="Folder ini kosong atau belum ada DLC hasil ekstrak." if self.lang == "id" else "No extracted DLC found in this folder.", fg="#94A3B8")
            else:
                parts = []
                if ready:
                    parts.append(f"✓ {ready} DLC Siap dimainkan" if self.lang == "id" else f"✓ {ready} DLC ready")
                if pkgs:
                    parts.append(f"📦 {pkgs} File .PKG Mentah" if self.lang == "id" else f"📦 {pkgs} Raw .PKG File")
                if invalid:
                    parts.append(f"⚠ {invalid} Perlu Perhatian" if self.lang == "id" else f"⚠ {invalid} Needs Attention")
                summary.configure(text="  |  ".join(parts), fg="#4ADE80" if ready else "#94A3B8")

        def open_folder():
            folder = Path(path_var.get())
            try:
                folder.mkdir(parents=True, exist_ok=True)
                os.startfile(str(folder))
            except OSError as error:
                messagebox.showerror("Cannot open DLC folder", str(error), parent=window)

        btn_canvas = tk.Canvas(frame, height=44, bg="#070E20", bd=0, highlightthickness=0)
        btn_canvas.grid(row=5, column=0, sticky="ew", pady=(8, 0))

        btn_choose = CanvasButton(btn_canvas, 136 // 2 + 4, 22, 136, 32,
                                  text="Choose folder…" if self.lang != "id" else "Pilih Folder…",
                                  command=choose_folder, lang=self.lang)
        btn_open = CanvasButton(btn_canvas, 136 + 10 + 124 // 2 + 4, 22, 124, 32,
                                text="Open folder" if self.lang != "id" else "Buka Folder",
                                command=open_folder, lang=self.lang)
        btn_refresh = CanvasButton(btn_canvas, 136 + 10 + 124 + 10 + 108 // 2 + 4, 22, 108, 32,
                                   text="Refresh" if self.lang != "id" else "Segarkan",
                                   command=refresh, lang=self.lang)
        btn_close = CanvasButton(btn_canvas, 750, 22, 108, 32,
                                 text="Close" if self.lang != "id" else "Tutup",
                                 command=window.destroy, is_primary=True, lang=self.lang)

        def _reposition_dlc_btns(e=None):
            cw = btn_canvas.winfo_width()
            if cw > 50:
                btn_close.set_geometry(cw - 108 // 2 - 4, 22, 108, 32)
        btn_canvas.bind("<Configure>", _reposition_dlc_btns)

        refresh()



    # ---- Cheats Manager Dialog ----

    def open_cheats_manager(self):

        if not basara4_cheats:

            messagebox.showinfo("Cheats", "Cheat engine module not available.")

            return

        try:

            current = basara4_cheats.normalize_selection(self.cfg.get("cheats", []))

        except ValueError as error:

            messagebox.showerror("Invalid cheat settings", str(error), parent=self)

            return



        window = tk.Toplevel(self)
        window.title("Basara 4 Cheats")
        self._apply_window_icon(window)
        apply_dark_titlebar(window)
        window.configure(bg="#070E20")

        window.geometry("640x430")
        window.minsize(580, 390)
        window.transient(self)
        window.grab_set()

        frame = tk.Frame(window, bg="#070E20", padx=18, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="GoldHEN cheats · CUSA01159 · update 01.02",
                 bg="#070E20", fg="#FF4242", font=("Segoe UI Bold", 11)).pack(anchor="w")

        tk.Label(frame, text="Cheat codes by Q8Despair. These are applied on the next game launch.",
                 bg="#070E20", fg="#FF6B6B", font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 12))

        selected = set(current)
        toggles = {}
        for cheat_id, cheat in basara4_cheats.CHEATS.items():
            var = tk.BooleanVar(value=cheat_id in selected)
            toggles[cheat_id] = var
            tk.Checkbutton(
                frame, text=f"{basara4_cheats.CHEATS[cheat_id]['name']}  ·  by {basara4_cheats.AUTHOR}",
                variable=var, bg="#070E20", fg="#FF5E5E", selectcolor="#040814",
                activebackground="#070E20", activeforeground="#FF7575", font=("Segoe UI", 9)
            ).pack(anchor="w", pady=4)

        tk.Label(frame, text="Cave dan hook tiap cheat dipisahkan agar semuanya bisa aktif bersamaan.",
                 bg="#070E20", fg="#FF6B6B", font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        source_row = tk.Frame(frame, bg="#070E20")
        source_row.pack(fill="x", pady=(10, 0))

        tk.Label(source_row, text="Source: GoldHEN Cheat Repository (GPL-3.0)",
                 bg="#070E20", fg="#FF6B6B", font=("Segoe UI", 8)).pack(side="left")

        def open_source():
            webbrowser.open(basara4_cheats.SOURCE_URL)

        btn_src_canvas = tk.Canvas(source_row, width=110, height=28, bg="#070E20", bd=0, highlightthickness=0)
        btn_src_canvas.pack(side="right")
        CanvasButton(btn_src_canvas, 55, 14, 104, 26, text="View source", command=open_source, lang=self.lang)

        buttons_canvas = tk.Canvas(frame, height=38, bg="#070E20", bd=0, highlightthickness=0)
        buttons_canvas.pack(fill="x", side="bottom", pady=(16, 0))

        def save():
            choices = [cheat_id for cheat_id, var in toggles.items() if var.get()]
            try:
                basara4_cheats.validate_selection(choices)
                previous = self.cfg.get("cheats", [])
                self.cfg["cheats"] = choices
                try:
                    save_config(self.cfg)
                except OSError:
                    self.cfg["cheats"] = previous
                    raise
            except (OSError, ValueError) as error:
                messagebox.showerror("Cannot save cheats", str(error), parent=window)
                return
            window.destroy()

        btn_cancel = CanvasButton(buttons_canvas, 100, 19, 100, 30, text="Cancel", command=window.destroy, lang=self.lang)
        btn_save = CanvasButton(buttons_canvas, 220, 19, 110, 30, text="Save cheats", command=save, is_primary=True, lang=self.lang)

        def _reposition_cheat_btns(e=None):
            cw = buttons_canvas.winfo_width()
            if cw > 50:
                btn_cancel.set_geometry(cw - 54, 19, 100, 30)
                btn_save.set_geometry(cw - 54 - 110 - 8, 19, 110, 30)
        buttons_canvas.bind("<Configure>", _reposition_cheat_btns)



    # ---- Keyboard & Mouse Mapping Dialog ----

    def open_keymap_ui(self):

        win = tk.Toplevel(self)
        win.title("Keyboard & Mouse Controls — Custom Keymap")
        self._apply_window_icon(win)
        apply_dark_titlebar(win)
        win.configure(bg=ROOT_BG)

        win.geometry("740x620")

        win.minsize(680, 520)

        win.grab_set()



        cur_map = dict(DEFAULT_PC_KEYMAP)

        cur_map.update(self.cfg.get("keymap", {}))

        mouse_cam_var = tk.BooleanVar(value=self.cfg.get("mouse_camera", True))

        mouse_sens_var = tk.IntVar(value=self.cfg.get("mouse_sens", 100))



        top_frame = ttk.Frame(win, style="Card.TFrame", padding=12)

        top_frame.pack(fill="x", padx=14, pady=(12, 6))



        tk.Label(top_frame, text="⚙️ Pengaturan Kontrol Keyboard & Mouse", bg=CARD_BG, fg=RED_PRIMARY, font=("Segoe UI Bold", 12)).pack(anchor="w")

        tk.Label(top_frame, text="Klik tombol untuk mengubah tombol pemetaan. Tekan tombol Keyboard atau Mouse untuk mengikat.", bg=CARD_BG, fg=FG, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))



        mouse_bar = ttk.Frame(top_frame, style="Card.TFrame")

        mouse_bar.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(mouse_bar, text="Aktifkan Kamera Mouse (Mouse Look)", variable=mouse_cam_var).pack(side="left")



        sens_frame = ttk.Frame(mouse_bar, style="Card.TFrame")

        sens_frame.pack(side="right")

        ttk.Label(sens_frame, text="Sensitivitas: ", style="Card.TLabel").pack(side="left")

        sens_lbl = ttk.Label(sens_frame, text=f"{mouse_sens_var.get()}%", style="Card.TLabel", width=5)

        sens_lbl.pack(side="right")



        def on_sens_scroll(val):

            sens_lbl.config(text=f"{int(float(val))}%")



        scale = ttk.Scale(sens_frame, from_=20, to=300, variable=mouse_sens_var, command=on_sens_scroll, length=120)

        scale.pack(side="left", padx=6)



        body_container = ttk.Frame(win, style="TFrame")

        body_container.pack(fill="both", expand=True, padx=14, pady=6)



        canvas = tk.Canvas(body_container, bg=ROOT_BG, highlightthickness=0)

        scrollbar = ttk.Scrollbar(body_container, orient="vertical", command=canvas.yview)

        scroll_content = ttk.Frame(canvas, style="TFrame")



        scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas_window = canvas.create_window((0, 0), window=scroll_content, anchor="nw")



        def on_canvas_configure(event):

            canvas.itemconfig(canvas_window, width=event.width)



        canvas.bind("<Configure>", on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)

        scrollbar.pack(side="right", fill="y")



        btn_widgets = {}

        active_listening = [None]



        def format_binding_display(key_str):

            if not key_str:

                return "None"

            return key_str.upper() if len(key_str) <= 3 else key_str



        def finish_listen(action_name, new_key):

            if active_listening[0] == action_name:

                active_listening[0] = None

                cur_map[action_name] = new_key

                btn = btn_widgets.get(action_name)

                if btn:

                    btn.config(text=format_binding_display(new_key), bg="#2C2824", fg=RED_PRIMARY)

                win.unbind("<Key>")

                win.unbind("<Button-1>")

                win.unbind("<Button-2>")

                win.unbind("<Button-3>")



        def start_listen(action_name):

            if active_listening[0]:

                old_action = active_listening[0]

                old_btn = btn_widgets.get(old_action)

                if old_btn:

                    old_btn.config(text=format_binding_display(cur_map.get(old_action, "")), bg="#2C2824", fg=RED_PRIMARY)

            active_listening[0] = action_name

            btn = btn_widgets.get(action_name)

            if btn:

                btn.config(text="[ TEKAN TOMBOL... ]", bg=RED_PRIMARY, fg="#FFF")



            def on_key_event(event):

                keysym = event.keysym

                key_map_table = {

                    "Return": "Return", "Escape": "Escape", "space": "Space",

                    "BackSpace": "Backspace", "Tab": "Tab", "Shift_L": "Left Shift",

                    "Shift_R": "Right Shift", "Control_L": "Left Ctrl", "Control_R": "Right Ctrl",

                    "Alt_L": "Left Alt", "Alt_R": "Right Alt", "Caps_Lock": "CapsLock",

                    "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",

                    "comma": "Comma", "equal": "Equals", "period": "Period",

                    "slash": "Slash", "semicolon": "Semicolon", "minus": "Minus"

                }

                mapped_name = key_map_table.get(keysym, keysym.capitalize() if len(keysym) > 1 else keysym.upper())

                finish_listen(action_name, mapped_name)

                return "break"



            def on_mouse_event(btn_num):

                name_map = {1: "Mouse Left", 2: "Mouse Middle", 3: "Mouse Right"}

                finish_listen(action_name, name_map.get(btn_num, f"Mouse {btn_num}"))

                return "break"



            win.bind("<Key>", on_key_event)

            win.focus_set()

            win.bind("<Button-1>", lambda e: on_mouse_event(1))

            win.bind("<Button-2>", lambda e: on_mouse_event(2))

            win.bind("<Button-3>", lambda e: on_mouse_event(3))



        for row_idx, (action_key, action_label, ps_button_label) in enumerate(ACTION_DESCRIPTIONS):

            item_frame = tk.Frame(scroll_content, bg="#181512", padx=12, pady=7, highlightbackground="#25211D", highlightthickness=1)

            item_frame.pack(fill="x", pady=2, padx=4)



            lbl_text = f"{action_label}"

            tk.Label(item_frame, text=lbl_text, bg="#181512", fg=FG, font=("Segoe UI Semibold", 9), anchor="w").pack(side="left", padx=(4, 0))

            tk.Label(item_frame, text=f"({ps_button_label})", bg="#181512", fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(side="left", padx=8)



            val = cur_map.get(action_key, "")

            key_btn = tk.Button(

                item_frame,

                text=format_binding_display(val),

                bg="#2C2824",

                fg=RED_PRIMARY,

                activebackground=RED_PRIMARY,

                activeforeground="#FFF",

                font=("Consolas", 10, "bold"),

                width=16,

                relief="flat",

                bd=0,

                padx=8,

                pady=4,

                cursor="hand2",

                command=lambda a=action_key: start_listen(a)

            )

            key_btn.pack(side="right")

            btn_widgets[action_key] = key_btn



        notice_frame = tk.Frame(scroll_content, bg=CARD_BG, padx=12, pady=6)

        notice_frame.pack(fill="x", pady=(8, 4), padx=4)

        tk.Label(

            notice_frame,

            text="ℹ️ Pergerakan Karakter otomatis terikat pada W, A, S, D (Standar PC). Kamera mouse mengontrol analog kanan.",

            bg=CARD_BG,

            fg=MUTED,

            font=("Segoe UI", 8, "italic")

        ).pack(anchor="w")



        bottom_bar = ttk.Frame(win, style="TFrame", padding=12)

        bottom_bar.pack(fill="x")



        def reset_defaults():

            cur_map.clear()

            cur_map.update(DEFAULT_PC_KEYMAP)

            mouse_cam_var.set(True)

            mouse_sens_var.set(100)

            sens_lbl.config(text="100%")

            for k, b in btn_widgets.items():

                b.config(text=format_binding_display(cur_map.get(k, "")), bg="#2C2824", fg=RED_PRIMARY)

            messagebox.showinfo("Reset Preset", "Pengaturan kontrol berhasil dikembalikan ke Preset Default PC!", parent=win)



        def save_and_close():

            self.cfg["keymap"] = cur_map

            self.cfg["mouse_camera"] = mouse_cam_var.get()

            self.cfg["mouse_sens"] = int(mouse_sens_var.get())

            save_config(self.cfg)

            win.destroy()

            messagebox.showinfo("Tersimpan", "Pengaturan kontrol Keyboard & Mouse berhasil disimpan!", parent=self)



        ttk.Button(bottom_bar, text="🔄 Reset ke Default PC", command=reset_defaults).pack(side="left", padx=4)

        ttk.Button(bottom_bar, text="Batal", command=win.destroy).pack(side="right", padx=4)

        ttk.Button(bottom_bar, text="💾 Simpan Pengaturan", command=save_and_close).pack(side="right", padx=4)



    # ---- Crash Diagnostic Dialog ----

    def _show_crash_dialog(self, code):

        data = extract_crash_summary(LOG)

        win = tk.Toplevel(self)
        win.title("Basara 4 PC — Crash Diagnostic")
        self._apply_window_icon(win)
        apply_dark_titlebar(win)
        win.configure(bg=ROOT_BG)

        win.geometry("740x560")

        win.minsize(680, 480)

        win.grab_set()



        btn_bar = ttk.Frame(win, style="TFrame", padding=12)

        btn_bar.pack(side="bottom", fill="x")



        header_frame = ttk.Frame(win, style="Card.TFrame", padding=14)

        header_frame.pack(side="top", fill="x", padx=12, pady=(12, 6))



        exit_hex = f"{code & 0xFFFFFFFF:#x}" if isinstance(code, int) else "Unknown"

        tk.Label(

            header_frame,

            text=f"⚠️ Game Berhenti Mendadak (Exit Code {exit_hex})",

            bg=CARD_BG,

            fg=RED_PRIMARY,

            font=("Segoe UI Bold", 12)

        ).pack(anchor="w")



        tk.Label(

            header_frame,

            text="Terdeteksi indikasi error dari log permainan di bawah ini:",

            bg=CARD_BG,

            fg=FG,

            font=("Segoe UI", 9)

        ).pack(anchor="w", pady=(4, 6))



        for err in data["detected_errors"]:

            tk.Label(

                header_frame,

                text=f"• {err}",

                bg=CARD_BG,

                fg=RED_PRIMARY,

                font=("Consolas", 9, "bold"),

                wraplength=680,

                justify="left"

            ).pack(anchor="w", padx=6)



        body_frame = ttk.Frame(win, style="TFrame")

        body_frame.pack(side="top", fill="both", expand=True, padx=12, pady=6)



        ttk.Label(body_frame, text="Cuplikan 10 Baris Log Terakhir (Raw Context):", style="Card.TLabel").pack(anchor="w", pady=(0, 4))

        txt = tk.Text(body_frame, bg="#0D0B0A", fg="#D6CFC7", relief="flat", wrap="none", font=("Consolas", 9), padx=8, pady=8)

        txt.insert("1.0", data["tail_context"])

        txt.config(state="disabled")

        txt.pack(fill="both", expand=True)



        def copy_details():

            try:

                k = ctypes.windll.kernel32

                class MEMORYSTATUSEX(ctypes.Structure):

                    _fields_ = [

                        ("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),

                        ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),

                        ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),

                        ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),

                        ("ullAvailExtendedVirtual", ctypes.c_uint64),

                    ]

                mem = MEMORYSTATUSEX()

                mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)

                k.GlobalMemoryStatusEx(ctypes.byref(mem))

                ram_total = f"{mem.ullTotalPhys // (1024*1024)} MB"

                ram_avail = f"{mem.ullAvailPhys // (1024*1024)} MB"

                commit_avail = f"{mem.ullAvailPageFile // (1024*1024)} MB"

            except Exception:

                ram_total = ram_avail = commit_avail = "N/A"



            gpu_list = "\n".join(f"  - {name}" for _, name, _ in SYSTEM_GPUS) if SYSTEM_GPUS else "  - None detected"



            audio_tail = ""

            if AUDIO_LOG.is_file():

                try:

                    a_lines = AUDIO_LOG.read_text(encoding="utf-8", errors="replace").splitlines()

                    if a_lines:

                        audio_tail = "\n".join(a_lines[-6:])

                except Exception:

                    pass



            clip_text = (

                f"=== Sengoku Basara 4 PC — Crash Diagnostic Report ===\n"

                f"Version       : v{VERSION}\n"

                f"Exit Code     : {exit_hex}\n"

                f"OS            : {platform.system()} {platform.release()} (Build {platform.version()})\n"

                f"Architecture  : {platform.machine()} ({platform.processor()})\n"

                f"RAM           : Total {ram_total} | Free {ram_avail} | Available Commit {commit_avail}\n"

                f"Vulkan GPUs   :\n{gpu_list}\n"

                f"Detected Fatal Signatures:\n" + "\n".join(f"  * {e}" for e in data["detected_errors"]) + "\n\n"

                f"--- [Last 10 Log Lines (last_run.log)] ---\n"

                f"{data['tail_context']}\n"

            )

            if audio_tail:

                clip_text += f"\n--- [Recent Audio Log (audio_debug.log)] ---\n{audio_tail}\n"



            clip_text += "\n=== End of Report ==="

            self.clipboard_clear()

            self.clipboard_append(clip_text)

            messagebox.showinfo(

                "Tersalin ke Clipboard",

                "Laporan crash lengkap (spek hardware, GPU, log error, dan audio log) berhasil disalin!\n"

                "Anda tinggal Paste (Ctrl+V) langsung ke Discord untuk bantuan teknis.",

                parent=win

            )



        def open_discord():

            webbrowser.open("https://discord.gg/UBZc57bBMa")



        ttk.Button(btn_bar, text="📋 Copy Error ke Clipboard", command=copy_details).pack(side="left", padx=4)

        ttk.Button(btn_bar, text="📁 Buka File Log", command=self.open_log).pack(side="left", padx=4)

        ttk.Button(btn_bar, text="🌐 Lapor ke Discord", command=open_discord).pack(side="left", padx=4)

        ttk.Button(btn_bar, text="Tutup", command=win.destroy).pack(side="right", padx=4)



    # ---- Auto Update Mechanism ----

    def _check_update_thread(self):

        info = check_latest_release()

        if info:

            self.update_info = info

            self.after(0, self._show_update_available)



    def _show_update_available(self):

        if not self.update_info or getattr(self, "_update_btn_shown", False):

            return

        self._update_btn_shown = True

        tag = self.update_info["tag"]

        if hasattr(self, "check_update_btn") and self.check_update_btn:

            self.check_update_btn.config(text=f"Update: {tag}")

        self.update_btn = tk.Button(

            self.mark_frame,

            text=f"Update ke {tag}",

            bg=RED_PRIMARY,

            fg=ROOT_BG,

            font=("Segoe UI", 9, "bold"),

            relief="flat",

            activebackground=RED_HOVER,

            activeforeground=ROOT_BG,

            cursor="hand2",

            command=self.prompt_update,

        )

        self.update_btn.pack(pady=(4, 0))



    def check_update_manual(self):

        self.status.config(text="Memeriksa pembaruan...")

        if hasattr(self, "header_status_pill"):

            self.header_status_pill.set_status("starting", "Memeriksa...")



        def run():

            info = check_latest_release()

            if info:

                self.update_info = info

                self.after(0, lambda: (

                    self.status.config(text="Ready"),
                    self._refresh_image_label(),
                    self._show_update_available(),

                    self.prompt_update()

                ))

            else:

                self.after(0, lambda: (

                    self.status.config(text=self.t("ready")),
                    self._refresh_image_label(),
                    messagebox.showinfo("Update", f"Anda sudah menggunakan versi terbaru (v{VERSION})." if self.lang == "id" else f"You are already using the latest version (v{VERSION}).")

                ))



        threading.Thread(target=run, daemon=True).start()



    def prompt_update(self):

        if not self.update_info:

            return

        tag = self.update_info["tag"]

        size_mb = self.update_info["size"] / (1024 * 1024)

        if messagebox.askyesno(

            "Update Tersedia",

            f"Versi baru {tag} tersedia di GitHub!\nUkuran unduhan: ~{size_mb:.1f} MB.\n\n"

            "Launcher akan mengunduh dan menerapkan update secara otomatis.\n"

            "Data game (folder game\\) dan save data Anda (folder user\\) TIDAK akan terhapus.\n\n"

            "Unduh dan pasang update sekarang?"

        ):

            self._download_and_apply_update(self.update_info)



    def _download_and_apply_update(self, info):

        win = tk.Toplevel(self)

        win.title("Basara 4 PC - Updater")

        win.configure(bg=ROOT_BG)

        win.geometry("440x180")

        win.resizable(False, False)

        win.grab_set()



        tk.Label(win, text=f"Mengunduh Pembaruan {info['tag']}...", bg=ROOT_BG, fg=RED_PRIMARY, font=("Segoe UI Bold", 11)).pack(pady=(18, 8))

        status_lbl = tk.Label(win, text="Menghubungkan ke GitHub...", bg=ROOT_BG, fg=FG, font=("Segoe UI", 9))

        status_lbl.pack(pady=(0, 8))



        prog = ttk.Progressbar(win, orient="horizontal", length=360, mode="determinate")

        prog.pack(pady=6)



        def worker():

            updates_dir = USER / "updates"

            updates_dir.mkdir(parents=True, exist_ok=True)

            zip_path = updates_dir / "update.zip"



            try:

                req = urllib.request.Request(info["url"], headers={"User-Agent": "Basara4-PC-Launcher"})

                ctx = ssl.create_default_context()

                with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:

                    total = int(resp.headers.get("Content-Length", info["size"] or 1))

                    downloaded = 0

                    chunk_size = 64 * 1024

                    with open(zip_path, "wb") as f:

                        while True:

                            chunk = resp.read(chunk_size)

                            if not chunk:

                                break

                            f.write(chunk)

                            downloaded += len(chunk)

                            percent = int((downloaded / total) * 100) if total else 0

                            cur_mb = downloaded / (1024 * 1024)

                            tot_mb = total / (1024 * 1024)

                            win.after(0, lambda p=percent, c=cur_mb, t=tot_mb: (

                                prog.configure(value=p),

                                status_lbl.configure(text=f"Mengunduh: {c:.1f} MB / {t:.1f} MB ({p}%)")

                            ))



                win.after(0, lambda: self._apply_update_and_restart(win))

            except Exception as e:

                win.after(0, lambda err=e: (

                    win.destroy(),

                    messagebox.showerror("Gagal Mengunduh", f"Pembaruan gagal diunduh:\n{err}")

                ))



        threading.Thread(target=worker, daemon=True).start()



    def _apply_update_and_restart(self, win):

        win.destroy()

        updater_cmd = USER / "updater.cmd"

        cmd_content = (

            "@echo off\r\n"

            "setlocal enabledelayedexpansion\r\n"

            "title Basara 4 PC - Updater\r\n"

            "cd /d \"%~dp0\"\r\n"

            "echo Menunggu launcher menutup...\r\n"

            "timeout /t 2 /nobreak >nul\r\n"

            "set \"ZIP=%~dp0updates\\update.zip\"\r\n"

            "set \"EXTRACT=%~dp0updates\\extract\"\r\n"

            "set \"DEST=%~dp0..\"\r\n"

            "if not exist \"!ZIP!\" exit /b 1\r\n"

            "echo Mengekstrak pembaruan...\r\n"

            "if exist \"!EXTRACT!\" rmdir /s /q \"!EXTRACT!\"\r\n"

            "mkdir \"!EXTRACT!\"\r\n"

            "tar -xf \"!ZIP!\" -C \"!EXTRACT!\" 2>nul\r\n"

            "if errorlevel 1 (\r\n"

            "    powershell.exe -NoProfile -Command \"Expand-Archive -Path '!ZIP!' -DestinationPath '!EXTRACT!' -Force\"\r\n"

            ")\r\n"

            "set \"SRC=!EXTRACT!\"\r\n"

            "if not exist \"!EXTRACT!\\Sengoku Basara 4.exe\" (\r\n"

                   "    for /d %%D in (\"!EXTRACT!\\*\") do (\r\n"

            "        if exist \"%%~fD\\Sengoku Basara 4.exe\" set \"SRC=%%~fD\"\r\n"

            "    )\r\n"

            ")\r\n"

            "echo Menerapkan file baru...\r\n"

            "if exist \"!SRC!\\_internal\" xcopy /e /y /i \"!SRC!\\_internal\" \"!DEST!\\_internal\" >nul\r\n"

            "if exist \"!SRC!\\bin\" xcopy /e /y /i \"!SRC!\\bin\" \"!DEST!\\bin\" >nul\r\n"

            "if exist \"!SRC!\\scripts\" xcopy /e /y /i \"!SRC!\\scripts\" \"!DEST!\\scripts\" >nul\r\n"

            "if exist \"!SRC!\\launcher\" xcopy /e /y /i \"!SRC!\\launcher\" \"!DEST!\\launcher\" >nul\r\n"

            "if exist \"!SRC!\\Sengoku Basara 4.exe\" copy /y \"!SRC!\\Sengoku Basara 4.exe\" \"!DEST!\\\" >nul\r\n"

            "if exist \"!SRC!\\Play Sengoku Basara 4.cmd\" copy /y \"!SRC!\\Play Sengoku Basara 4.cmd\" \"!DEST!\\\" >nul\r\n"

            "if exist \"!SRC!\\NOTICE.md\" copy /y \"!SRC!\\NOTICE.md\" \"!DEST!\\\" >nul\r\n"

            "if exist \"!SRC!\\LICENSE\" copy /y \"!SRC!\\LICENSE\" \"!DEST!\\\" >nul\r\n"

            "rmdir /s /q \"!EXTRACT!\" 2>nul\r\n"

            "del /f /q \"!ZIP!\" 2>nul\r\n"

            "echo Memulai versi baru...\r\n"

            "start \"\" \"!DEST!\\Sengoku Basara 4.exe\"\r\n"

            "del /f /q \"%~f0\" 2>nul\r\n"

            "exit /b 0\r\n"

        )

        updater_cmd.write_text(cmd_content, encoding="ascii")

        subprocess.Popen(["cmd.exe", "/c", str(updater_cmd)], creationflags=NO_WINDOW)

        self.destroy()



    def show_credits(self):
        notice = ROOT / "NOTICE.md"
        try:
            text = notice.read_text(encoding="utf-8")
        except OSError:
            text = "Credits are in NOTICE.md."

        win = tk.Toplevel(self)
        win.title(f"{BRAND} - {self.t('credits_btn')}")
        self._apply_window_icon(win)
        apply_dark_titlebar(win)
        win.configure(bg="#070E20")
        win.geometry("740x520")
        win.minsize(640, 420)
        win.transient(self)

        top_bar = tk.Frame(win, bg="#070E20", padx=10, pady=10)
        top_bar.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(top_bar, text="Sengoku Basara 4 PC — Timotius Edition:", bg="#070E20", fg="#FF4242", font=("Segoe UI Bold", 11)).pack(side="left", padx=(0, 10))
        
        btn_top_canvas = tk.Canvas(top_bar, width=170, height=32, bg="#070E20", bd=0, highlightthickness=0)
        btn_top_canvas.pack(side="left")
        CanvasButton(btn_top_canvas, 85, 16, 166, 28, text="⚡ GitHub Repository",
                     command=lambda: webbrowser.open("https://github.com/timotius/basara4-native-pc"), is_primary=True, lang=self.lang)

        box_frame = tk.Frame(win, bg="#070E20")
        box_frame.pack(fill="both", expand=True, padx=10, pady=10)
        box = tk.Text(box_frame, bg="#040814", fg="#FF5E5E", insertbackground="#FF5E5E", selectbackground="#1E3A6E",
                      selectforeground="#FFFFFF", wrap="word", relief="flat", padx=14, pady=12,
                      font=("Segoe UI", 10), highlightthickness=1, highlightbackground="#2563EB")
        scrollbar = ttk.Scrollbar(box_frame, orient="vertical", command=box.yview, style="Basara.Vertical.TScrollbar")
        box.configure(yscrollcommand=scrollbar.set)
        box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        box.insert("1.0", text)
        box.config(state="disabled")
        apply_dark_titlebar(win)
    def _deiconify(self):

        self.deiconify()



    def on_stop(self):

        self._stopped_by_user = True

        if self.proc and self.proc.poll() is None:

            try:

                log_launch(f"Stopping game process PID {self.proc.pid}")

                self.proc.kill()

            except Exception as e:

                log_launch(f"Error terminating process: {e}")



    def _poll(self):

        if self.proc and self.proc.poll() is not None:

            code = self.proc.returncode

            log_launch(f"Game process exited with returncode {code:#x} ({code})")

            self.proc = None

            self.busy = False

            self.play.config(state="normal")

            self.stop.config(state="disabled")

            if hasattr(self, "header_status_pill"):

                self.header_status_pill.set_status("ready", self.t("ready"))

            if code not in (0, None) and not getattr(self, "_stopped_by_user", False):

                self._deiconify()

                self._show_crash_dialog(code)

            if self.play_now:

                if code in (0, None) or getattr(self, "_stopped_by_user", False):

                    self.destroy()

                return

            err_msg = self.t("exited_with_code", code=f"{code & 0xFFFFFFFF:#x}") if (code not in (0, None) and not getattr(self, "_stopped_by_user", False)) else None

            self.status.config(text=err_msg if err_msg else self.t("closed"))

            self._load_ini_into_ui()

        self.after(500, self._poll)



    # ---- controller and files ----

    def map_pad(self, extra):

        exe = BIN / "basara4-pad-mapper.exe"

        if not exe.is_file():

            messagebox.showerror(self.t("err_runtime_missing"), str(exe))

            return

        env = os.environ.copy()

        env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")

        USER.mkdir(parents=True, exist_ok=True)



        if not MAPPING.exists() or MAPPING.stat().st_size == 0:

            MAPPING.write_text(DEFAULT_XINPUT_MAPPING, encoding="utf-8")



        runner_bat = USER / "run_pad_mapper.bat"

        extra_args_str = " ".join(f'"{a}"' for a in extra)

        bat_lines = [
            "@echo off",
            "chcp 65001 >nul",
            "title Sengoku Basara 4 - Gamepad Mapper (Timotius)",
            f'cd /d "{BIN}"',
            f'"{exe}" "{MAPPING}" {extra_args_str}',
            "echo.",
            "echo ==================================================",
            "echo [OK] Pemetaan stik selesai. Tekan tombol apa saja untuk menutup.",
            "pause >nul"
        ]
        try:
            runner_bat.write_text("\r\n".join(bat_lines) + "\r\n", encoding="utf-8")
        except Exception as e:
            log_debug(f"Failed to write pad mapper runner script: {e}")

        try:
            cmd_line = f'cmd.exe /c ""{runner_bat}""'
            subprocess.Popen(cmd_line, cwd=str(BIN), env=env, creationflags=0x00000010)
            self.status.config(text=self.t("pad_prompt"))
            self.after(3000, self._pad_text)

        except Exception as e:

            messagebox.showerror(self.t("control_gamepad_btn"), f"Failed to start controller mapper:\n{e}")



    def reset_map(self):

        if not messagebox.askyesno(self.t("reset_map"), self.t("confirm_reset_map")):

            return



        USER.mkdir(parents=True, exist_ok=True)

        if MAPPING.exists():

            try:

                shutil.copy2(MAPPING, str(MAPPING) + ".bak")

            except Exception as e:

                log_debug(f"Backup mapping error: {e}")



        try:

            MAPPING.write_text(DEFAULT_XINPUT_MAPPING, encoding="utf-8")

            self._pad_text()

            self.status.config(text=self.t("reset_map_success"))

            messagebox.showinfo(self.t("reset_map"), self.t("reset_map_success"))

        except Exception as e:

            messagebox.showerror(self.t("reset_map"), f"Failed to reset mapping:\n{e}")



    def open_gamepad_control_ui(self):

        """Interactive Gamepad Rebinding Modal allowing direct button remapping & presets."""

        win = tk.Toplevel(self)

        win.title(f"{BRAND} - {self.t('control_gamepad_btn')}")

        win.configure(bg=ROOT_BG)

        win.geometry("820x640")

        win.minsize(760, 560)

        win.grab_set()

        apply_dark_titlebar(win)
        self._apply_window_icon(win)



        # Parse active mapping

        mapping_text = DEFAULT_XINPUT_MAPPING.strip()

        if MAPPING.exists() and MAPPING.stat().st_size > 0:

            try:

                mapping_text = MAPPING.read_text(encoding="utf-8", errors="ignore").strip()

            except Exception:

                pass



        lines = [l for l in mapping_text.splitlines() if l.strip() and not l.startswith("#")]

        cur_line = lines[0] if lines else DEFAULT_XINPUT_MAPPING.splitlines()[0]

        tokens = cur_line.split(",")

        guid = tokens[0] if len(tokens) > 0 else "0300fa675e0400008e02000010017801"

        name = tokens[1] if len(tokens) > 1 else "Xbox 360 Controller"

        bindings = {}

        platform_str = "Windows"

        for t in tokens[2:]:

            if ":" in t:

                k, v = t.split(":", 1)

                if k == "platform":

                    platform_str = v

                else:

                    bindings[k] = v



        defaults = {

            "a": "b0", "b": "b1", "x": "b2", "y": "b3",

            "leftshoulder": "b4", "rightshoulder": "b5",

            "lefttrigger": "a2", "righttrigger": "a5",

            "back": "b7", "start": "b6",

            "leftstick": "b8", "rightstick": "b9",

            "dpup": "h0.1", "dpdown": "h0.4", "dpleft": "h0.8", "dpright": "h0.2",

            "leftx": "a0", "lefty": "a1", "rightx": "a3", "righty": "a4"

        }

        for k, v in defaults.items():

            if k not in bindings:

                bindings[k] = v



        header_frame = tk.Frame(win, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, bd=0, padx=16, pady=12)

        header_frame.pack(fill="x", padx=14, pady=(14, 8))



        tk.Label(header_frame, text="🎮 ATUR KONTROLER (GAMEPAD REBINDING)", bg=CARD_BG, fg=CRIMSON_HEADER, font=("Segoe UI Bold", 13)).pack(anchor="w")

        tk.Label(header_frame, text="Ubah binding tombol controller Anda secara langsung tanpa harus menjalankan wizard dari awal.", bg=CARD_BG, fg=FG, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 8))



        preset_bar = tk.Frame(header_frame, bg=CARD_BG)

        preset_bar.pack(fill="x")

        tk.Label(preset_bar, text="Pilihan Preset Cepat: ", bg=CARD_BG, fg=RED_PRIMARY, font=("Segoe UI Semibold", 9)).pack(side="left")



        body_frame = tk.Frame(win, bg=ROOT_BG)

        body_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        body_frame.columnconfigure(0, weight=1)

        body_frame.columnconfigure(1, weight=1)



        left_card = tk.Frame(body_frame, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, bd=0, padx=14, pady=10)

        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))



        tk.Label(left_card, text="⚔️ Tombol Aksi & Bahu", bg=CARD_BG, fg=CRIMSON_HEADER, font=("Segoe UI Bold", 10)).pack(anchor="w", pady=(0, 8))



        btn_options = [

            ("a", "A / ✕ Cross (Jump / Lompat)", ["b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7"]),

            ("b", "B / ◯ Circle (Basara Attack)", ["b1", "b0", "b2", "b3", "b4", "b5", "b6", "b7"]),

            ("x", "X / ◻ Square (Normal Attack)", ["b2", "b0", "b1", "b3", "b4", "b5", "b6", "b7"]),

            ("y", "Y / △ Triangle (Special Skill 1)", ["b3", "b0", "b1", "b2", "b4", "b5", "b6", "b7"]),

            ("leftshoulder", "L1 / LB (Guard / Tangkis)", ["b4", "b5", "a2", "a5", "b6", "b7"]),

            ("rightshoulder", "R1 / RB (Special Skill 2)", ["b5", "b4", "a5", "a2", "b6", "b7"]),

            ("lefttrigger", "L2 / LT (Special Skill 3)", ["a2", "b4", "a5", "b5", "b6", "b7"]),

            ("righttrigger", "R2 / RT (Drive Mode / Boost)", ["a5", "b5", "a2", "b4", "b6", "b7"])

        ]



        combos = {}

        for key, label, vals in btn_options:

            row = tk.Frame(left_card, bg=CARD_BG)

            row.pack(fill="x", pady=3)

            tk.Label(row, text=label, bg=CARD_BG, fg=FG, font=("Segoe UI", 8)).pack(side="left")

            cur_val = bindings.get(key, vals[0])

            if cur_val not in vals:

                vals = [cur_val] + vals

            var = tk.StringVar(value=cur_val)

            cb = ttk.Combobox(row, textvariable=var, values=vals, width=8, state="readonly")

            cb.pack(side="right")

            combos[key] = var



        right_card = tk.Frame(body_frame, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, bd=0, padx=14, pady=10)

        right_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))



        tk.Label(right_card, text="🕹️ Navigasi, Stik & Kamera", bg=CARD_BG, fg=CRIMSON_HEADER, font=("Segoe UI Bold", 10)).pack(anchor="w", pady=(0, 8))



        nav_options = [

            ("start", "Start / Options (Menu / Jeda)", ["b6", "b7", "b8", "b9"]),

            ("back", "Back / Select / Share (Taunt)", ["b7", "b6", "b8", "b9"]),

            ("leftstick", "L3 (Left Stick Click)", ["b8", "b9", "b6", "b7"]),

            ("rightstick", "R3 (Right Stick Click / In-game Menu)", ["b9", "b8", "b6", "b7"]),

            ("dpup", "D-Pad Atas / Up", ["h0.1", "b11", "b12"]),

            ("dpdown", "D-Pad Bawah / Down", ["h0.4", "b12", "b11"]),

            ("dpleft", "D-Pad Kiri / Left", ["h0.8", "b13", "b14"]),

            ("dpright", "D-Pad Kanan / Right", ["h0.2", "b14", "b13"]),

            ("rightx", "Kamera X (Horizontal Look)", ["a3", "a3~", "a0", "a2"]),

            ("righty", "Kamera Y (Vertical Look)", ["a4", "a4~", "a1", "a5"])

        ]



        for key, label, vals in nav_options:

            row = tk.Frame(right_card, bg=CARD_BG)

            row.pack(fill="x", pady=2)

            tk.Label(row, text=label, bg=CARD_BG, fg=FG, font=("Segoe UI", 8)).pack(side="left")

            cur_val = bindings.get(key, vals[0])

            if cur_val not in vals:

                vals = [cur_val] + vals

            var = tk.StringVar(value=cur_val)

            cb = ttk.Combobox(row, textvariable=var, values=vals, width=8, state="readonly")

            cb.pack(side="right")

            combos[key] = var



        def apply_preset_xbox():

            p = {"a": "b0", "b": "b1", "x": "b2", "y": "b3", "leftshoulder": "b4", "rightshoulder": "b5",

                 "lefttrigger": "a2", "righttrigger": "a5", "back": "b6", "start": "b7",

                 "leftstick": "b8", "rightstick": "b9", "rightx": "a3", "righty": "a4"}

            for k, v in p.items():

                if k in combos:

                    combos[k].set(v)



        def apply_preset_playstation():

            p = {"a": "b0", "b": "b1", "x": "b2", "y": "b3", "leftshoulder": "b4", "rightshoulder": "b5",

                 "lefttrigger": "a2", "righttrigger": "a5", "back": "b7", "start": "b6",

                 "leftstick": "b8", "rightstick": "b9", "rightx": "a3", "righty": "a4"}

            for k, v in p.items():

                if k in combos:

                    combos[k].set(v)



        def apply_preset_switch():

            p = {"a": "b1", "b": "b0", "x": "b3", "y": "b2", "leftshoulder": "b4", "rightshoulder": "b5",

                 "lefttrigger": "a2", "righttrigger": "a5", "back": "b6", "start": "b7",

                 "leftstick": "b8", "rightstick": "b9", "rightx": "a3", "righty": "a4"}

            for k, v in p.items():

                if k in combos:

                    combos[k].set(v)



        def toggle_invert_camera():

            cur_rx = combos["rightx"].get()

            cur_ry = combos["righty"].get()

            combos["rightx"].set("a3~" if cur_rx == "a3" else "a3")

            combos["righty"].set("a4~" if cur_ry == "a4" else "a4")



        ttk.Button(preset_bar, text="Xbox Default", command=apply_preset_xbox).pack(side="left", padx=3)

        ttk.Button(preset_bar, text="PlayStation DualShock", command=apply_preset_playstation).pack(side="left", padx=3)

        ttk.Button(preset_bar, text="Nintendo Switch", command=apply_preset_switch).pack(side="left", padx=3)

        ttk.Button(preset_bar, text="Invert Kamera", command=toggle_invert_camera).pack(side="left", padx=3)



        action_bar = tk.Frame(win, bg=ROOT_BG)

        action_bar.pack(fill="x", padx=14, pady=(0, 14))



        def save_and_close():

            for k, var in combos.items():

                bindings[k] = var.get()



            order = ["a", "b", "x", "y", "leftshoulder", "rightshoulder", "lefttrigger", "righttrigger",

                     "back", "start", "leftstick", "rightstick", "guide", "dpup", "dpdown", "dpleft", "dpright",

                     "leftx", "lefty", "rightx", "righty"]

            parts = [guid, name]

            for k in order:

                if k in bindings:

                    parts.append(f"{k}:{bindings[k]}")

            parts.append(f"platform:{platform_str}")

            new_line = ",".join(parts) + ",\n"



            try:

                USER.mkdir(parents=True, exist_ok=True)

                MAPPING.write_text(new_line, encoding="utf-8")

                (USER / "gamecontrollerdb.txt").write_text(new_line, encoding="utf-8")

                (ROOT / "gamecontrollerdb.txt").write_text(new_line, encoding="utf-8")

                self._pad_text()

                messagebox.showinfo("Control Gamepad", "Pemetaan kontroler berhasil disimpan ke gamepad_mapping.txt & gamecontrollerdb.txt!")

                win.destroy()

            except Exception as e:

                messagebox.showerror("Error", f"Gagal menyimpan pemetaan: {e}")



        ModernButton(action_bar, text="💾 Simpan Pemetaan (Save)", command=save_and_close,

                     is_primary=True, width=220, height=36, font=("Segoe UI Bold", 10)).pack(side="left", padx=(0, 8))



        ModernButton(action_bar, text="🔄 Reset Default", command=lambda: [self.reset_map(), win.destroy()],

                     is_primary=False, width=150, height=36).pack(side="left", padx=(0, 8))



        ModernButton(action_bar, text="🛠️ Hardware Wizard...", command=lambda: [self.map_pad([]), win.destroy()],

                     is_primary=False, width=170, height=36).pack(side="left", padx=(0, 8))



        ModernButton(action_bar, text="Tutup (Close)", command=win.destroy,

                     is_primary=False, width=120, height=36).pack(side="right")



    def open_analog_sensitivity_ui(self):

        """Analog stick deadzone & sensitivity calibration dialog."""

        win = tk.Toplevel(self)

        win.title(f"{BRAND} - {self.t('analog_sens_btn')}")

        win.configure(bg=ROOT_BG)

        win.geometry("580x440")

        win.minsize(520, 380)

        win.grab_set()

        apply_dark_titlebar(win)
        self._apply_window_icon(win)



        card = tk.Frame(win, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, bd=0, padx=16, pady=14)

        card.pack(fill="both", expand=True, padx=14, pady=14)



        tk.Label(card, text="🕹️ KALIBRASI SENSITIVITAS & DEADZONE ANALOG", bg=CARD_BG, fg=CRIMSON_HEADER, font=("Segoe UI Bold", 11)).pack(anchor="w")

        tk.Label(card, text="Atur batas mati (deadzone) dan kepekaan stik analog untuk gerakan karakter dan kamera.", bg=CARD_BG, fg=FG, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 12))



        deadzone_var = tk.IntVar(value=self.cfg.get("stick_deadzone", 10))

        r1 = tk.Frame(card, bg=CARD_BG)

        r1.pack(fill="x", pady=6)

        tk.Label(r1, text="Deadzone Stik Kiri (Gerak Karakter):", bg=CARD_BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")

        lbl_dz = tk.Label(r1, text=f"{deadzone_var.get()}%", bg=CARD_BG, fg=RED_PRIMARY, font=("Segoe UI Bold", 9), width=5)

        lbl_dz.pack(side="right")

        s1 = ttk.Scale(card, from_=5, to=30, variable=deadzone_var, command=lambda v: lbl_dz.config(text=f"{int(float(v))}%"))

        s1.pack(fill="x", pady=(0, 8))



        cam_deadzone_var = tk.IntVar(value=self.cfg.get("cam_deadzone", 8))

        r2 = tk.Frame(card, bg=CARD_BG)

        r2.pack(fill="x", pady=6)

        tk.Label(r2, text="Deadzone Stik Kanan (Kamera):", bg=CARD_BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")

        lbl_cdz = tk.Label(r2, text=f"{cam_deadzone_var.get()}%", bg=CARD_BG, fg=RED_PRIMARY, font=("Segoe UI Bold", 9), width=5)

        lbl_cdz.pack(side="right")

        s2 = ttk.Scale(card, from_=5, to=30, variable=cam_deadzone_var, command=lambda v: lbl_cdz.config(text=f"{int(float(v))}%"))

        s2.pack(fill="x", pady=(0, 8))



        sens_var = tk.IntVar(value=self.cfg.get("cam_sensitivity", 100))

        r3 = tk.Frame(card, bg=CARD_BG)

        r3.pack(fill="x", pady=6)

        tk.Label(r3, text="Kepekaan Kamera (Sensitivity):", bg=CARD_BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")

        lbl_sens = tk.Label(r3, text=f"{sens_var.get()}%", bg=CARD_BG, fg=RED_PRIMARY, font=("Segoe UI Bold", 9), width=5)

        lbl_sens.pack(side="right")

        s3 = ttk.Scale(card, from_=50, to=200, variable=sens_var, command=lambda v: lbl_sens.config(text=f"{int(float(v))}%"))

        s3.pack(fill="x", pady=(0, 12))



        act = tk.Frame(card, bg=CARD_BG)

        act.pack(side="bottom", fill="x")



        def save_sens():

            self.cfg["stick_deadzone"] = int(deadzone_var.get())

            self.cfg["cam_deadzone"] = int(cam_deadzone_var.get())

            self.cfg["cam_sensitivity"] = int(sens_var.get())

            save_config(self.cfg)

            messagebox.showinfo("Sensitivitas Analog", "Pengaturan sensitivitas stik berhasil disimpan!")

            win.destroy()



        ModernButton(act, text="💾 Simpan", command=save_sens, is_primary=True, width=120, height=34).pack(side="left", padx=(0, 6))

        ModernButton(act, text="🕹️ Calibrate Hardware...", command=lambda: [self.map_pad(["--sticks"]), win.destroy()],

                     is_primary=False, width=180, height=34).pack(side="left", padx=(0, 6))

        ModernButton(act, text="Tutup", command=win.destroy, is_primary=False, width=100, height=34).pack(side="right")





    def open_log(self):

        if LOG.exists() and LOG.stat().st_size > 0:

            os.startfile(LOG)

        elif LAUNCH_DEBUG_LOG.exists() and LAUNCH_DEBUG_LOG.stat().st_size > 0:

            os.startfile(LAUNCH_DEBUG_LOG)

        elif DEBUG_LOG.exists():

            os.startfile(DEBUG_LOG)

        else:

            messagebox.showinfo(self.t("open_log"), "No log yet. Start the game first.")



    def open_audio_log(self):

        if AUDIO_LOG.exists():

            os.startfile(AUDIO_LOG)

        else:

            messagebox.showinfo(self.t("open_audio_log"), "No audio log yet. Tick Audio debug log, then start the game.")



    def open_saves(self):

        path = USER / "savedata"

        path.mkdir(parents=True, exist_ok=True)

        os.startfile(path)



    def _close(self):

        if self.proc and self.proc.poll() is None:

            if not messagebox.askyesno("Sengoku Basara 4", self.t("confirm_close")):

                return

            self.proc.kill()

        try:

            self._collect()

        except Exception:

            pass

        self.destroy()





if __name__ == "__main__":

    Launcher(play_now="--play" in sys.argv).mainloop()

