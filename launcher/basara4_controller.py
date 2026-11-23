"""Controller window: maps a controller without a console (Basara 4 PC by Timotius).

The mapper (bin\\basara4-pad-mapper.exe <mapping file> --ui) detects the inputs and writes
user\\gamepad_mapping.txt; the file format and the game side do not change. It sends one JSON event per
line on stdout and reads one command per line on stdin (select N, skip, cancel, redo <entry>,
flip <entry>, check left|right|off, save). This window shows what it asks and what it recorded and sends
those commands. No console window opens: the mapper runs with CREATE_NO_WINDOW and is closed with the
window.

Sticks get two extra views. While a stick is asked for, a guide shows the direction with a moving white
dot and a blinking arrow, and a green dot shows the player's own stick. After the stick steps, a check
shows what the game will receive (the mapper reads the stick through the recorded mapping, as the game
does): the player compares it with the thumb and can flip an axis or map the stick again.
"""
import ctypes
import json
import math
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

CREATE_NO_WINDOW = 0x08000000

ENTRIES = [
    ("a", "Bottom button (A or Cross)", "Cross"),
    ("b", "Right button (B or Circle)", "Circle"),
    ("x", "Left button (X or Square)", "Square"),
    ("y", "Top button (Y or Triangle)", "Triangle"),
    ("leftshoulder", "Left shoulder button (upper)", "L1"), ("rightshoulder", "Right shoulder button (upper)", "R1"),
    ("lefttrigger", "Left trigger (lower)", "L2"), ("righttrigger", "Right trigger (lower)", "R2"),
    ("back", "Small left button (Select / Back)", "Touchpad (pause menu)"),
    ("start", "Small right button (Start)", "Options"),
    ("leftstick", "Press the left stick in", "L3"), ("rightstick", "Press the right stick in", "R3"),
    ("guide", "Centre / Home button (if any)", "PS button"),
    ("dpup", "D-pad up", "D-pad up"), ("dpdown", "D-pad down", "D-pad down"),
    ("dpleft", "D-pad left", "D-pad left"), ("dpright", "D-pad right", "D-pad right"),
    ("leftx", "Left stick: push RIGHT", "Left stick"), ("lefty", "Left stick: push DOWN (toward you)", "Left stick"),
    ("rightx", "Right stick: push RIGHT", "Right stick"),
    ("righty", "Right stick: push DOWN (toward you)", "Right stick"),
]

ENTRIES_ID = {
    "a": ("Tombol bawah (A atau Silang)", "Cross (Silang)"),
    "b": ("Tombol kanan (B atau Lingkaran)", "Circle (Lingkaran)"),
    "x": ("Tombol kiri (X atau Kotak)", "Square (Kotak)"),
    "y": ("Tombol atas (Y atau Segitiga)", "Triangle (Segitiga)"),
    "leftshoulder": ("Tombol bahu kiri (atas)", "L1"),
    "rightshoulder": ("Tombol bahu kanan (atas)", "R1"),
    "lefttrigger": ("Trigger kiri (bawah)", "L2"),
    "righttrigger": ("Trigger kanan (bawah)", "R2"),
    "back": ("Tombol kecil kiri (Select / Back)", "Touchpad (menu jeda)"),
    "start": ("Tombol kecil kanan (Start)", "Options"),
    "leftstick": ("Tekan stik analog kiri ke dalam", "L3"),
    "rightstick": ("Tekan stik analog kanan ke dalam", "R3"),
    "guide": ("Tombol tengah / Home (jika ada)", "Tombol PS"),
    "dpup": ("D-pad atas", "D-pad atas"),
    "dpdown": ("D-pad bawah", "D-pad bawah"),
    "dpleft": ("D-pad kiri", "D-pad kiri"),
    "dpright": ("D-pad kanan", "D-pad kanan"),
    "leftx": ("Stik kiri: dorong ke KANAN", "Stik kiri"),
    "lefty": ("Stik kiri: dorong ke BAWAH (ke arah Anda)", "Stik kiri"),
    "rightx": ("Stik kanan: dorong ke KANAN", "Stik kanan"),
    "righty": ("Stik kanan: dorong ke BAWAH (ke arah Anda)", "Stik kanan"),
}

STICKS = {"leftx", "lefty", "rightx", "righty"}

LABELS = {
    "xbox": {
        "a": "A (bottom)", "b": "B (right)", "x": "X (left)", "y": "Y (top)",
        "leftshoulder": "LB (left shoulder)", "rightshoulder": "RB (right shoulder)",
        "lefttrigger": "LT (left trigger)", "righttrigger": "RT (right trigger)",
        "back": "View / Back (small left button)", "start": "Menu / Start (small right button)",
        "leftstick": "LS (press the left stick in)", "rightstick": "RS (press the right stick in)",
        "guide": "Xbox button (centre)",
    },
    "playstation": {
        "a": "Cross (bottom)", "b": "Circle (right)", "x": "Square (left)", "y": "Triangle (top)",
        "leftshoulder": "L1 (left shoulder)", "rightshoulder": "R1 (right shoulder)",
        "lefttrigger": "L2 (left trigger)", "righttrigger": "R2 (right trigger)",
        "back": "Share / Create (small left button)", "start": "Options (small right button)",
        "leftstick": "L3 (press the left stick in)", "rightstick": "R3 (press the right stick in)",
        "guide": "PS button (centre)",
    },
}

