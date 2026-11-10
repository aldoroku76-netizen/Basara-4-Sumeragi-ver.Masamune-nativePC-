"""Build and packaging script for Sengoku Basara 4 Launcher.

Compiles launcher/basara4_launcher.py with the bundled Python 3.12 runtime and
injects the bytecode into the PyInstaller executables ('Sengoku Basara 4.exe' and 'Basara4Launcher.exe').
"""
import ctypes
import os
import shutil
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_PY = ROOT / "launcher" / "basara4_launcher.py"
PYC_RAW = ROOT / "launcher" / "basara4_launcher.pyc_raw"
ORIG_EXE = ROOT / "Sengoku Basara 4.exe.orig"
if not ORIG_EXE.is_file() and (ROOT / "assets" / "Sengoku Basara 4.exe.orig").is_file():
    ORIG_EXE = ROOT / "assets" / "Sengoku Basara 4.exe.orig"
TARGET_EXE1 = ROOT / "Sengoku Basara 4.exe"
TARGET_EXE2 = ROOT / "Basara4Launcher.exe"


def compile_with_python312():
    print(f"[*] Compiling {LAUNCHER_PY} using _internal/python312.dll...")
    os.environ["PYTHONPATH"] = str(ROOT / "_internal" / "base_library.zip") + ";" + str(ROOT / "_internal")
    os.environ["PYTHONHOME"] = str(ROOT / "_internal")

    dll_path = str(ROOT / "_internal" / "python312.dll")
    py312 = ctypes.CDLL(dll_path)
    py312.Py_InitializeEx.argtypes = [ctypes.c_int]
    py312.Py_InitializeEx.restype = None
    py312.Py_InitializeEx(0)

    code = f"""
import marshal
src = open(r"{LAUNCHER_PY}", "r", encoding="utf-8").read()
co = compile(src, "basara4_launcher.py", "exec")
with open(r"{PYC_RAW}", "wb") as f:
    marshal.dump(co, f)
print("SUCCESSFULLY COMPILED bytecode with Python 3.12 DLL!")
"""
    py312.PyRun_SimpleString.argtypes = [ctypes.c_char_p]
    py312.PyRun_SimpleString.restype = ctypes.c_int
    res = py312.PyRun_SimpleString(code.encode("utf-8"))
    py312.Py_FinalizeEx.restype = ctypes.c_int
    py312.Py_FinalizeEx()

    if res != 0 or not PYC_RAW.is_file():
        raise RuntimeError(f"Compilation failed with exit code {res}")
    print(f"[+] Bytecode written to {PYC_RAW} ({PYC_RAW.stat().st_size} bytes)")


def rebuild_pyinstaller_exe(orig_exe_path, pyc_path, out_exe_path):
    print(f"[*] Injecting bytecode into {out_exe_path.name}...")
    with open(orig_exe_path, "rb") as f:
        exe_data = f.read()

    with open(pyc_path, "rb") as f:
        pyc_data = f.read()

    magic = b"MEI\x0c\x0b\n\x0b\x0e"
    c_idx = exe_data.rfind(magic)
    if c_idx == -1:
        raise ValueError("Could not find PyInstaller cookie in base executable")

    _, orig_archive_len, orig_toc_offset, orig_toc_len, pyvers, pylib = struct.unpack(
        "!8sIIii64s", exe_data[c_idx:c_idx + 88]
    )
    archive_start = (c_idx + 88) - orig_archive_len

    # Parse TOC
    curr = archive_start + orig_toc_offset
    entries = []
    while curr < archive_start + orig_toc_offset + orig_toc_len:
        entry_len, = struct.unpack("!I", exe_data[curr:curr + 4])
        pos, dlen, ulen, cflag, typcd = struct.unpack("!IIIbb", exe_data[curr + 4:curr + 18])
        name = exe_data[curr + 18:curr + entry_len].rstrip(b"\x00")
        entries.append({
            "name": name,
            "pos": pos,
            "len": dlen,
            "ulen": ulen,
            "cflag": cflag,
            "typcd": typcd,
            "raw_entry": bytearray(exe_data[curr:curr + entry_len]),
        })
        curr += entry_len

    # Compress new bytecode
    new_compressed = zlib.compress(pyc_data, 9)
    new_dlen = len(new_compressed)
    new_ulen = len(pyc_data)

    launcher_entry = next(e for e in entries if e["name"] == b"basara4_launcher")
    orig_pos = launcher_entry["pos"]
    orig_dlen = launcher_entry["len"]
    delta = new_dlen - orig_dlen

    bootloader_and_prefix = exe_data[:archive_start + orig_pos]
    orig_launcher_end = archive_start + orig_pos + orig_dlen
    archive_middle = exe_data[orig_launcher_end:archive_start + orig_toc_offset]

    for e in entries:
        if e["name"] == b"basara4_launcher":
            e["len"] = new_dlen
            e["ulen"] = new_ulen
            e["cflag"] = 1
        elif e["pos"] > orig_pos:
            e["pos"] += delta
        struct.pack_into("!IIIbb", e["raw_entry"], 4, e["pos"], e["len"], e["ulen"], e["cflag"], e["typcd"])

    new_toc_data = b"".join(e["raw_entry"] for e in entries)
    new_toc_offset = orig_toc_offset + delta
    new_archive_len = orig_archive_len + delta

    new_cookie = struct.pack(
        "!8sIIii64s", magic, new_archive_len, new_toc_offset, len(new_toc_data), pyvers, pylib
    )

    final_data = bootloader_and_prefix + new_compressed + archive_middle + new_toc_data + new_cookie

    with open(out_exe_path, "wb") as f:
        f.write(final_data)

    print(f"[+] Successfully rebuilt {out_exe_path} (size: {len(final_data)} bytes)")


