"""Read visible metadata from extracted Basara 4 add-on folders (Flexible DLC Scanner)."""
import os
from pathlib import Path
import struct
import hashlib

EXPECTED_TITLE_ID = "CUSA01159"
MAX_ENTRIES = 4096


def _parse_sfo(data):
    if len(data) < 20:
        raise ValueError("param.sfo is truncated")
    magic, _version, key_offset, data_offset, count = struct.unpack_from("<4sIIII", data)
    if magic != b"\0PSF" or count > MAX_ENTRIES:
        raise ValueError("invalid param.sfo")
    index_end = 20 + count * 16
    if not index_end <= key_offset <= data_offset <= len(data):
        raise ValueError("invalid param.sfo offsets")

    values = {}
    for index in range(count):
        key_at, _format, length, _maximum, value_at = struct.unpack_from(
            "<HHIII", data, 20 + index * 16)
        key_start = key_offset + key_at
        key_end = data.find(b"\0", key_start, data_offset)
        value_start = data_offset + value_at
        value_end = value_start + length
        if key_start >= data_offset or key_end < 0 or value_end > len(data):
            raise ValueError("param.sfo entry is out of bounds")
        key = data[key_start:key_end].decode("utf-8", "replace")
        value = data[value_start:value_end].split(b"\0", 1)[0].decode("utf-8", "replace")
        values[key] = value
    return values


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


def read_extracted_dlc(path, lang="en", skip_base_game=True):
    """Return user-visible metadata for a valid extracted add-on directory (Flexible DLC Scanner)."""
    path = Path(path)
    if not path.is_dir():
        raise ValueError("not a DLC folder" if lang != "id" else "bukan folder DLC")
    sfo_path = path / "sce_sys" / "param.sfo"
    if not sfo_path.is_file():
        raise ValueError("param.sfo not found" if lang != "id" else "file param.sfo tidak ditemukan")
    values = _parse_sfo(sfo_path.read_bytes())
    content_id = values.get("CONTENT_ID", "")
    title_id = values.get("TITLE_ID", "")
    category = values.get("CATEGORY", "")
    if title_id and title_id != EXPECTED_TITLE_ID:
        raise ValueError(
            f"folder is for {title_id or 'an unknown title'}, not {EXPECTED_TITLE_ID}"
            if lang != "id" else
            f"folder untuk {title_id or 'title tidak dikenal'}, bukan {EXPECTED_TITLE_ID}"
        )
    # If it's the base game folder itself (e.g. CUSA01159 with base eboot.bin), skip if requested
    if skip_base_game and path.name == EXPECTED_TITLE_ID and (path / "eboot.bin").is_file():
        raise ValueError(
            "Base Game folder - not a DLC add-on"
            if lang != "id" else
            "Folder Game Utama (Base Game) - bukan folder DLC"
        )
    label = extract_entitlement_label(content_id, path.name)
    title = values.get("TITLE") or path.name
    return {
        "title": title,
        "content_id": content_id or f"JP0102-{EXPECTED_TITLE_ID}_00-{label}",
        "title_id": title_id or EXPECTED_TITLE_ID,
        "label": label,
        "category": category or "ac",
        "app_ver": values.get("APP_VER", "1.00"),
    }


def scan_extracted_dlc(folder, lang="en"):
    """Return sorted (path, metadata, error) records for extracted DLC folders and packages (Flexible DLC Scanner)."""
    if folder is None or not str(folder).strip():
        return []
    folder = Path(folder)
    if not folder.is_dir():
        msg = "DLC folder does not exist" if lang != "id" else "Folder DLC tidak ditemukan"
        return [(folder, None, msg)]

    records = []
    seen_paths = set()

    for root, dirs, files in os.walk(folder):
        rel_parts = Path(root).relative_to(folder).parts
        if len(rel_parts) > 5:
            dirs.clear()
            continue

        if "sce_sys" in dirs:
            cand_path = Path(root)
            real_path = cand_path.resolve()
            if real_path not in seen_paths:
                seen_paths.add(real_path)
                sfo = cand_path / "sce_sys" / "param.sfo"
                if sfo.is_file():
                    try:
                        info = read_extracted_dlc(cand_path, lang=lang)
                        records.append((cand_path, info, ""))
                    except (OSError, ValueError, struct.error) as error:
                        if "Base Game" not in str(error):
                            records.append((cand_path, None, str(error)))
            dirs.clear()
            continue

        for f in files:
            if f.lower().endswith(".pkg"):
                pkg_path = Path(root) / f
                real_pkg = pkg_path.resolve()
                if real_pkg not in seen_paths:
                    seen_paths.add(real_pkg)
                    msg = (
                        "File .PKG mentah (ekstrak dengan PS4 PKG Tool dahulu)"
                        if lang == "id" else
                        "Raw .PKG file (extract with PS4 PKG Tool first)"
                    )
                    records.append((pkg_path, None, msg))

    records.sort(key=lambda item: item[0].name.casefold())
    return records