LABELS_ID = {
    "xbox": {
        "a": "A (bawah)", "b": "B (kanan)", "x": "X (kiri)", "y": "Y (atas)",
        "leftshoulder": "LB (bahu kiri)", "rightshoulder": "RB (bahu kanan)",
        "lefttrigger": "LT (trigger kiri)", "righttrigger": "RT (trigger kanan)",
        "back": "View / Back (tombol kecil kiri)", "start": "Menu / Start (tombol kecil kanan)",
        "leftstick": "LS (tekan stik kiri)", "rightstick": "RS (tekan stik kanan)",
        "guide": "Tombol Xbox (tengah)",
    },
    "playstation": {
        "a": "Cross / Silang (bawah)", "b": "Circle / Lingkaran (kanan)", "x": "Square / Kotak (kiri)", "y": "Triangle / Segitiga (atas)",
        "leftshoulder": "L1 (bahu kiri)", "rightshoulder": "R1 (bahu kanan)",
        "lefttrigger": "L2 (trigger kiri)", "righttrigger": "R2 (trigger kanan)",
        "back": "Share / Create (tombol kecil kiri)", "start": "Options (tombol kecil kanan)",
        "leftstick": "L3 (tekan stik kiri)", "rightstick": "R3 (tekan stik kanan)",
        "guide": "Tombol PS (tengah)",
    },
}


def pad_label(name, kind, lang="en"):
    """What to press for entry `name` on a controller of this kind ("xbox", "playstation", other)."""
    if lang == "id":
        label = LABELS_ID.get(kind, {}).get(name)
        if label:
            return label
        return ENTRIES_ID.get(name, ("", ""))[0] or next(pad for entry, pad, _game in ENTRIES if entry == name)
    label = LABELS.get(kind, {}).get(name)
    return label or next(pad for entry, pad, _game in ENTRIES if entry == name)


def game_label(name, lang="en"):
    if lang == "id" and name in ENTRIES_ID:
        return ENTRIES_ID[name][1]
    return next(g for n, _p, g in ENTRIES if n == name)


STICK_STEPS = [("leftx", "Left stick", "RIGHT", (1, 0)), ("lefty", "Left stick", "DOWN (toward you)", (0, 1)),
               ("rightx", "Right stick", "RIGHT", (1, 0)), ("righty", "Right stick", "DOWN (toward you)", (0, 1))]
STICK_STEPS_ID = [("leftx", "Stik kiri", "KANAN", (1, 0)), ("lefty", "Stik kiri", "BAWAH (ke arah Anda)", (0, 1)),
                  ("rightx", "Stik kanan", "KANAN", (1, 0)), ("righty", "Stik kanan", "BAWAH (ke arah Anda)", (0, 1))]
CHECK_SIDES = [("left", "left stick", "leftx", "lefty"), ("right", "right stick", "rightx", "righty")]
CHECK_SIDES_ID = [("left", "stik kiri", "leftx", "lefty"), ("right", "stik kanan", "rightx", "righty")]

TEXT = {
    "title": "Controller Mapping — Basara 4 PC",
    "idle": "Press Map all, then press each button on your controller when it is asked for.",
    "idle_saved": "A custom mapping is in use. Press Map all to make a new one.",
    "starting": "Looking for your controller...",
    "choose": "More than one controller is connected. Choose the one to map:",
    "button": "Press {pad} on your controller  →  {game} in the game",
    "stick": "{stick} ({n} of 4): push it straight {dir} and hold, then let go",
    "stick_hint": "One straight push. Do not spin the stick in circles.",
    "stick_waiting": "Waiting for you to push {dir}...",
    "stick_moving": "Keep pushing {dir} until it stops, hold, then let go.",
    "progress": "{n} of {total}  |  15 seconds without input skips this one",
    "used": "That input is already used by another entry. Let go and press the right one.",
    "stick_rotated": "That was a circle or a push back. Push straight {dir} and hold, then let go.",
    "stick_two_axes": "The stick moved in two directions. Push straight {dir} and hold, then let go.",
    "check": "Check your {stick}: push it up-right. The dot must go up-right too.",
    "check_hint": "The dot and the label show what the game will receive. Compare them with your thumb. "
                  "If they go another way, tick Flip below.",
    "game_sees": "Game sees: {where}",
    "center": "CENTER",
    "flip_x": "Flip left / right", "flip_y": "Flip up / down",
    "looks_right": "Looks right", "redo_stick": "Redo this stick",
    "check_done": "Sticks checked. Press Done to save.",
    "review": "All entries done. Check the list, then press Done to save.",
    "saved": "Saved. The game uses this mapping from its next start.",
    "cancelled": "Cancelled. Nothing was saved.",
    "ended": "The mapper stopped without saving.",
    "not_started": "The mapper could not start: {reason}",
    "busy": "Finish or cancel the mapping in this window first.",
    "set": "not set", "skipped": "skipped", "no_input": "skipped (no input)", "waiting": "press now",
    "map_all": "Map all", "map_sticks": "Map sticks", "map_sticks_only": "Map sticks only",
    "skip": "Skip", "cancel": "Cancel", "reset": "Reset",
    "done": "Done", "use": "Use this controller", "manual": "Presets / Manual...",
    "col_pad": "Controller", "col_game": "In game", "col_set": "Set",
    "kind_xbox": "{name}: buttons are shown with their Xbox names.",
    "kind_playstation": "{name}: buttons are shown with their PlayStation names.",
    "kind_other": "{name}: buttons are shown by where they are on the controller.",
}

