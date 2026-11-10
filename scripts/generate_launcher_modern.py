"""Generate modernized Sengoku Basara 4 launcher with flipped layout and glassmorphism."""
import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

launcher_code = '''"""Basara 4 PC Launcher - by Timotius.

Next-Gen Sengoku Basara 4 Sumeragi (PS4, CUSA01159) Native PC Launcher.
Powered by Ponytail Wrapper Runtime & REA Engine.
Modernized Glassmorphism UI/UX with Flipped Dual-Column Layout.
"""
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
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
GITHUB_REPO = "Timotiusconnect/basara4-native-pc"
Timotius = "#E0526A"

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
        "tail_context": "\\n".join(tail_lines),
        "total_lines": len(lines)
    }


def parse_version(tag):
    nums = re.findall(r"\\d+", str(tag))
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
    "guide:b10,dpup:h0.1,dpdown:h0.4,dpleft:h0.8,dpright:h0.2,leftx:a0,lefty:a1,rightx:a3~,righty:a4,platform:Windows,\\n"
    "xinput,XInput Controller,a:b0,b:b1,x:b2,y:b3,leftshoulder:b4,rightshoulder:b5,lefttrigger:a2,"
    "righttrigger:a5,back:b6,start:b7,leftstick:b8,rightstick:b9,guide:b10,dpup:h0.1,dpdown:h0.4,"
    "dpleft:h0.8,dpright:h0.2,leftx:a0,lefty:a1,rightx:a3,righty:a4,platform:Windows,\\n"
)
AUDIO_LOG = USER / "audio_debug.log"
DEBUG_LOG = USER / "debug_launch.log"
LAUNCH_DEBUG_LOG = USER / "launch_debug.log"
AUDIO_WAV = USER / "audio_wav"
STAMP = OUT / "prepared.json"
LOCALES_PATH = ROOT / "launcher" / "locales.json"
DEFAULT_DLC_DIR = ROOT.parent / "DLC"
if not DEFAULT_DLC_DIR.is_dir():
    DEFAULT_DLC_DIR = USER / "dlc"

WAV_WARNING = (
    "WAV capture saves the final mix and every long voice as uncompressed audio in user\\\\audio_wav: "
    "about 70 MB per minute, up to 3 GB for one session.\\n\\n"
    "Use it only to find an audio problem, and delete the files afterwards.\\n\\n"
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
    """The audio captures an earlier session left in user\\audio_wav: (files, total bytes)."""
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
            f.write(line + "\\n")
    except Exception:
        pass


def log_launch(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [BOOT] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        USER.mkdir(parents=True, exist_ok=True)
        with open(LAUNCH_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\\n")
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\\n")
    except Exception:
        pass


def get_resource_path(name):
    """Find a resource file checking _MEIPASS, ROOT/launcher, ROOT, and script dir."""
    if hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / name
        if p.is_file():
            return p
    for folder in [ROOT / "launcher", ROOT, Path(__file__).resolve().parent]:
        p = folder / name
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
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk
    log_debug("Pillow (PIL) successfully imported")
except ImportError as e:
    Image = ImageDraw = None
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
                    name = p.deviceName.decode("utf-8", errors="replace").strip("\\x00")
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

# Sengoku Basara Glassmorphism Luxury Dark Samurai Palette
ROOT_BG = "#0E0C10"
CARD_BG = "#19141C"
CARD_BORDER = "#008CFF"
CARD_BORDER_GLOW = "#008CFF"
GOLD = "#D32F2F"
GOLD_ACCENT = "#C02626"
GOLD_METALLIC = "#E53935"
RED_PRIMARY = "#D32F2F"
RED_DARK = "#8B0000"
RED_HOVER = "#E53935"
RED_PRESSED = "#B71C1C"
FG = "#F3EFE6"
MUTED = "#8D8374"
HEADER_BG = "#141017"
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


def load_locales():
    """Load localization dictionary from JSON or fallback to defaults."""
    path = get_resource_path("locales.json")
    if path and path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log_debug(f"Failed to parse locales.json: {e}")
    return {}


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
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


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
                return f"{name} failed (exit {result.returncode}). See user\\\\prepare.log"
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
        return f"content_profile.py failed (exit {result.returncode}). See user\\\\prepare.log"
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


# Button Texture Cache to avoid redundant PIL image generation during motion
_BTN_CACHE = {}


def get_cached_btn_img(w, h, is_primary, state):
    key = (w, h, is_primary, state)
    if key in _BTN_CACHE:
        return _BTN_CACHE[key]
    if Image is None or ImageDraw is None:
        return None

    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    radius = 10 if not is_primary else 12

    if is_primary:
        # AAA Ruby-Red to Crimson Gradient with Gold Wireline Border
        if state == "hover":
            c1, c2 = (229, 57, 53), (160, 0, 0)
            b_col = (255, 230, 128, 255)
        elif state == "pressed":
            c1, c2 = (183, 28, 28), (107, 0, 0)
            b_col = (218, 165, 32, 255)
        elif state == "disabled":
            c1, c2 = (46, 30, 30), (31, 20, 20)
            b_col = (58, 42, 42, 255)
        else:
            c1, c2 = (211, 47, 47), (139, 0, 0)
            b_col = (255, 215, 0, 255)

        for y in range(h):
            for x in range(w):
                t = (x / max(w, 1) * 0.35) + (y / max(h, 1) * 0.65)
                r = int(c1[0] + (c2[0] - c1[0]) * t)
                g = int(c1[1] + (c2[1] - c1[1]) * t)
                b = int(c1[2] + (c2[2] - c1[2]) * t)
                im.putpixel((x, y), (r, g, b, 255))

        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)
        im.putalpha(mask)

        # Metallic Gold Border
        ImageDraw.Draw(im).rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, outline=b_col, width=1)
    else:
        # Sleek Dark Pill Button
        if state == "hover":
            fill_col = (44, 36, 50, 255)
            b_col = (229, 184, 0, 230)
        elif state == "pressed":
            fill_col = (28, 22, 32, 255)
            b_col = (255, 215, 0, 255)
        elif state == "disabled":
            fill_col = (24, 20, 27, 255)
            b_col = (45, 38, 48, 160)
        else:
            fill_col = (34, 28, 38, 255)
            b_col = (68, 55, 74, 200)

        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=fill_col, outline=b_col, width=1)

    photo = ImageTk.PhotoImage(im)
    _BTN_CACHE[key] = photo
    return photo


class ModernButton(tk.Canvas):
    """Modern AAA Gaming Button with gradient, glow, metallic borders, and micro-interactions."""
    def __init__(self, parent, text="", command=None, width=120, height=36,
                 is_primary=False, state="normal", font=("Segoe UI Semibold", 10), bg_color=CARD_BG):
        super().__init__(parent, width=width, height=height, bg=bg_color,
                         highlightthickness=0, bd=0, cursor="hand2" if state == "normal" else "arrow")
        self.text = text
        self.command = command
        self.w = width
        self.h = height
        self.is_primary = is_primary
        self.state_mode = state
        self.font = font
        self.bg_color = bg_color

        self.current_step = 0
        self.max_steps = 6
        self.hovered = False
        self.pressed = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.render()

    def _on_enter(self, event):
        if self.state_mode != "normal":
            return
        self.hovered = True
        self.config(cursor="hand2")
        self._animate()

    def _on_leave(self, event):
        if self.state_mode != "normal":
            return
        self.hovered = False
        self.pressed = False
        self.config(cursor="arrow")
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
        if self.hovered and self.current_step < self.max_steps:
            self.current_step += 1
            self.render()
            self.after(16, self._animate)
        elif not self.hovered and self.current_step > 0:
            self.current_step -= 1
            self.render()
            self.after(16, self._animate)

    def config(self, **kwargs):
        if "state" in kwargs:
            self.state_mode = kwargs.pop("state")
            self.config(cursor="hand2" if self.state_mode == "normal" else "arrow")
        if "text" in kwargs:
            self.text = kwargs.pop("text")
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        super().config(**kwargs)
        self.render()

    def render(self):
        self.delete("all")
        t = self.current_step / self.max_steps
        y_offset = -2 * t if not self.pressed else 1

        state_key = "disabled" if self.state_mode == "disabled" else ("pressed" if self.pressed else ("hover" if self.hovered else "normal"))

        # Drop shadow glow for primary button on hover
        if self.is_primary and self.hovered and self.state_mode == "normal":
            radius = 12
            x0, y0 = 1, 1 + y_offset
            x1, y1 = self.w - 1, self.h + 2 + y_offset
            self.create_polygon(
                x0 + radius, y0 - 1, x1 - radius, y0 - 1,
                x1 + 1, y0, x1 + 2, y1 - radius,
                x1 - radius, y1 + 1, x0 + radius, y1 + 1,
                x0 - 1, y1, x0 - 1, y0 + radius,
                fill="#4A1212", outline="", smooth=True
            )

        btn_img = get_cached_btn_img(self.w - 4, self.h - 4, self.is_primary, state_key)
        if btn_img:
            self._img_ref = btn_img
            self.create_image(self.w // 2, (self.h // 2) + y_offset, image=btn_img)
        else:
            # Fallback simple shape
            self.create_rectangle(2, 2 + y_offset, self.w - 2, self.h - 2 + y_offset, fill=RED_PRIMARY if self.is_primary else "#221C26", outline=GOLD)

        if self.state_mode == "disabled":
            fg_col = "#6E6260"
        elif self.is_primary:
            fg_col = "#FFFFFF"
        else:
            fg_col = GOLD if (self.hovered and self.state_mode == "normal") else FG

        self.create_text(
            self.w / 2, (self.h / 2) + y_offset,
            text=self.text, fill=fg_col, font=self.font
        )


class StatusPill(tk.Canvas):
    """Modern live status pill with pulsing indicator dot and glowing outline."""
    def __init__(self, parent, bg_color=HEADER_BG, width=170, height=30):
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0, bd=0)
        self.w = width
        self.h = height
        self.state_mode = "ready"
        self.text = "Siap dimainkan"
        self.render()

    def set_status(self, state, text):
        self.state_mode = state
        self.text = text
        self.render()

    def render(self):
        self.delete("all")
        if self.state_mode == "ready":
            pill_bg, border_col, dot_col, text_col = "#112416", "#22C55E", "#22C55E", "#4ADE80"
        elif self.state_mode == "starting":
            pill_bg, border_col, dot_col, text_col = "#2A230E", "#D32F2F", "#D32F2F", "#FACC15"
        elif self.state_mode == "running":
            pill_bg, border_col, dot_col, text_col = "#281C0E", "#D32F2F", "#D32F2F", "#FDE047"
        else:
            pill_bg, border_col, dot_col, text_col = "#281216", "#EF4444", "#EF4444", "#F87171"

        r = 8
        self.create_polygon(
            r + 2, 2, self.w - r - 2, 2,
            self.w - 2, r + 2, self.w - 2, self.h - r - 2,
            self.w - r - 2, self.h - 2, r + 2, self.h - 2,
            2, self.h - r - 2, 2, r + 2,
            fill=pill_bg, outline=border_col, width=1, smooth=True
        )

        # Glowing dot
        self.create_oval(14, (self.h // 2) - 4, 22, (self.h // 2) + 4, fill=dot_col, outline="")
        self.create_text(
            (self.w // 2) + 6, self.h // 2,
            text=self.text, fill=text_col, font=("Segoe UI Semibold", 8)
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
            fill="#120F14", outline=CARD_BORDER, width=1, smooth=True
        )

        if self.current_lang == "en":
            self.create_polygon(
                5, 4, 46, 4, 48, 6, 48, 26, 46, 28, 5, 28, 3, 26, 3, 6,
                fill=RED_PRIMARY, outline=GOLD_ACCENT, width=1, smooth=True
            )
            en_color = "#FFFFFF"
            id_color = MUTED if self.hovered_side != "id" else FG
        else:
            self.create_polygon(
                48, 4, 91, 4, 93, 6, 93, 26, 91, 28, 48, 28, 46, 26, 46, 6,
                fill=RED_PRIMARY, outline=GOLD_ACCENT, width=1, smooth=True
            )
            id_color = "#FFFFFF"
            en_color = MUTED if self.hovered_side != "en" else FG

        self.create_text(25, 16, text="EN", fill=en_color, font=("Segoe UI Bold", 9))
        self.create_text(71, 16, text="ID", fill=id_color, font=("Segoe UI Bold", 9))


class Launcher(tk.Tk):
    def __init__(self, play_now=False):
        log_debug("Launcher __init__ started")
        super().__init__()
        try:
            self.cfg = load_config()
            log_debug(f"Loaded config from {CONFIG}")
        except Exception as e:
            log_debug(f"Error loading config: {e}\\n{traceback.format_exc()}")
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

        self.title(f"{self.t('app_title')} · {BRAND} by {AUTHOR}")
        self.configure(bg=ROOT_BG)
        self.geometry("1100x670")
        self.minsize(1040, 620)

        icon_path = get_resource_path("basara4.ico")
        if icon_path and icon_path.is_file():
            try:
                self.iconbitmap(str(icon_path))
                log_debug(f"Window icon loaded: {icon_path}")
            except Exception as e:
                log_debug(f"Could not load iconbitmap: {e}")

        try:
            self._style()
            log_debug("Styles initialized")
        except Exception as e:
            log_debug(f"Error initializing styles: {e}\\n{traceback.format_exc()}")

        try:
            self._art()
            log_debug("Artwork initialized")
        except Exception as e:
            log_debug(f"Error initializing artwork: {e}\\n{traceback.format_exc()}")

        try:
            self._build()
            log_debug("Flipped dual-column UI layout built successfully")
        except Exception as e:
            log_debug(f"Error building UI layout: {e}\\n{traceback.format_exc()}")

        try:
            self._load_ini_into_ui()
            log_debug("INI loaded into UI successfully")
        except Exception as e:
            log_debug(f"Error loading INI into UI: {e}\\n{traceback.format_exc()}")

        try:
            self._refresh_image_label()
        except Exception as e:
            log_debug(f"Error refreshing image label: {e}\\n{traceback.format_exc()}")

        try:
            apply_dark_titlebar(self)
            self.deiconify()
            self.update_idletasks()
            self.lift()
            log_debug("Dark titlebar applied & window mapped")
        except Exception as e:
            log_debug(f"Error finalizing window setup: {e}\\n{traceback.format_exc()}")

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
        """Dynamically switch between English and Bahasa Indonesia."""
        if lang not in ("en", "id"):
            return
        self.lang = lang
        self.cfg["language"] = lang
        save_config(self.cfg)
        log_debug(f"Language switched to: {lang}")

        self.title(f"{self.t('app_title')} · {BRAND} by {AUTHOR}")
        if hasattr(self, "lang_toggle"):
            self.lang_toggle.set_language(lang)
        if hasattr(self, "header_title"):
            self.header_title.config(text=f"{self.t('app_subtitle')} · {self.t('app_title').upper()}")
        if hasattr(self, "header_status_pill"):
            state = "running" if (self.proc and self.proc.poll() is None) else ("starting" if self.busy else "ready")
            text = self.t("running") if state == "running" else (self.t("starting") if state == "starting" else self.t("ready"))
            self.header_status_pill.set_status(state, text)
        if hasattr(self, "play"):
            self.play.config(text=self.t("play_btn"))
        if hasattr(self, "stop"):
            self.stop.config(text=self.t("stop_btn"))
        if hasattr(self, "credits_btn"):
            self.credits_btn.config(text=self.t("credits_btn"))
        if hasattr(self, "check_update_btn"):
            self.check_update_btn.config(text="Cek Update" if lang == "id" else "Check Update")
        if hasattr(self, "card_game_title"):
            self.card_game_title.config(text=f"📁 {self.t('section_game')}")
        if hasattr(self, "game_folder_lbl"):
            self.game_folder_lbl.config(text=self.t("game_folder"))
        if hasattr(self, "browse_btn"):
            self.browse_btn.config(text=self.t("browse_btn"))
        if hasattr(self, "card_display_title"):
            self.card_display_title.config(text=f"🖥️ {self.t('section_display')}")
        if hasattr(self, "card_ctrl_title"):
            self.card_ctrl_title.config(text=f"🎮 {self.t('section_controller')}")
        if hasattr(self, "lbl_win_size"):
            self.lbl_win_size.config(text=self.t("window_size"))
        if hasattr(self, "lbl_upscale"):
            self.lbl_upscale.config(text=self.t("upscaling"))
        if hasattr(self, "lbl_fps"):
            self.lbl_fps.config(text=self.t("frame_limit"))
        if hasattr(self, "lbl_aniso"):
            self.lbl_aniso.config(text=self.t("anisotropic"))
        if hasattr(self, "res_hint"):
            self.res_hint.config(text=self.t("res_hint"))
        if hasattr(self, "fps_hint"):
            self.fps_hint.config(text=self.t("fps_hint"))
        if hasattr(self, "menu_hint"):
            self.menu_hint.config(text=self.t("ingame_menu"))
        if hasattr(self, "btn_map_pad"):
            self.btn_map_pad.config(text=self.t("map_pad"))
        if hasattr(self, "btn_map_sticks"):
            self.btn_map_sticks.config(text=self.t("map_sticks"))
        if hasattr(self, "btn_reset_map"):
            self.btn_reset_map.config(text=self.t("reset_map"))
        if hasattr(self, "btn_open_log"):
            self.btn_open_log.config(text=self.t("open_log"))
        if hasattr(self, "btn_open_saves"):
            self.btn_open_saves.config(text=self.t("open_saves"))
        if hasattr(self, "btn_open_audio_log"):
            self.btn_open_audio_log.config(text=self.t("open_audio_log"))
        if hasattr(self, "lbl_gpu"):
            self.lbl_gpu.config(text=self.t("gpu_select"))
        if hasattr(self, "chk_vsync"):
            self.chk_vsync.config(text=self.t("vsync"))
        if hasattr(self, "chk_rcas"):
            self.chk_rcas.config(text=self.t("rcas"))
        if hasattr(self, "chk_audio"):
            self.chk_audio.config(text=self.t("audio_log"))
        if hasattr(self, "chk_wav"):
            self.chk_wav.config(text=self.t("wav_capture"))
        if hasattr(self, "lbl_input_mode"):
            self.lbl_input_mode.config(text=self.t("input_mode"))
        if hasattr(self, "rb_controller"):
            self.rb_controller.config(text=self.t("input_mode_controller"))
        if hasattr(self, "rb_kbm"):
            self.rb_kbm.config(text=self.t("input_mode_kbm"))
        if hasattr(self, "btn_kbm"):
            self.btn_kbm.config(text=self.t("kbm_controls_btn"))
        if hasattr(self, "btn_cheats"):
            self.btn_cheats.config(text=self.t("cheats_btn"))
        if hasattr(self, "btn_dlc"):
            self.btn_dlc.config(text=self.t("dlc_btn"))

        if hasattr(self, "radio_buttons"):
            for btn, key in self.radio_buttons:
                btn.config(text=self.t(f"mode_{key}"))

        self._refresh_image_label()
        self._pad_text()

    # ---- look & styles ----
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure(".", background=CARD_BG, foreground=FG, fieldbackground=CARD_BG,
                    bordercolor=CARD_BORDER, lightcolor=CARD_BG, darkcolor=CARD_BG,
                    font=("Segoe UI", 9))
        s.configure("TFrame", background=ROOT_BG)
        s.configure("Card.TFrame", background=CARD_BG)
        s.configure("TLabel", background=ROOT_BG, foreground=FG)
        s.configure("Card.TLabel", background=CARD_BG, foreground=FG)
        s.configure("Muted.TLabel", background=CARD_BG, foreground=MUTED, font=("Segoe UI", 8))
        s.configure("Head.TLabel", background=ROOT_BG, foreground=GOLD, font=("Segoe UI Bold", 11))
        s.configure("CardHead.TLabel", background=CARD_BG, foreground=GOLD, font=("Segoe UI Bold", 10))

        s.configure("TRadiobutton", background=CARD_BG, foreground=FG, font=("Segoe UI", 9))
        s.configure("TCheckbutton", background=CARD_BG, foreground=FG, font=("Segoe UI", 9))
        s.map("TRadiobutton",
              background=[("active", CARD_BG)],
              foreground=[("active", GOLD), ("selected", GOLD)])
        s.map("TCheckbutton",
              background=[("active", CARD_BG)],
              foreground=[("active", GOLD), ("selected", GOLD)])

        s.configure("TCombobox", arrowcolor=GOLD, background=CARD_BG, fieldbackground="#151118",
                    foreground=FG, bordercolor=CARD_BORDER, lightcolor=CARD_BORDER, darkcolor=CARD_BORDER,
                    padding=4)
        s.map("TCombobox",
              fieldbackground=[("readonly", "#151118")],
              foreground=[("readonly", FG)],
              selectbackground=[("readonly", RED_PRIMARY)],
              selectforeground=[("readonly", "#FFFFFF")])
        self.option_add("*TCombobox*Listbox.background", "#1A1520")
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", RED_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))

        s.configure("TEntry", fieldbackground="#151118", foreground=FG, bordercolor=CARD_BORDER,
                    lightcolor=CARD_BORDER, darkcolor=CARD_BORDER, padding=5)

        s.configure("Vertical.TScrollbar", background="#2C272C", troughcolor="#141216",
                    bordercolor=CARD_BORDER, arrowcolor=GOLD_ACCENT)

    def _find_launcher_bg(self):
        """Locate launcherbg in project root, launcher dir, or sys._MEIPASS (.png, .jpg, .webp)."""
        candidates = [
            "Launcherbg.png", "launcherbg.png", "Launcherbg.jpg", "launcherbg.jpg",
            "Launcherbg.webp", "launcherbg.webp"
        ]
        search_dirs = [
            ROOT,
            ROOT / "launcher",
            Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else None,
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
        self.cover = self.bg_raw = self.bg_img = None
        if Image is None:
            return
        if self.cfg.get("game"):
            sys_dir = Path(self.cfg["game"]) / "sce_sys"
            try:
                icon_p = sys_dir / "icon0.png"
                if icon_p.is_file():
                    self.cover = ImageTk.PhotoImage(Image.open(icon_p).convert("RGB").resize((240, 240)))
            except Exception as e:
                log_debug(f"Could not load icon0.png: {e}")

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

        if self.bg_raw is not None:
            self._update_bg(1100, 670)

    def _update_bg(self, w=None, h=None):
        """Render Date Masamune artwork with blur(14px), brightness(0.65), and 135deg glassmorphism gradient."""
        if self.bg_raw is None or Image is None or ImageDraw is None:
            return
        w = max(w or self.winfo_width(), 1040)
        h = max(h or self.winfo_height(), 620)
        try:
            iw, ih = self.bg_raw.size
            scale = max(w / iw, h / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            resized = self.bg_raw.resize((nw, nh), Image.Resampling.BILINEAR)
            left = (nw - w) // 2
            top = (nh - h) // 2
            cropped = resized.crop((left, top, left + w, top + h))

            # Glassmorphism filter: blur(14px) and brightness(0.65)
            blurred = cropped.filter(ImageFilter.GaussianBlur(14))
            darkened = ImageEnhance.Brightness(blurred).enhance(0.65)

            # High-performance 135deg vignette gradient: linear-gradient(135deg, rgba(18, 14, 22, 0.88), rgba(10, 8, 14, 0.94))
            grad_small = Image.new("RGBA", (64, 64))
            draw_small = ImageDraw.Draw(grad_small)
            for gy in range(64):
                for gx in range(64):
                    t = (gx + gy) / 128.0
                    r = int(18 + (10 - 18) * t)
                    g = int(14 + (8 - 14) * t)
                    b = int(22 + (14 - 22) * t)
                    a = int(224 + (240 - 224) * t)
                    draw_small.point((gx, gy), fill=(r, g, b, a))

            grad = grad_small.resize((w, h), Image.Resampling.BILINEAR)
            final = Image.alpha_composite(darkened, grad)

            self.bg_img = ImageTk.PhotoImage(final.convert("RGB"))
            if hasattr(self, "bg_label") and self.bg_label:
                self.bg_label.configure(image=self.bg_img, bg=ROOT_BG)
        except Exception as e:
            log_debug(f"Error updating glassmorphism background: {e}")

    def _on_configure(self, event):
        if event.widget != self:
            return
        w, h = event.width, event.height
        if getattr(self, "_last_size", None) == (w, h):
            return
        self._last_size = (w, h)
        if hasattr(self, "_bg_timer") and self._bg_timer:
            self.after_cancel(self._bg_timer)
        self._bg_timer = self.after(50, lambda: self._update_bg(w, h))

    # ---- Modernized Flipped Asymmetric Dual-Column Layout ----
    def _build(self):
        # 1. Seamless Glassmorphism Root Viewport
        self.bg_label = tk.Label(self, bd=0, bg=ROOT_BG)
        if self.bg_img:
            self.bg_label.configure(image=self.bg_img)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # 2. Modern Transparent Top Header Bar
        header = tk.Frame(self, bg=HEADER_BG, height=52, highlightthickness=1,
                          highlightbackground=CARD_BORDER, bd=0)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        header_inner = tk.Frame(header, bg=HEADER_BG)
        header_inner.pack(fill="both", expand=True, padx=20)

        # Left: Game Title with Stylized Crest
        left_h = tk.Frame(header_inner, bg=HEADER_BG)
        left_h.pack(side="left", fill="y")

        self.header_title = tk.Label(
            left_h,
            text=f"{self.t('app_subtitle')} · {self.t('app_title').upper()}",
            bg=HEADER_BG, fg=GOLD, font=("Segoe UI Bold", 11)
        )
        self.header_title.pack(side="left", pady=14)

        # Center/Left: Live Status Pill
        self.header_status_pill = StatusPill(left_h, bg_color=HEADER_BG, width=160, height=28)
        self.header_status_pill.pack(side="left", padx=16, pady=11)
        self.header_status_pill.set_status("ready", self.t("ready"))

        # Right: Language Switcher Toggle
        self.lang_toggle = LanguageToggle(header_inner, current_lang=self.lang,
                                          on_change=self.set_language, bg_color=HEADER_BG)
        self.lang_toggle.pack(side="right", pady=10)

        # 3. Main Central Container (Flipped Asymmetric Dual-Column)
        self.main_container = tk.Frame(self, bg="")
        self.main_container.pack(fill="both", expand=True, padx=18, pady=14)

        # Layout Reorientation: Column 0 (Left) = Wide Settings (Flex-1) | Column 1 (Right) = Hero Panel (~340px)
        self.main_container.columnconfigure(0, weight=1)
        self.main_container.columnconfigure(1, weight=0)
        self.main_container.rowconfigure(0, weight=1)

        # =====================================================================
        # LEFT COLUMN (WIDE / FLEX-1): MAIN SETTINGS & UTILITIES PANEL
        # =====================================================================
        settings_panel = tk.Frame(self.main_container, bg="")
        settings_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        settings_panel.columnconfigure(0, weight=1)

        # CARD 1: GAME LOCATION
        card_game = tk.Frame(settings_panel, bg=CARD_BG, highlightbackground=CARD_BORDER,
                             highlightthickness=1, bd=0, padx=16, pady=12)
        card_game.pack(fill="x", pady=(0, 10))
        card_game.columnconfigure(1, weight=1)

        self.card_game_title = tk.Label(card_game, text=f"📁 {self.t('section_game')}", bg=CARD_BG, fg=GOLD,
                                        font=("Segoe UI Bold", 10))
        self.card_game_title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.game_var = tk.StringVar(value=self.cfg["game"])
        self.game_var.trace_add("write", lambda *_: self._refresh_image_label())

        self.game_folder_lbl = ttk.Label(card_game, text=self.t("game_folder"), style="Card.TLabel")
        self.game_folder_lbl.grid(row=1, column=0, sticky="w", padx=(0, 8))

        self.game_entry = ttk.Entry(card_game, textvariable=self.game_var)
        self.game_entry.grid(row=1, column=1, sticky="ew", padx=4)

        self.browse_btn = ModernButton(card_game, text=self.t("browse_btn"), command=self._browse, is_primary=False,
                                       width=110, height=30, font=("Segoe UI", 9), bg_color=CARD_BG)
        self.browse_btn.grid(row=1, column=2, padx=(4, 0))

        self.image_label = ttk.Label(card_game, text="", style="Muted.TLabel")
        self.image_label.grid(row=2, column=1, sticky="w", padx=8, pady=(4, 0))

        # CARD 2: DISPLAY & GRAPHICS
        card_display = tk.Frame(settings_panel, bg=CARD_BG, highlightbackground=CARD_BORDER,
                                highlightthickness=1, bd=0, padx=16, pady=12)
        card_display.pack(fill="x", pady=(0, 10))
        card_display.columnconfigure(1, weight=1)
        card_display.columnconfigure(3, weight=1)

        self.card_display_title = tk.Label(card_display, text=f"🖥️ {self.t('section_display')}", bg=CARD_BG, fg=GOLD,
                                           font=("Segoe UI Bold", 10))
        self.card_display_title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        # Display Mode Radios
        self.mode_var = tk.StringVar(value=self.cfg["display_mode"])
        modes_frame = tk.Frame(card_display, bg=CARD_BG)
        modes_frame.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 8))

        self.radio_buttons = []
        for label, key in DISPLAY_MODES:
            rb = ttk.Radiobutton(modes_frame, text=self.t(f"mode_{key}"), value=key, variable=self.mode_var)
            rb.pack(side="left", padx=(0, 16))
            self.radio_buttons.append((rb, key))

        # Row 2: GPU Selection Dropdown
        self.lbl_gpu = ttk.Label(card_display, text=self.t("gpu_select"), style="Card.TLabel")
        self.lbl_gpu.grid(row=2, column=0, sticky="w", pady=4)
        self.gpu_names = [name for _, name, _ in SYSTEM_GPUS]
        cur_gpu_idx = self.cfg.get("gpu_index", -1)
        cur_gpu_name = next((name for idx, name, _ in SYSTEM_GPUS if idx == cur_gpu_idx), self.gpu_names[0])
        self.gpu_var = tk.StringVar(value=cur_gpu_name)
        self.gpu_combo = ttk.Combobox(card_display, textvariable=self.gpu_var, state="readonly", width=42,
                                      values=self.gpu_names)
        self.gpu_combo.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=4)

        # Row 3: Frame limit & Anisotropic
        self.lbl_fps = ttk.Label(card_display, text=self.t("frame_limit"), style="Card.TLabel")
        self.lbl_fps.grid(row=3, column=0, sticky="w", pady=4)
        self.fps_var = tk.StringVar()
        self.fps_combo = ttk.Combobox(card_display, textvariable=self.fps_var, state="readonly", width=22,
                                      values=[n for n, _ in FPS_LIMITS])
        self.fps_combo.grid(row=3, column=1, sticky="ew", padx=(8, 18), pady=4)

        self.lbl_aniso = ttk.Label(card_display, text=self.t("anisotropic"), style="Card.TLabel")
        self.lbl_aniso.grid(row=3, column=2, sticky="w", pady=4)
        self.aniso_var = tk.StringVar()
        self.aniso_combo = ttk.Combobox(card_display, textvariable=self.aniso_var, state="readonly", width=18,
                                        values=[n for n, _ in ANISO])
        self.aniso_combo.grid(row=3, column=3, sticky="ew", padx=(8, 0), pady=4)

        # Row 4: Window size & Upscaling
        self.lbl_win_size = ttk.Label(card_display, text=self.t("window_size"), style="Card.TLabel")
        self.lbl_win_size.grid(row=4, column=0, sticky="w", pady=4)
        self.res_var = tk.StringVar()
        self.res_combo = ttk.Combobox(card_display, textvariable=self.res_var, state="readonly", width=22,
                                      values=[n for n, _ in RESOLUTIONS])
        self.res_combo.grid(row=4, column=1, sticky="ew", padx=(8, 18), pady=4)

        self.lbl_upscale = ttk.Label(card_display, text=self.t("upscaling"), style="Card.TLabel")
        self.lbl_upscale.grid(row=4, column=2, sticky="w", pady=4)
        self.up_var = tk.StringVar()
        self.up_combo = ttk.Combobox(card_display, textvariable=self.up_var, state="readonly", width=18,
                                     values=[n for n, _ in UPSCALERS])
        self.up_combo.grid(row=4, column=3, sticky="ew", padx=(8, 0), pady=4)

        # Row 5: Checkboxes
        check_frame = tk.Frame(card_display, bg=CARD_BG)
        check_frame.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 4))

        self.vsync_var = tk.BooleanVar(value=self.cfg["vsync"])
        self.rcas_var = tk.BooleanVar(value=self.cfg["rcas"])
        self.audio_var = tk.BooleanVar(value=self.cfg.get("audio_log", False))
        self.wav_var = tk.BooleanVar(value=False)

        self.chk_vsync = ttk.Checkbutton(check_frame, text=self.t("vsync"), variable=self.vsync_var)
        self.chk_vsync.pack(side="left", padx=(0, 16))
        self.chk_rcas = ttk.Checkbutton(check_frame, text=self.t("rcas"), variable=self.rcas_var)
        self.chk_rcas.pack(side="left", padx=(0, 16))
        self.chk_audio = ttk.Checkbutton(check_frame, text=self.t("audio_log"), variable=self.audio_var,
                                         command=self._audio_toggled)
        self.chk_audio.pack(side="left", padx=(0, 16))
        self.chk_wav = ttk.Checkbutton(check_frame, text=self.t("wav_capture"), variable=self.wav_var,
                                       command=self._wav_toggled)
        self.chk_wav.pack(side="left")

        # Hints
        self.res_hint = ttk.Label(card_display, text=self.t("res_hint"), style="Muted.TLabel", wraplength=620)
        self.res_hint.grid(row=6, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.menu_hint = ttk.Label(card_display, text=self.t("ingame_menu"), style="Muted.TLabel")
        self.menu_hint.grid(row=7, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # CARD 3: CONTROLLER & INPUT
        card_ctrl = tk.Frame(settings_panel, bg=CARD_BG, highlightbackground=CARD_BORDER,
                             highlightthickness=1, bd=0, padx=16, pady=12)
        card_ctrl.pack(fill="x")

        self.card_ctrl_title = tk.Label(card_ctrl, text=f"🎮 {self.t('section_controller')}", bg=CARD_BG, fg=GOLD,
                                        font=("Segoe UI Bold", 10))
        self.card_ctrl_title.pack(anchor="w", pady=(0, 6))

        # Input Mode Selector Bar
        input_mode_frame = tk.Frame(card_ctrl, bg=CARD_BG)
        input_mode_frame.pack(fill="x", pady=(0, 8))
        self.lbl_input_mode = ttk.Label(input_mode_frame, text=self.t("input_mode"), style="Card.TLabel")
        self.lbl_input_mode.pack(side="left", padx=(0, 10))

        self.input_mode_var = tk.StringVar(value=self.cfg.get("input_mode", "controller"))
        self.rb_controller = ttk.Radiobutton(input_mode_frame, text=self.t("input_mode_controller"),
                                             value="controller", variable=self.input_mode_var)
        self.rb_controller.pack(side="left", padx=(0, 16))
        self.rb_kbm = ttk.Radiobutton(input_mode_frame, text=self.t("input_mode_kbm"),
                                      value="kbm_coop", variable=self.input_mode_var)
        self.rb_kbm.pack(side="left")

        # Row 1 of Utilities Buttons
        tools_row1 = tk.Frame(card_ctrl, bg=CARD_BG)
        tools_row1.pack(fill="x", pady=(0, 6))

        self.btn_kbm = ModernButton(tools_row1, text=self.t("kbm_controls_btn"),
                                    command=self.open_keymap_ui, width=165, height=30, bg_color=CARD_BG)
        self.btn_kbm.pack(side="left", padx=(0, 8))

        self.btn_map_pad = ModernButton(tools_row1, text=self.t("map_pad"),
                                        command=lambda: self.map_pad([]), width=115, height=30, bg_color=CARD_BG)
        self.btn_map_pad.pack(side="left", padx=(0, 8))

        self.btn_map_sticks = ModernButton(tools_row1, text=self.t("map_sticks"),
                                           command=lambda: self.map_pad(["--sticks"]), width=125, height=30, bg_color=CARD_BG)
        self.btn_map_sticks.pack(side="left", padx=(0, 8))

        self.btn_reset_map = ModernButton(tools_row1, text=self.t("reset_map"),
                                          command=self.reset_map, width=125, height=30, bg_color=CARD_BG)
        self.btn_reset_map.pack(side="left")

        # Row 2 of Utilities Buttons
        tools_row2 = tk.Frame(card_ctrl, bg=CARD_BG)
        tools_row2.pack(fill="x", pady=(0, 6))

        self.btn_cheats = ModernButton(tools_row2, text=self.t("cheats_btn"),
                                       command=self.open_cheats_manager, width=155, height=30, bg_color=CARD_BG)
        self.btn_cheats.pack(side="left", padx=(0, 8))

        self.btn_open_log = ModernButton(tools_row2, text=self.t("open_log"),
                                         command=self.open_log, width=90, height=30, bg_color=CARD_BG)
        self.btn_open_log.pack(side="left", padx=(0, 8))

        self.btn_open_audio_log = ModernButton(tools_row2, text=self.t("open_audio_log"),
                                               command=self.open_audio_log, width=90, height=30, bg_color=CARD_BG)
        self.btn_open_audio_log.pack(side="left", padx=(0, 8))

        self.btn_open_saves = ModernButton(tools_row2, text=self.t("open_saves"),
                                           command=self.open_saves, width=90, height=30, bg_color=CARD_BG)
        self.btn_open_saves.pack(side="left", padx=(0, 8))

        self.btn_dlc = ModernButton(tools_row2, text=self.t("dlc_btn"),
                                    command=self.open_dlc_manager, width=175, height=30, bg_color=CARD_BG)
        self.btn_dlc.pack(side="left")

        self.pad_label = ttk.Label(card_ctrl, text="", style="Muted.TLabel")
        self.pad_label.pack(anchor="w", pady=(6, 0))
        self._pad_text()

        # =====================================================================
        # RIGHT COLUMN (FIXED WIDTH ~340px): HERO & ACTION PANEL
        # =====================================================================
        hero_card = tk.Frame(self.main_container, bg=CARD_BG, highlightbackground=CARD_BORDER,
                             highlightthickness=1, bd=0, padx=16, pady=16, width=340)
        hero_card.grid(row=0, column=1, sticky="nsew")
        hero_card.pack_propagate(False)

        # High-res Cover art container with glowing crimson border
        cover_container = tk.Frame(hero_card, bg="#1B0B0E", highlightbackground=RED_PRIMARY,
                                   highlightthickness=1, bd=0)
        cover_container.pack(pady=(2, 8))

        if self.cover:
            self.cover_label = tk.Label(cover_container, image=self.cover, bd=0, bg="#1B0B0E")
            self.cover_label.pack()
        else:
            tk.Label(cover_container, text=self.t("app_subtitle"), bg="#1B0B0E", fg=GOLD,
                     font=("Segoe UI Bold", 14), width=24, height=10).pack()

        # Titles
        ttk.Label(hero_card, text="戦国BASARA4 皇", style="CardHead.TLabel",
                  font=("Segoe UI Bold", 13)).pack(pady=(4, 0))
        ttk.Label(hero_card, text="Sengoku Basara 4 Sumeragi", style="Card.TLabel",
                  font=("Segoe UI Semibold", 10)).pack()
        ttk.Label(hero_card, text="CUSA01159 · Native PS4 PC Port", style="Muted.TLabel").pack()

        self.status = ttk.Label(hero_card, text=self.t("ready"), style="Muted.TLabel",
                                wraplength=290, justify="center")
        self.status.pack(pady=(8, 8))

        # Primary High-Impact Crimson Action Button ("MAINKAN GAME")
        self.play = ModernButton(hero_card, text=self.t("play_btn"), command=self.on_play, is_primary=True,
                                 width=290, height=52, font=("Segoe UI Bold", 14), bg_color=CARD_BG)
        self.play.pack(pady=(2, 6))

        # Secondary "Stop game" Button
        self.stop = ModernButton(hero_card, text=self.t("stop_btn"), command=self.on_stop, is_primary=False,
                                 width=290, height=34, state="disabled", font=("Segoe UI Semibold", 10), bg_color=CARD_BG)
        self.stop.pack(pady=(0, 6))

        # Bottom watermark
        mark = tk.Frame(hero_card, bg=CARD_BG)
        mark.pack(side="bottom", pady=(4, 4))
        tk.Label(mark, text=BRAND.upper(), bg=CARD_BG, fg=GOLD, font=("Georgia", 11, "bold")).pack()
        tk.Label(mark, text=f"{self.t('by_author')} · v{VERSION}", bg=CARD_BG, fg=MUTED, font=("Segoe UI", 8)).pack()
        self.mark_frame = mark

        # Bottom Action Row: Credits and Check Update
        btn_row = tk.Frame(hero_card, bg=CARD_BG)
        btn_row.pack(side="bottom", fill="x", pady=(0, 6))
        self.credits_btn = ModernButton(btn_row, text=self.t("credits_btn"), command=self.show_credits, is_primary=False,
                                        width=140, height=30, font=("Segoe UI", 8), bg_color=CARD_BG)
        self.credits_btn.pack(side="left", padx=(0, 6))
        self.check_update_btn = ModernButton(btn_row, text="Cek Update" if self.lang == "id" else "Check Update",
                                             command=self.check_update_manual, is_primary=False,
                                             width=140, height=30, font=("Segoe UI", 8), bg_color=CARD_BG)
        self.check_update_btn.pack(side="left")

    # ---- helpers ----
    def _browse(self):
        path = filedialog.askdirectory(initialdir=self.game_var.get() or str(ROOT), mustexist=True)
        if path:
            self.game_var.set(os.path.normpath(path))

    def _refresh_image_label(self):
        game = self.game_var.get().strip()
        if not game or not (Path(game) / "eboot.bin").is_file():
            text = self.t("no_eboot")
        elif image_ready(game):
            text = f"✓ {self.t('game_ready')}"
        else:
            text = self.t("prep_notice")
        self.image_label.config(text=text)

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

    def _pad_text(self):
        has_custom = False
        if MAPPING.exists() and MAPPING.stat().st_size > 0:
            try:
                content = MAPPING.read_text(encoding="utf-8", errors="ignore").strip()
                has_custom = (content != DEFAULT_XINPUT_MAPPING.strip())
            except Exception:
                has_custom = True
        self.pad_label.config(text=self.t("pad_custom") if has_custom else self.t("pad_default"))

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
        if messagebox.askyesno("Audio captures", f"user\\\\audio_wav holds {format_size(total)} of audio captures "
                               f"({len(files)} files) from an earlier session.\\n\\nDelete them to free the space?",
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
            messagebox.showerror(self.t("err_cannot_start"), f"{self.t('err_runtime_missing')}\\n{exe}")
            return

        avail_mb = check_commit_limit_mb()
        if avail_mb is not None and avail_mb < 2560:
            if not messagebox.askyesno(
                "Virtual Memory Sangat Rendah",
                f"Sisa alokasi memori virtual Windows Anda hanya ~{avail_mb} MB.\\n"
                "Game membutuhkan setidaknya ~3584 MB (3.5 GB) virtual memory.\\n\\n"
                "Jika game crash dengan Error 1455, pastikan Virtual Memory (Paging File) aktif di Windows.\\n\\n"
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
                return "\\n".join(lines[-max_lines:])
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
                    log_launch(f"Audio patch warning: {e}\\n{traceback.format_exc()}")

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
                    log_launch(f"Patch build warning: {e}\\n{traceback.format_exc()}")
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
            log_launch(f"Unhandled exception during game boot sequence: {e}\\n{tb}")
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
        messagebox.showerror(self.t("err_cannot_start"), f"{self.t('err_boot_failed', default='Gagal memulai proses game:')}\\n\\n{error}")

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
        window.title("Extracted Basara 4 DLC")
        window.geometry("920x480")
        window.minsize(720, 360)
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

        frame = ttk.Frame(window, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="DLC folder", style="Head.TLabel").grid(row=0, column=0, sticky="w")
        path_var = tk.StringVar(value=self.cfg.get("dlc_dir", str(DEFAULT_DLC_DIR)))
        path_entry = ttk.Entry(frame, textvariable=path_var, state="readonly")
        path_entry.grid(row=1, column=0, sticky="ew", pady=(8, 12))

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("folder", "title", "content_id", "status")
        table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for column, heading, width in (
                ("folder", "ENTITLEMENT", 180), ("title", "DLC", 220),
                ("content_id", "CONTENT ID", 300), ("status", "STATUS", 180)):
            table.heading(column, text=heading)
            table.column(column, width=width, minwidth=100, stretch=column in ("title", "content_id"))
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        summary = ttk.Label(frame, text="", style="Muted.TLabel")
        summary.grid(row=3, column=0, sticky="w", pady=(10, 0))

        def choose_folder():
            initial_dir = Path(path_var.get())
            if not initial_dir.is_dir():
                initial_dir = ROOT if ROOT.is_dir() else Path.home()
            try:
                selected = filedialog.askdirectory(
                    parent=self, title="Select the parent folder of extracted Basara 4 DLC",
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
            try:
                records = scan_extracted_dlc(path_var.get())
            except OSError as error:
                messagebox.showerror("Cannot scan DLC folder", str(error), parent=window)
                return
            ready = sum(info is not None for _path, info, _error in records)
            invalid = len(records) - ready
            for path, info, error in records:
                if info:
                    table.insert("", "end", values=(path.name, info["title"], info["content_id"], "READY"))
                else:
                    table.insert("", "end", values=(path.name, "", "", f"CHECK: {error}"))
            summary.configure(text=f"{ready} DLC ready for the next game launch"
                               + (f"  |  {invalid} need attention" if invalid else "")
                               if records else "No extracted DLC found in this folder.")

        def open_folder():
            folder = Path(path_var.get())
            try:
                folder.mkdir(parents=True, exist_ok=True)
                os.startfile(str(folder))
            except OSError as error:
                messagebox.showerror("Cannot open DLC folder", str(error), parent=window)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Choose folder…", command=choose_folder).pack(side="left")
        ttk.Button(buttons, text="Open folder", command=open_folder).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
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
        window.configure(bg=CARD_BG)
        window.geometry("640x430")
        window.minsize(580, 390)
        window.transient(self)
        window.grab_set()

        frame = ttk.Frame(window, style="Card.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="GoldHEN cheats · CUSA01159 · update 01.02",
                  style="CardHead.TLabel", font=("Segoe UI Bold", 11)).pack(anchor="w")
        ttk.Label(frame, text="Cheat codes by Q8Despair. These are applied on the next game launch.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 12))

        selected = set(current)
        toggles = {}
        for cheat_id, cheat in basara4_cheats.CHEATS.items():
            var = tk.BooleanVar(value=cheat_id in selected)
            toggles[cheat_id] = var
            ttk.Checkbutton(
                frame, text=f"{basara4_cheats.CHEATS[cheat_id]['name']}  ·  by {basara4_cheats.AUTHOR}",
                variable=var).pack(anchor="w", pady=4)
        ttk.Label(frame, text="Cave dan hook tiap cheat dipisahkan agar semuanya bisa aktif bersamaan.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        source_row = ttk.Frame(frame, style="Card.TFrame")
        source_row.pack(fill="x", pady=(10, 0))
        ttk.Label(source_row, text="Source: GoldHEN Cheat Repository (GPL-3.0)",
                  style="Muted.TLabel").pack(side="left")

        def open_source():
            webbrowser.open(basara4_cheats.SOURCE_URL)

        ttk.Button(source_row, text="View source", command=open_source).pack(side="right")

        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x", side="bottom", pady=(16, 0))

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

        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="right")
        ttk.Button(buttons, text="Save cheats", command=save).pack(side="right", padx=(0, 8))

    # ---- Keyboard & Mouse Mapping Dialog ----
    def open_keymap_ui(self):
        win = tk.Toplevel(self)
        win.title("Keyboard & Mouse Controls — Custom Keymap")
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

        tk.Label(top_frame, text="⚙️ Pengaturan Kontrol Keyboard & Mouse", bg=CARD_BG, fg=GOLD, font=("Segoe UI Bold", 12)).pack(anchor="w")
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
                    btn.config(text=format_binding_display(new_key), bg="#2C2824", fg=GOLD)
                win.unbind("<Key>")
                win.unbind("<Button-1>")
                win.unbind("<Button-2>")
                win.unbind("<Button-3>")

        def start_listen(action_name):
            if active_listening[0]:
                old_action = active_listening[0]
                old_btn = btn_widgets.get(old_action)
                if old_btn:
                    old_btn.config(text=format_binding_display(cur_map.get(old_action, "")), bg="#2C2824", fg=GOLD)
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
                fg=GOLD,
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
                b.config(text=format_binding_display(cur_map.get(k, "")), bg="#2C2824", fg=GOLD)
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
                fg=GOLD,
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

            gpu_list = "\\n".join(f"  - {name}" for _, name, _ in SYSTEM_GPUS) if SYSTEM_GPUS else "  - None detected"

            audio_tail = ""
            if AUDIO_LOG.is_file():
                try:
                    a_lines = AUDIO_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
                    if a_lines:
                        audio_tail = "\\n".join(a_lines[-6:])
                except Exception:
                    pass

            clip_text = (
                f"=== Sengoku Basara 4 PC — Crash Diagnostic Report ===\\n"
                f"Version       : v{VERSION}\\n"
                f"Exit Code     : {exit_hex}\\n"
                f"OS            : {platform.system()} {platform.release()} (Build {platform.version()})\\n"
                f"Architecture  : {platform.machine()} ({platform.processor()})\\n"
                f"RAM           : Total {ram_total} | Free {ram_avail} | Available Commit {commit_avail}\\n"
                f"Vulkan GPUs   :\\n{gpu_list}\\n"
                f"Detected Fatal Signatures:\\n" + "\\n".join(f"  * {e}" for e in data["detected_errors"]) + "\\n\\n"
                f"--- [Last 10 Log Lines (last_run.log)] ---\\n"
                f"{data['tail_context']}\\n"
            )
            if audio_tail:
                clip_text += f"\\n--- [Recent Audio Log (audio_debug.log)] ---\\n{audio_tail}\\n"

            clip_text += "\\n=== End of Report ==="
            self.clipboard_clear()
            self.clipboard_append(clip_text)
            messagebox.showinfo(
                "Tersalin ke Clipboard",
                "Laporan crash lengkap (spek hardware, GPU, log error, dan audio log) berhasil disalin!\\n"
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
            bg=GOLD,
            fg=ROOT_BG,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            activebackground="#DBB458",
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
                    self.header_status_pill.set_status("ready", self.t("ready")),
                    self._show_update_available(),
                    self.prompt_update()
                ))
            else:
                self.after(0, lambda: (
                    self.status.config(text=self.t("ready")),
                    self.header_status_pill.set_status("ready", self.t("ready")),
                    messagebox.showinfo("Update", f"Anda sudah menggunakan versi terbaru (v{VERSION}).")
                ))

        threading.Thread(target=run, daemon=True).start()

    def prompt_update(self):
        if not self.update_info:
            return
        tag = self.update_info["tag"]
        size_mb = self.update_info["size"] / (1024 * 1024)
        if messagebox.askyesno(
            "Update Tersedia",
            f"Versi baru {tag} tersedia di GitHub!\\nUkuran unduhan: ~{size_mb:.1f} MB.\\n\\n"
            "Launcher akan mengunduh dan menerapkan update secara otomatis.\\n"
            "Data game (folder game\\\\) dan save data Anda (folder user\\\\) TIDAK akan terhapus.\\n\\n"
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

        tk.Label(win, text=f"Mengunduh Pembaruan {info['tag']}...", bg=ROOT_BG, fg=GOLD, font=("Segoe UI Bold", 11)).pack(pady=(18, 8))
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
                    messagebox.showerror("Gagal Mengunduh", f"Pembaruan gagal diunduh:\\n{err}")
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_update_and_restart(self, win):
        win.destroy()
        updater_cmd = USER / "updater.cmd"
        cmd_content = (
            "@echo off\\r\\n"
            "setlocal enabledelayedexpansion\\r\\n"
            "title Basara 4 PC - Updater\\r\\n"
            "cd /d \\\"%~dp0\\\"\\r\\n"
            "echo Menunggu launcher menutup...\\r\\n"
            "timeout /t 2 /nobreak >nul\\r\\n"
            "set \\\"ZIP=%~dp0updates\\\\update.zip\\\"\\r\\n"
            "set \\\"EXTRACT=%~dp0updates\\\\extract\\\"\\r\\n"
            "set \\\"DEST=%~dp0..\\\"\\r\\n"
            "if not exist \\\"!ZIP!\\\" exit /b 1\\r\\n"
            "echo Mengekstrak pembaruan...\\r\\n"
            "if exist \\\"!EXTRACT!\\\" rmdir /s /q \\\"!EXTRACT!\\\"\\r\\n"
            "mkdir \\\"!EXTRACT!\\\"\\r\\n"
            "tar -xf \\\"!ZIP!\\\" -C \\\"!EXTRACT!\\\" 2>nul\\r\\n"
            "if errorlevel 1 (\\r\\n"
            "    powershell.exe -NoProfile -Command \\\"Expand-Archive -Path '!ZIP!' -DestinationPath '!EXTRACT!' -Force\\\"\\r\\n"
            ")\\r\\n"
            "set \\\"SRC=!EXTRACT!\\\"\\r\\n"
            "if not exist \\\"!EXTRACT!\\\\Sengoku Basara 4.exe\\\" (\\r\\n"
                   "    for /d %%D in (\\\"!EXTRACT!\\\\*\\\") do (\\r\\n"
            "        if exist \\\"%%~fD\\\\Sengoku Basara 4.exe\\\" set \\\"SRC=%%~fD\\\"\\r\\n"
            "    )\\r\\n"
            ")\\r\\n"
            "echo Menerapkan file baru...\\r\\n"
            "if exist \\\"!SRC!\\\\_internal\\\" xcopy /e /y /i \\\"!SRC!\\\\_internal\\\" \\\"!DEST!\\\\_internal\\\" >nul\\r\\n"
            "if exist \\\"!SRC!\\\\bin\\\" xcopy /e /y /i \\\"!SRC!\\\\bin\\\" \\\"!DEST!\\\\bin\\\" >nul\\r\\n"
            "if exist \\\"!SRC!\\\\scripts\\\" xcopy /e /y /i \\\"!SRC!\\\\scripts\\\" \\\"!DEST!\\\\scripts\\\" >nul\\r\\n"
            "if exist \\\"!SRC!\\\\launcher\\\" xcopy /e /y /i \\\"!SRC!\\\\launcher\\\" \\\"!DEST!\\\\launcher\\\" >nul\\r\\n"
            "if exist \\\"!SRC!\\\\Sengoku Basara 4.exe\\\" copy /y \\\"!SRC!\\\\Sengoku Basara 4.exe\\\" \\\"!DEST!\\\\\\\" >nul\\r\\n"
            "if exist \\\"!SRC!\\\\Play Sengoku Basara 4.cmd\\\" copy /y \\\"!SRC!\\\\Play Sengoku Basara 4.cmd\\\" \\\"!DEST!\\\\\\\" >nul\\r\\n"
            "if exist \\\"!SRC!\\\\NOTICE.md\\\" copy /y \\\"!SRC!\\\\NOTICE.md\\\" \\\"!DEST!\\\\\\\" >nul\\r\\n"
            "if exist \\\"!SRC!\\\\LICENSE\\\" copy /y \\\"!SRC!\\\\LICENSE\\\" \\\"!DEST!\\\\\\\" >nul\\r\\n"
            "rmdir /s /q \\\"!EXTRACT!\\\" 2>nul\\r\\n"
            "del /f /q \\\"!ZIP!\\\" 2>nul\\r\\n"
            "echo Memulai versi baru...\\r\\n"
            "start \\\"\\\" \\\"!DEST!\\\\Sengoku Basara 4.exe\\\"\\r\\n"
            "del /f /q \\\"%~f0\\\" 2>nul\\r\\n"
            "exit /b 0\\r\\n"
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
        win.configure(bg=ROOT_BG)
        win.geometry("740x520")
        win.minsize(640, 420)
        win.transient(self)

        top_bar = ttk.Frame(win, style="Card.TFrame", padding=10)
        top_bar.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(top_bar, text="Community & Official Channels:", style="CardHead.TLabel").pack(side="left", padx=(0, 10))
        ttk.Button(top_bar, text="💬 Discord",
                   command=lambda: webbrowser.open("https://discord.gg/UBZc57bBMa")).pack(side="left", padx=4)
        ttk.Button(top_bar, text="🎬 TikTok (@Timotiusconnect)",
                   command=lambda: webbrowser.open("https://www.tiktok.com/@Timotiusconnect")).pack(side="left", padx=4)
        ttk.Button(top_bar, text="☕ Support Dev",
                   command=lambda: webbrowser.open("https://sociabuzz.com/Timotiusgame/tribe")).pack(side="left", padx=4)

        box_frame = ttk.Frame(win, style="Card.TFrame")
        box_frame.pack(fill="both", expand=True, padx=10, pady=10)
        box = tk.Text(box_frame, bg=CARD_BG, fg=FG, wrap="word", relief="flat", padx=14, pady=12,
                      font=("Segoe UI", 10), highlightthickness=1, highlightbackground=CARD_BORDER)
        scrollbar = ttk.Scrollbar(box_frame, orient="vertical", command=box.yview, style="Vertical.TScrollbar")
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

        try:
            probe = subprocess.run(
                [str(exe), str(MAPPING)] + extra,
                env=env,
                capture_output=True,
                text=True,
                timeout=0.6
            )
            if probe.returncode != 0:
                out = (probe.stdout + " " + probe.stderr).strip()
                if "Tidak ada controller" in out or "No controller" in out or not out:
                    messagebox.showwarning(self.t("map_pad"), self.t("err_no_pad"))
                    return
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            log_debug(f"Gamepad probe exception: {e}")

        extra_args = " ".join(extra)
        cmd = f'title Basara 4 Gamepad Mapper & "{exe}" "{MAPPING}" {extra_args} & echo. & pause'
        try:
            subprocess.Popen(["cmd.exe", "/c", cmd], env=env, creationflags=0x00000010)
            self.status.config(text=self.t("pad_prompt"))
            self.after(3000, self._pad_text)
        except Exception as e:
            messagebox.showerror(self.t("map_pad"), f"Failed to start controller mapper:\\n{e}")

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
            messagebox.showerror(self.t("reset_map"), f"Failed to reset mapping:\\n{e}")

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
'''

print("Validating code with AST...")
tree = ast.parse(launcher_code)
print(f"AST parse successful! Nodes: {len(tree.body)}")

dest = ROOT / "launcher" / "basara4_launcher.py"
with open(dest, "w", encoding="utf-8") as f:
    f.write(launcher_code)
print(f"Successfully updated {dest} ({len(launcher_code)} bytes)")