def update_pe_icon(exe_path, ico_path):
    """Inject multi-resolution icon directly into PE header without disturbing PyInstaller overlay."""
    kernel32 = ctypes.windll.kernel32
    exe_path = Path(exe_path).resolve()
    ico_path = Path(ico_path).resolve()

    full_data = exe_path.read_bytes()
    magic = b"MEI\x0c\x0b\n\x0b\x0e"
    c_idx = full_data.rfind(magic)
    if c_idx == -1:
        return
    _, orig_archive_len, orig_toc_offset, orig_toc_len, pyvers, pylib = struct.unpack("!8sIIii64s", full_data[c_idx:c_idx + 88])
    archive_start = (c_idx + 88) - orig_archive_len
    pe_data = full_data[:archive_start]
    overlay_data = full_data[archive_start:]

    temp_pe = ROOT / "scratch" / "temp_pe.exe"
    temp_pe.parent.mkdir(parents=True, exist_ok=True)
    temp_pe.write_bytes(pe_data)

    ico_data = ico_path.read_bytes()
    reserved, typ, count = struct.unpack("<HHH", ico_data[:6])
    ico_entries = []
    for i in range(count):
        off = 6 + i * 16
        w, h, colors, res, planes, bpp, size, offset = struct.unpack("<BBBBHHII", ico_data[off:off+16])
        ico_entries.append({
            "w": w, "h": h, "colors": colors, "res": res, "planes": planes, "bpp": bpp,
            "size": size, "offset": offset, "data": ico_data[offset:offset+size]
        })

    grp_header = struct.pack("<HHH", 0, 1, count)
    grp_entries = bytearray()
    for idx, e in enumerate(ico_entries, start=1):
        grp_entries += struct.pack("<BBBBHHIH", e["w"], e["h"], e["colors"], e["res"], e["planes"], e["bpp"], e["size"], idx)
    grp_data = grp_header + bytes(grp_entries)

    h_update = kernel32.BeginUpdateResourceW(str(temp_pe), False)
    if not h_update:
        return

    from ctypes import wintypes
    RT_ICON = ctypes.cast(3, wintypes.LPCWSTR)
    RT_GROUP_ICON = ctypes.cast(14, wintypes.LPCWSTR)

    for idx, e in enumerate(ico_entries, start=1):
        icon_id = ctypes.cast(idx, wintypes.LPCWSTR)
        raw_buf = (ctypes.c_char * len(e["data"])).from_buffer_copy(e["data"])
        kernel32.UpdateResourceW(h_update, RT_ICON, icon_id, 0, raw_buf, len(e["data"]))

    grp_buf = (ctypes.c_char * len(grp_data)).from_buffer_copy(grp_data)
    kernel32.UpdateResourceW(h_update, RT_GROUP_ICON, ctypes.cast(1, wintypes.LPCWSTR), 0, grp_buf, len(grp_data))
    kernel32.EndUpdateResourceW(h_update, False)

    new_pe_data = temp_pe.read_bytes()
    final_data = new_pe_data + overlay_data
    exe_path.write_bytes(final_data)
    print(f"[+] Injected Yukimura icon ({count} frames) into {exe_path.name}")


def main():
    compile_with_python312()
    rebuild_pyinstaller_exe(ORIG_EXE, PYC_RAW, TARGET_EXE1)
    # Also create Basara4Launcher.exe so both executable references work
    rebuild_pyinstaller_exe(ORIG_EXE, PYC_RAW, TARGET_EXE2)
    
    # Guarantee Yukimura icon is embedded in both binaries
    yukimura_ico = ROOT / "basara4.ico"
    if yukimura_ico.is_file():
        update_pe_icon(TARGET_EXE1, yukimura_ico)
        update_pe_icon(TARGET_EXE2, yukimura_ico)
    print("\n[SUCCESS] Build completed successfully!")


if __name__ == "__main__":
    main()