TEXT_ID = {
    "title": "Pemetaan Kontroler — Basara 4 PC",
    "idle": "Tekan Petakan Semua, lalu tekan setiap tombol pada stik saat diminta.",
    "idle_saved": "Mapping kustom sedang aktif. Tekan Petakan Semua untuk membuat yang baru.",
    "starting": "Mencari kontroler Anda...",
    "choose": "Lebih dari satu kontroler terhubung. Pilih salah satu untuk dipetakan:",
    "button": "Tekan {pad} pada kontroler  →  {game} di dalam game",
    "stick": "{stick} ({n} dari 4): dorong lurus ke {dir} dan tahan, lalu lepaskan",
    "stick_hint": "Dorong lurus satu arah. Jangan memutar stik melingkar.",
    "stick_waiting": "Menunggu Anda mendorong ke {dir}...",
    "stick_moving": "Terus dorong ke {dir} sampai berhenti, tahan sejenak, lalu lepaskan.",
    "progress": "{n} dari {total}  |  15 detik tanpa input akan melewati tombol ini",
    "used": "Tombol itu sudah dipakai untuk fungsi lain. Lepaskan lalu tekan tombol yang benar.",
    "stick_rotated": "Gerakan memutar atau balik terdeteksi. Dorong lurus ke {dir} dan tahan, lalu lepaskan.",
    "stick_two_axes": "Stik bergerak ke dua arah sekaligus. Dorong lurus ke {dir} dan tahan, lalu lepaskan.",
    "check": "Uji {stick} Anda: dorong serong kanan-atas. Titik hijau harus ikut ke kanan-atas.",
    "check_hint": "Titik hijau dan teks menampilkan arah yang diterima game. Bandingkan dengan arah jempol Anda. "
                  "Jika terbalik, centang Balik Arah di bawah.",
    "game_sees": "Game membaca: {where}",
    "center": "TENGAH (CENTER)",
    "flip_x": "Balik kiri / kanan", "flip_y": "Balik atas / bawah",
    "looks_right": "Sudah Sesuai", "redo_stick": "Ulangi Stik Ini",
    "check_done": "Pemeriksaan stik selesai. Tekan Selesai untuk menyimpan.",
    "review": "Semua tombol selesai. Periksa daftar di bawah, lalu tekan Selesai untuk menyimpan.",
    "saved": "Tersimpan! Game akan menggunakan mapping ini saat dijalankan.",
    "cancelled": "Dibatalkan. Perubahan tidak disimpan.",
    "ended": "Mapper berhenti tanpa menyimpan.",
    "not_started": "Mapper tidak dapat dijalankan: {reason}",
    "busy": "Selesaikan atau batalkan proses pemetaan di jendela ini terlebih dahulu.",
    "set": "belum diatur", "skipped": "dilewati", "no_input": "dilewati (tanpa input)", "waiting": "tekan sekarang",
    "map_all": "Petakan Semua", "map_sticks": "Petakan Stik", "map_sticks_only": "Petakan Stik Saja",
    "skip": "Lewati", "cancel": "Batal", "reset": "Reset",
    "done": "Selesai", "use": "Gunakan Kontroler Ini", "manual": "Preset / Manual...",
    "col_pad": "Kontroler", "col_game": "Di Game", "col_set": "Status / Binding",
    "kind_xbox": "{name}: tombol ditampilkan dengan nama tombol Xbox.",
    "kind_playstation": "{name}: tombol ditampilkan dengan nama tombol PlayStation.",
    "kind_other": "{name}: tombol ditampilkan berdasarkan posisinya pada kontroler.",
}

GUIDE_SIZE, GUIDE_RADIUS = 180, 70
FRAME_MS, SLIDE_MS, BLINK_MS = 33, 2200, 1100
STICK_FULL, SEES_DEADZONE, PUSH_SEEN = 32768, 8000, 4000


def apply_dark_titlebar(window):
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def game_sees(x, y, center_text=None):
    """The direction the game receives from SDL values: y is negative when pushed up."""
    vertical = "UP" if y < -SEES_DEADZONE else "DOWN" if y > SEES_DEADZONE else ""
    horizontal = "LEFT" if x < -SEES_DEADZONE else "RIGHT" if x > SEES_DEADZONE else ""
    return "-".join(part for part in (vertical, horizontal) if part) or (center_text or TEXT["center"])


