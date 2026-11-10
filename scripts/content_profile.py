"""Prepare explicit offline AppContent metadata (Flexible DLC Scanner)."""
import argparse
import json
import os
import struct
from pathlib import Path
from prepare import read_sfo, sfo

MAX_ADDONS = 64
ADDON_LABEL_LENGTH = 16


def _ensure_dlc_junction(source_dir, target_link):
    """Ensure target_link is a junction/symlink pointing to source_dir."""
    try:
        source_dir = Path(source_dir).resolve()
        target_link = Path(target_link)
        if target_link.resolve() == source_dir:
            return
        if target_link.exists() or target_link.is_symlink():
            if target_link.is_dir() and not target_link.is_symlink():
                # Real directory with files, do not overwrite
                return
            target_link.unlink(missing_ok=True)
        import _winapi
        _winapi.CreateJunction(str(source_dir), str(target_link))
    except Exception:
        try:
            target_link.symlink_to(source_dir, target_is_directory=True)
        except Exception:
            pass


def extract_entitlement_label(content_id, folder_name=""):
    """Extract and validate 16-character ASCII entitlement label from CONTENT_ID or folder name."""
    label = ""
    if content_id:
        if "_00-" in content_id:
            label = content_id.split("_00-")[-1][:16]
        elif len(content_id) >= 36:
            label = content_id[20:36]
        elif len(content_id) >= 16:
            label = content_id[-16:]
        else:
            label = content_id.ljust(16, "0")
    if not label and folder_name:
        label = folder_name[:16]
    clean = "".join(c if (c.isalnum() or c == "_") else "_" for c in label)
    if not clean:
        clean = "DLC0000000000001"
    return clean.ljust(16, "0")[:16]


def find_addons(dlc_dir, title_id):
    """Flexible DLC Scanner: Dynamically detect extracted add-on folders under DLC/ or user/dlc/."""
    addons = {}
    searched_dirs = []
    root_dir = Path(__file__).resolve().parent.parent
    user_dlc_dir = root_dir / "user" / "dlc"
    user_dlc_dir.mkdir(parents=True, exist_ok=True)

    if dlc_dir and str(dlc_dir).strip():
        p = Path(dlc_dir)
        if p.is_dir() and p not in searched_dirs:
            searched_dirs.append(p)

    default_dlc_dirs = [
        root_dir / "DLC" / "DLC" / "CUSA01159",
        root_dir / "DLC",
        user_dlc_dir,
        root_dir.parent / "DLC",
        root_dir / "game",
    ]
    for d in default_dlc_dirs:
        if d.is_dir() and d not in searched_dirs:
            searched_dirs.append(d)

    seen_folders = set()

    for target_dir in searched_dirs:
        try:
            for root, dirs, files in os.walk(target_dir):
                rel_parts = Path(root).relative_to(target_dir).parts
                if len(rel_parts) > 5:
                    dirs.clear()
                    continue

                if "sce_sys" in dirs:
                    cand_path = Path(root)
                    real_path = cand_path.resolve()
                    if real_path in seen_folders:
                        dirs.clear()
                        continue
                    seen_folders.add(real_path)

                    sfo_path = cand_path / "sce_sys" / "param.sfo"
                    if not sfo_path.is_file():
                        dirs.clear()
                        continue

                    values = read_sfo(sfo_path)
                    if not values:
                        print(f"DLC: skipped {cand_path.name}: unreadable param.sfo")
                        dirs.clear()
                        continue

                    cand_title_id = values.get("TITLE_ID", "")
                    if cand_title_id and cand_title_id != title_id:
                        dirs.clear()
                        continue

                    # Skip main game base installation itself (eboot.bin)
                    if cand_path.name == title_id and (cand_path / "eboot.bin").is_file():
                        dirs.clear()
                        continue

                    content = values.get("CONTENT_ID", "")
                    label = extract_entitlement_label(content, cand_path.name)

                    # Ensure junction exists at user_dlc_dir / label
                    _ensure_dlc_junction(cand_path, user_dlc_dir / label)
                    if dlc_dir and Path(dlc_dir).is_dir():
                        _ensure_dlc_junction(cand_path, Path(dlc_dir) / label)

                    title = values.get("TITLE", label)
                    addons.setdefault(label, (label, title, cand_path.name))
                    dirs.clear()
                    continue
        except OSError:
            pass

    all_addons = list(addons.values())
    for label, _title, _source in all_addons[MAX_ADDONS:]:
        print(f"DLC: skipped {label}: runtime supports at most {MAX_ADDONS} add-ons")
    result = all_addons[:MAX_ADDONS]
    for label, title, source in result:
        printable_title = title.encode("ascii", "backslashreplace").decode("ascii")
        print(f"DLC: ready to mount {printable_title} ({label}, {source})")
    return result


def prepare(game, out, sku="full", dlc_dir=None):
    values = sfo((game / "sce_sys/param.sfo").read_bytes())
    params = [values.get(f"USER_DEFINED_PARAM_{i}", 0) for i in range(1, 5)]
    if any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in params):
        raise ValueError("invalid user-defined parameter")
    addons = find_addons(dlc_dir, values.get("TITLE_ID"))
    profile = dict(
        title_id=values.get("TITLE_ID"),
        sku=sku,
        sku_source="explicit probe setting",
        user_params=params,
        mounted_addons=[dict(label=l, title=t, source=s) for l, t, s in addons],
        boot_attr=0,
    )
    out.mkdir(parents=True, exist_ok=True)
    blob = struct.pack("<8s6I", b"G3CONT02", {"full": 3, "trial": 1}[sku], *params, len(addons))
    for label, _title, _source in addons:
        blob += label.encode("ascii") + b"\0"
    (out / "content.bin").write_bytes(blob)
    (out / "content-profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    print(f"AppContent profile: SKU={sku} (probe setting), user params={params}, add-ons={len(addons)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("game", type=Path)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "out")
    p.add_argument("--sku", choices=["full", "trial"], default="full")
    p.add_argument("--dlc-dir", type=Path, help="folder containing extracted DLC folders")
    a = p.parse_args()
    prepare(a.game, a.out, a.sku, a.dlc_dir)