class MapperProcess:
    """basara4-pad-mapper.exe --ui as a child process. Events are read on a thread and queued for the Tk
    thread; commands are written one per line. A line that is not JSON (a plain message) is ignored."""

    def __init__(self, exe, mapping, extra, env):
        self.events = queue.Queue()
        self.proc = subprocess.Popen(
            [str(exe), str(mapping), *extra, "--ui"], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, text=True, encoding="utf-8",
            errors="replace", bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and "ev" in event:
                    self.events.put(event)
        except (OSError, ValueError):
            pass
        finally:
            try:
                self.proc.stdout.close()
            except Exception:
                pass
        self.events.put({"ev": "exit", "code": self.proc.wait()})

    def send(self, command):
        try:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def close(self):
        """Ends the mapper without saving: "cancel", then closed input (which the mapper also reads as
        cancel). A mapper that does not end in 2 seconds is killed; it writes the file only on "save"."""
        if self.proc.poll() is None:
            self.send("cancel")
        try:
            self.proc.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


class StickPanel(tk.Frame):
    """The circle of one stick: the guide (moving white dot, blinking arrow, the player's green dot) or
    the check (green dot = what the game receives, with its direction written under the circle)."""

    def __init__(self, parent, bg, fg, accent):
        super().__init__(parent, bg=bg)
        self.fg, self.accent, self.dim = fg, accent, "#2B4C7E"
        self.canvas = tk.Canvas(self, width=GUIDE_SIZE, height=GUIDE_SIZE, bg=bg, highlightthickness=0)
        self.canvas.pack(side="left", padx=(0, 14))
        c, r = GUIDE_SIZE / 2, GUIDE_RADIUS
        self.canvas.create_oval(c - r, c - r, c + r, c + r, outline=self.dim, width=2)
        self.canvas.create_line(c - r, c, c + r, c, fill=self.dim, dash=(2, 4))
        self.canvas.create_line(c, c - r, c, c + r, fill=self.dim, dash=(2, 4))
        for text, x, y in (("UP", c, c - r - 9), ("DOWN", c, c + r + 9), ("LEFT", c - r + 2, c - 9),
                           ("RIGHT", c + r - 2, c - 9)):
            self.canvas.create_text(x, y, text=text, fill="#60A5FA", font=("Segoe UI", 7, "bold"))
        self.arrow = self.canvas.create_line(c, c, c, c, fill=accent, width=4, arrow="last", state="hidden")
        self.guide_dot = self.canvas.create_oval(0, 0, 0, 0, fill="#ffffff", outline="", state="hidden")
        self.live_dot = self.canvas.create_oval(0, 0, 0, 0, fill="#4ADE80", outline="", state="hidden")
        self.side = tk.Frame(self, bg=bg)
        self.side.pack(side="left", fill="both", expand=True)
        self.direction = (1, 0)
        self.anim_job = None
        self.anim_start = 0.0

    @staticmethod
    def _place(canvas, item, x, y, radius):
        canvas.coords(item, x - radius, y - radius, x + radius, y + radius)

    @staticmethod
    def _in_circle(u, v):
        length = math.hypot(u, v)
        return (u / length, v / length) if length > 1 else (u, v)

    def guide(self, direction):
        self.direction = direction
        c, r = GUIDE_SIZE / 2, GUIDE_RADIUS
        dx, dy = direction
        self.canvas.coords(self.arrow, c + dx * 22, c + dy * 22, c + dx * (r - 6), c + dy * (r - 6))
        self.canvas.itemconfigure(self.arrow, state="normal")
        self.canvas.itemconfigure(self.guide_dot, state="normal")
        self.canvas.itemconfigure(self.live_dot, state="normal")
        self.show_live(0, 0)
        self.anim_start = time.monotonic()
        if self.anim_job is None:
            self._animate()

    def _animate(self):
        self.anim_job = None
        if not self.canvas.winfo_exists():
            return
        elapsed = (time.monotonic() - self.anim_start) * 1000
        out = (1 - math.cos(2 * math.pi * (elapsed % SLIDE_MS) / SLIDE_MS)) / 2
        c, dx, dy = GUIDE_SIZE / 2, *self.direction
        self._place(self.canvas, self.guide_dot, c + dx * out * (GUIDE_RADIUS - 8), c + dy * out * (GUIDE_RADIUS - 8), 8)
        bright = (elapsed % BLINK_MS) < BLINK_MS / 2
        self.canvas.itemconfigure(self.arrow, fill=self.accent if bright else self.dim)
        self.anim_job = self.after(FRAME_MS, self._animate)

    def stop(self):
        if self.anim_job is not None:
            self.after_cancel(self.anim_job)
            self.anim_job = None
        if self.canvas.winfo_exists():
            self.canvas.itemconfigure(self.arrow, state="hidden")
            self.canvas.itemconfigure(self.guide_dot, state="hidden")

    def show_live(self, along, across):
        c, r = GUIDE_SIZE / 2, GUIDE_RADIUS
        dx, dy = self.direction
        a, s = self._in_circle(min(along, STICK_FULL) / STICK_FULL, min(across, STICK_FULL) / STICK_FULL)
        self._place(self.canvas, self.live_dot, c + (dx * a - dy * s) * r, c + (dy * a + dx * s) * r, 6)

    def check(self):
        self.stop()
        self.canvas.itemconfigure(self.live_dot, state="normal")
        self.show_game(0, 0)

    def show_game(self, x, y):
        c, r = GUIDE_SIZE / 2, GUIDE_RADIUS
        u, v = self._in_circle(max(-1.0, min(1.0, x / STICK_FULL)), max(-1.0, min(1.0, y / STICK_FULL)))
        self._place(self.canvas, self.live_dot, c + u * r, c + v * r, 7)

    def live_dot_center(self):
        x0, y0, x1, y1 = self.canvas.coords(self.live_dot)
        return (x0 + x1) / 2, (y0 + y1) / 2


class ControllerWindow(tk.Toplevel):
    """Map all / Map sticks only / Skip / Cancel / Reset / Done, the list of entries, what to press now,
    the stick guide and the stick check — styled in Timotius's Date Masamune Dark Navy & Samurai Red theme."""

    def __init__(self, parent, exe, mapping, env, sticks_only=False, on_saved=None, on_reset=None,
                 colors=None, lang="en", on_manual=None):
        super().__init__(parent)
        self.exe, self.mapping, self.env, self.sticks_only = Path(exe), Path(mapping), env, sticks_only
        self.on_saved, self.on_reset, self.on_manual = on_saved, on_reset, on_manual
        self.lang = lang if lang in ("en", "id") else "en"
        self.txt = TEXT_ID if self.lang == "id" else TEXT
        self.mapper = None
        self.pump_job = None
        self.state = "idle"
        self.finished = False
        self.error_shown = False
        self.asking = None
        self.kind = "other"
        self.bindings = {}
        self.checks = None
        self.checks_total = 0
        self.redo_left = 0
        self._backup_bytes = None

        colors = colors or {}
        bg = colors.get("bg", "#070E20")
        panel = colors.get("panel", "#0A142F")
        fg = colors.get("fg", "#F1F5F9")
        accent = colors.get("accent", "#FF4242")
        border = colors.get("border", "#1E88E5")
        self._bg, self._panel, self._fg, self._accent = bg, panel, fg, accent

        self.title(self.txt["title"])
        self.configure(bg=bg)
        self.transient(parent)
        self.geometry("680x560")
        self.minsize(580, 480)
        if hasattr(parent, "_apply_window_icon"):
            try:
                parent._apply_window_icon(self)
            except Exception:
                pass
        apply_dark_titlebar(self)

        banner = tk.Frame(self, bg=panel, padx=14, pady=10, highlightbackground=border, highlightthickness=1)
        banner.pack(fill="x", padx=12, pady=(12, 6))
        self.prompt = tk.Label(banner, text="", bg=panel, fg=accent, font=("Segoe UI", 11, "bold"),
                               wraplength=610, justify="left", anchor="w")
        self.prompt.pack(fill="x")
        self.detail = tk.Label(banner, text="", bg=panel, fg=fg, font=("Segoe UI", 9), wraplength=610,
                               justify="left", anchor="w")
        self.detail.pack(fill="x", pady=(4, 0))
        self.chooser = tk.Frame(banner, bg=panel)
        self.device_var = tk.StringVar()
        self.device_list = ttk.Combobox(self.chooser, textvariable=self.device_var, state="readonly", width=48)
        self.device_list.pack(side="left")
        ttk.Button(self.chooser, text=self.txt["use"], command=self._use_device).pack(side="left", padx=(8, 0))
        self.devices = []

        style = ttk.Style(self)
        style.configure("Pad.TFrame", background=bg)
        style.configure("PadPanel.TFrame", background=panel)
        style.configure("Pad.TButton", background="#102044", foreground=fg, padding=(10, 5), borderwidth=1,
                        font=("Segoe UI Semibold", 9))
        style.map("Pad.TButton",
                  background=[("active", "#1E3A6E"), ("disabled", "#081022")],
                  foreground=[("active", "#FFFFFF"), ("disabled", "#4A5A70")])
        style.configure("PadAccent.TButton", background=accent, foreground="#FFFFFF", padding=(12, 5), borderwidth=0,
                        font=("Segoe UI Bold", 9))
        style.map("PadAccent.TButton",
                  background=[("active", "#FF5E5E"), ("disabled", "#3A1520")],
                  foreground=[("disabled", "#7A5A60")])
        style.configure("Pad.TCheckbutton", background=panel, foreground=fg, font=("Segoe UI", 9))
        style.map("Pad.TCheckbutton", background=[("active", panel)], foreground=[("active", "#E5C168")])

        self.buttons = ttk.Frame(self, style="Pad.TFrame", padding=(12, 6, 12, 12))
        self.buttons.pack(side="bottom", fill="x")
        self.map_all = ttk.Button(self.buttons, text=self.txt["map_sticks" if sticks_only else "map_all"],
                                  style="PadAccent.TButton", command=self.start)
        self.map_sticks = ttk.Button(self.buttons, text=self.txt["map_sticks_only"],
                                     style="Pad.TButton", command=self.start_sticks_only)
        self.temp_sticks = False
        self.skip = ttk.Button(self.buttons, text=self.txt["skip"], style="Pad.TButton",
                               command=lambda: self._send("skip"))
        self.cancel = ttk.Button(self.buttons, text=self.txt["cancel"], style="Pad.TButton",
                                 command=lambda: self._send("cancel"))
        self.reset = ttk.Button(self.buttons, text=self.txt["reset"], style="Pad.TButton", command=self._reset)
        self.done = ttk.Button(self.buttons, text=self.txt["done"], style="PadAccent.TButton", command=self._done)
        for button in (self.map_all, self.map_sticks, self.skip, self.cancel, self.reset):
            button.pack(side="left", padx=(0, 6))
        if self.on_manual:
            self.manual_btn = ttk.Button(self.buttons, text=self.txt["manual"], style="Pad.TButton",
                                         command=self._open_manual)
            self.manual_btn.pack(side="left", padx=(0, 6))
        self.done.pack(side="right")

        # Stick guidance & verification panel
        self.stick_area = tk.Frame(self, bg=panel, padx=14, pady=10, highlightbackground=border, highlightthickness=1)
        self.stick = StickPanel(self.stick_area, panel, fg, accent)
        self.stick.pack(fill="x")
        side = self.stick.side
        step_list = STICK_STEPS_ID if self.lang == "id" else STICK_STEPS
        self.steps = [tk.Label(side, text="", bg=panel, fg=fg, font=("Segoe UI", 9), anchor="w")
                      for _ in step_list]
        self.you = tk.Label(side, text="", bg=panel, fg="#4ADE80", font=("Segoe UI", 9, "bold"), anchor="w",
                            wraplength=340, justify="left")
        self.sees = tk.Label(side, text="", bg=panel, fg="#4ADE80", font=("Segoe UI", 11, "bold"), anchor="w")
        self.flip_x_var, self.flip_y_var = tk.BooleanVar(), tk.BooleanVar()
        self.flip_x = ttk.Checkbutton(side, text=self.txt["flip_x"], variable=self.flip_x_var,
                                      style="Pad.TCheckbutton", command=lambda: self._flip(2))
        self.flip_y = ttk.Checkbutton(side, text=self.txt["flip_y"], variable=self.flip_y_var,
                                      style="Pad.TCheckbutton", command=lambda: self._flip(3))
        self.check_buttons = ttk.Frame(side, style="PadPanel.TFrame")
        self.looks_right = ttk.Button(self.check_buttons, text=self.txt["looks_right"],
                                      style="PadAccent.TButton", command=self._looks_right)
        self.redo_stick = ttk.Button(self.check_buttons, text=self.txt["redo_stick"],
                                     style="Pad.TButton", command=self._redo_stick)
        self.looks_right.pack(side="left", padx=(0, 8))
        self.redo_stick.pack(side="left")

        table = tk.Frame(self, bg=panel, highlightbackground=border, highlightthickness=1)
        table.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        style.configure("Pad.Treeview", background="#060C1E", fieldbackground="#060C1E", foreground="#FF5E5E",
                        rowheight=24, borderwidth=0, font=("Segoe UI", 9))
        style.map("Pad.Treeview", background=[("selected", "#1E3A6E")], foreground=[("selected", "#FFFFFF")])
        style.configure("Pad.Treeview.Heading", background="#0A142F", foreground=accent, relief="flat",
                        font=("Segoe UI Bold", 9))
        style.map("Pad.Treeview.Heading", background=[("active", "#15244E")])
        self.rows = ttk.Treeview(table, columns=("pad", "game", "set"), show="headings", height=12,
                                 selectmode="browse", style="Pad.Treeview")
        for column, title, width in (("pad", self.txt["col_pad"], 270),
                                     ("game", self.txt["col_game"], 150),
                                     ("set", self.txt["col_set"], 130)):
            self.rows.heading(column, text=title)
            self.rows.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.rows.yview)
        self.rows.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.rows.pack(side="left", fill="both", expand=True)
        self._fill_rows()
        self.table = table

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Destroy>", self._destroyed, add="+")
        self._show_state("idle")
        self._say(self.txt["idle_saved"] if self.mapping.exists() else self.txt["idle"])

    def _open_manual(self):
        if self.mapper:
            self._say(self.txt["busy"])
            return
        cb = self.on_manual
        self.close()
        if cb:
            cb()

    def _entries(self):
        return [entry for entry in ENTRIES if not self.sticks_only or entry[0] in STICKS]

    def _names(self):
        return [name for name, _pad, _game in self._entries()]

    def _fill_rows(self):
        self.rows.delete(*self.rows.get_children())
        for name, _pad, _game in self._entries():
            self.rows.insert("", "end", iid=name,
                             values=(pad_label(name, self.kind, self.lang), game_label(name, self.lang), self.txt["set"]))

    def _set_kind(self, kind):
        self.kind = kind if kind in LABELS else "other"
        for name in self.rows.get_children():
            _pad, game, recorded = self.rows.item(name, "values")
            self.rows.item(name, values=(pad_label(name, self.kind, self.lang), game, recorded))

    def set_sticks_only(self, sticks_only):
        if self.mapper:
            self._say(self.txt["busy"])
            return False
        if sticks_only != self.sticks_only:
            self.sticks_only = sticks_only
            self.map_all.config(text=self.txt["map_sticks" if sticks_only else "map_all"])
            self._fill_rows()
        return True

    def start_sticks_only(self):
        if self.mapper:
            return
        was_sticks_only = self.sticks_only
        self.set_sticks_only(True)
        self.temp_sticks = not was_sticks_only
        self.start()
        if not self.mapper:
            self._leave_temporary_sticks()

    def _leave_temporary_sticks(self):
        if self.temp_sticks:
            self.temp_sticks = False
            self.set_sticks_only(False)

    def _snapshot_backup(self):
        try:
            if self.mapping.is_file() and self.mapping.stat().st_size > 0:
                self._backup_bytes = self.mapping.read_bytes()
            else:
                self._backup_bytes = None
        except OSError:
            self._backup_bytes = None

    def _restore_backup_if_corrupted(self):
        """Atomic save safeguard: if a failed save left gamepad_mapping.txt missing or empty,
        restore the previous valid mapping."""
        if self._backup_bytes:
            try:
                if not self.mapping.is_file() or self.mapping.stat().st_size == 0:
                    self.mapping.parent.mkdir(parents=True, exist_ok=True)
                    tmp = self.mapping.with_name(self.mapping.name + ".restore.tmp")
                    tmp.write_bytes(self._backup_bytes)
                    os.replace(tmp, self.mapping)
            except OSError:
                pass

    def start(self):
        if self.mapper:
            return
        self._snapshot_backup()
        self._fill_rows()
        try:
            self.mapper = MapperProcess(self.exe, self.mapping, ["--sticks"] if self.sticks_only else [], self.env)
        except OSError as exc:
            self._say(self.txt["not_started"].format(reason=exc.strerror or exc))
            return
        self.finished = self.error_shown = False
        self.bindings, self.checks, self.asking, self.checks_total, self.redo_left = {}, None, None, 0, 0
        self._show_state("mapping")
        self._say(self.txt["starting"])
        self.pump_job = self.after(FRAME_MS, self._pump)

    def _pump(self):
        self.pump_job = None
        mapper = self.mapper
        if not mapper:
            return
        try:
            while self.mapper is mapper:
                self.handle(mapper.events.get_nowait())
        except queue.Empty:
            pass
        if self.mapper is mapper:
            self.pump_job = self.after(FRAME_MS, self._pump)

    def _send(self, command):
        if self.mapper:
            self.mapper.send(command)

    def handle(self, event):
        kind, target = event.get("ev"), event.get("target")
        if kind == "devices":
            self.devices = event.get("list") or []
            if len(self.devices) > 1:
                self.device_list["values"] = [d.get("name", "Gamepad") for d in self.devices]
                self.device_list.current(0)
                self._say(self.txt["choose"])
                self.chooser.pack(fill="x", pady=(8, 0))
        elif kind == "controller":
            self.chooser.pack_forget()
            self._set_kind(event.get("kind"))
            self.detail.config(text=self.txt[f"kind_{self.kind}"].format(name=event.get("name", "") or "Controller"))
        elif kind == "prompt" and target in self._names():
            self.error_shown = False
            self._ask(target)
        elif kind in ("captured", "flipped") and target in self._names():
            self.bindings[target] = event.get("binding", "")
            self._set(target, event.get("binding", ""))
        elif kind == "timeout" and target in self._names():
            self.bindings.pop(target, None)
            self._set(target, self.txt["no_input"])
        elif kind == "skipped" and target in self._names():
            self.bindings.pop(target, None)
            self._set(target, self.txt["skipped"])
        elif kind == "used":
            self.detail.config(text=self.txt["used"])
        elif kind == "warn" and event.get("reason") in ("stick_rotated", "stick_two_axes"):
            step = self._step(target)
            default_dir = "arah yang ditunjuk" if self.lang == "id" else "in the direction shown"
            self.detail.config(text=self.txt[event["reason"]].format(dir=step[2] if step else default_dir))
        elif kind == "live":
            self._live(target, event)
        elif kind == "review":
            self._review()
        elif kind == "saved":
            self.finished = True
            self._hide_sticks()
            self._say(self.txt["saved"])
            if self.on_saved:
                self.on_saved()
        elif kind == "cancelled":
            self.finished = True
            self._restore_backup_if_corrupted()
            self._hide_sticks()
            self._say(self.txt["cancelled"])
        elif kind == "error":
            self.error_shown = True
            self._restore_backup_if_corrupted()
            if self.redo_left and self.asking is None and self.checks:
                self.redo_left = 0
                self._start_check()
                self.detail.config(text=event.get("message", ""))
            else:
                self._say(event.get("message", ""))
        elif kind == "exit":
            code = event.get("code")
            if code != 0:
                self._restore_backup_if_corrupted()
            explained = (code in (0, 2) and self.finished) or (code == 1 and self.error_shown)
            mapper, self.mapper = self.mapper, None
            if mapper:
                mapper.close()
            self._hide_sticks()
            if not explained:
                self._say(self.txt["ended"])
            self._show_state("idle")
            self._leave_temporary_sticks()

    def _step(self, target):
        steps = STICK_STEPS_ID if self.lang == "id" else STICK_STEPS
        return next((step for step in steps if step[0] == target), None)

    def _ask(self, target):
        pad, game = pad_label(target, self.kind, self.lang), game_label(target, self.lang)
        names = self._names()
        self.asking = target
        self._show_state("mapping")
        step = self._step(target)
        steps = STICK_STEPS_ID if self.lang == "id" else STICK_STEPS
        if step:
            _name, stick, direction, vector = step
            self.prompt.config(text=self.txt["stick"].format(stick=stick, n=steps.index(step) + 1, dir=direction))
            self.detail.config(text=self.txt["stick_hint"])
            self._show_guide(target, vector)
        else:
            self._hide_sticks()
            self.prompt.config(text=self.txt["button"].format(pad=pad, game=game))
            self.detail.config(text=self.txt["progress"].format(n=names.index(target) + 1, total=len(names)))
        self.rows.item(target, values=(pad, game, self.txt["waiting"]))
        self.rows.see(target)
        self.rows.selection_set(target)

    def _set(self, target, value):
        pad, game = pad_label(target, self.kind, self.lang), game_label(target, self.lang)
        self.rows.item(target, values=(pad, game, value))

    def _say(self, text):
        self.prompt.config(text=text)
        if not self.mapper:
            self.detail.config(text="")

    def _show_state(self, state):
        self.state = state
        enabled = {"idle": {self.map_all, self.map_sticks, self.reset, self.done}, "mapping": {self.skip, self.cancel},
                   "review": {self.done, self.cancel}, "check": {self.cancel}}[state]
        for button in (self.map_all, self.map_sticks, self.skip, self.cancel, self.reset, self.done):
            button.state(["!disabled"] if button in enabled else ["disabled"])

    def _show_stick_area(self):
        if not self.stick_area.winfo_manager():
            self.stick_area.pack(fill="x", padx=12, pady=(0, 6), before=self.table)

    def _hide_sticks(self):
        self.stick.stop()
        self.stick_area.pack_forget()

    def _show_guide(self, target, vector):
        for widget in (self.sees, self.flip_x, self.flip_y, self.check_buttons):
            widget.pack_forget()
        steps = STICK_STEPS_ID if self.lang == "id" else STICK_STEPS
        current = [step[0] for step in steps].index(target)
        for index, (label, (_name, stick, direction, _v)) in enumerate(zip(self.steps, steps)):
            marker = "► " if index == current else "   "
            if self.lang == "id":
                when = "sekarang" if index == current else "selesai" if index < current else "berikutnya"
                push_txt = f"{marker}{index + 1}. {stick} → dorong ke {direction}  ({when})"
            else:
                when = "now" if index == current else "done" if index < current else "next"
                push_txt = f"{marker}{index + 1}. {stick} → push {direction}  ({when})"
            label.config(text=push_txt, fg=self.stick.accent if index == current else self.stick.fg)
            label.pack(fill="x")
        self.you.config(text=self.txt["stick_waiting"].format(dir=self._step(target)[2]))
        self.you.pack(fill="x", pady=(8, 0))
        self._show_stick_area()
        self.stick.guide(vector)

    def _live(self, target, event):
        if self.state == "mapping" and target == self.asking and self._step(target):
            push, side = int(event.get("push", 0)), int(event.get("side", 0))
            self.stick.show_live(push, side)
            direction = self._step(target)[2]
            self.you.config(text=self.txt["stick_moving" if push >= PUSH_SEEN else "stick_waiting"].format(dir=direction))
        elif self.state == "check" and self.checks and target == self.checks[0][0]:
            x, y = int(event.get("x", 0)), int(event.get("y", 0))
            self.stick.show_game(x, y)
            self.sees.config(text=self.txt["game_sees"].format(where=game_sees(x, y, self.txt["center"])))

    def _review(self):
        self.asking = None
        if self.state == "check":
            return
        if self.redo_left:
            self.redo_left -= 1
            if self.redo_left:
                self.stick.stop()
                return
        check_sides = CHECK_SIDES_ID if self.lang == "id" else CHECK_SIDES
        if self.checks is None:
            self.checks = [side for side in check_sides
                           if self.bindings.get(side[2], "").startswith("a")
                           or self.bindings.get(side[3], "").startswith("a")]
            self.checks_total = len(self.checks)
        if self.checks:
            self._start_check()
        else:
            self._hide_sticks()
            self._show_state("review")
            self._say(self.txt["check_done"] if self.checks_total else self.txt["review"])

    def _start_check(self):
        side, stick, x_entry, y_entry = self.checks[0]
        self._show_state("check")
        self.prompt.config(text=self.txt["check"].format(stick=stick))
        self.detail.config(text=self.txt["check_hint"])
        for label in self.steps:
            label.pack_forget()
        self.you.pack_forget()
        self.flip_x_var.set(False)
        self.flip_y_var.set(False)
        self.flip_x.state(["!disabled"] if self.bindings.get(x_entry, "").startswith("a") else ["disabled"])
        self.flip_y.state(["!disabled"] if self.bindings.get(y_entry, "").startswith("a") else ["disabled"])
        self.sees.config(text=self.txt["game_sees"].format(where=self.txt["center"]))
        for widget in (self.sees, self.flip_x, self.flip_y):
            widget.pack(fill="x", pady=(0, 4))
        self.check_buttons.pack(fill="x", pady=(8, 0))
        self._show_stick_area()
        self.stick.check()
        self._send(f"check {side}")

    def _flip(self, column):
        if self.checks:
            self._send(f"flip {self.checks[0][column]}")

    def _looks_right(self):
        if not self.checks:
            return
        self.checks.pop(0)
        if self.checks:
            self._start_check()
        else:
            self._send("check off")
            self._hide_sticks()
            self._show_state("review")
            self._say(self.txt["check_done"])

    def _redo_stick(self):
        if not self.checks:
            return
        _side, _stick, x_entry, y_entry = self.checks[0]
        self.redo_left = 2
        self._send("check off")
        for entry in (x_entry, y_entry):
            self._send(f"redo {entry}")

    def _use_device(self):
        index = self.device_list.current()
        if 0 <= index < len(self.devices):
            self._send(f"select {self.devices[index].get('i', index)}")
            self.chooser.pack_forget()

    def _done(self):
        if self.state == "review":
            self._send("save")
        else:
            self.close()

    def _reset(self):
        if self.on_reset:
            self.on_reset()
        self._say(self.txt["idle_saved"] if self.mapping.exists() else self.txt["idle"])

    def close(self):
        self._stop()
        self.destroy()

    def _destroyed(self, event):
        if event.widget is self:
            self._stop()

    def _stop(self):
        self.stick.stop()
        if self.pump_job:
            self.after_cancel(self.pump_job)
            self.pump_job = None
        mapper, self.mapper = self.mapper, None
        if mapper:
            mapper.close()
        self._restore_backup_if_corrupted()
