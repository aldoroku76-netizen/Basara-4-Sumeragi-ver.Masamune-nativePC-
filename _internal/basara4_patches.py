"""Basara 4 PC - by Timotius.   Copyright (C) 2026 Timotius.   GPL-2.0-or-later (NOTICE.md).

Sengoku Basara 4 Sumeragi (CUSA01159) memory patches for the runtime loader.

Writes patches.bin (G3PATCH2: patch base, count, then offset/length/bytes per write), found by code
signature in the game's eboot.elf so they apply to any build with the same code.

unlimited_fps: the game's own frame limiter (a sleep followed by a spin on the TSC until one frame
period has passed) is skipped. The game measures the real time each frame took and scales its update
by it, so a higher frame rate does not make it run faster.
"""
import argparse
import struct
import sys
from pathlib import Path

EBOOT_BASE = 0x400000

# vsubss/vmulss, vucomiss, jb (sleep only when the wait is long) ... call usleep ... vucomiss, jbe (leave
# the spin loop at once when the period has passed). "??" bytes are displacements.
LIMITER = ("c5 e2 5c d0 c5 f2 59 ca c5 f8 2e 0d ?? ?? ?? ?? 72 20 c4 e1 fa 2c c1 69 f8 e8 03 00 00 "
           "81 c7 18 fc ff ff e8 ?? ?? ?? ?? c5 fa 10 5d cc c5 fa 10 43 60 c5 f8 2e d8 "
           "c5 fb 10 4d d0 0f 86 ?? ?? ?? ??")
SLEEP_JB, SPIN_JBE = 16, 59


def eboot_image(elf):
    """The PT_LOAD bytes of eboot.elf at their virtual addresses."""
    phoff, = struct.unpack_from('<Q', elf, 0x20)
    phentsize, phnum = struct.unpack_from('<HH', elf, 0x36)
    loads = []
    for i in range(phnum):
        kind, _, offset, vaddr, _, filesz, _, _ = struct.unpack_from('<IIQQQQQQ', elf, phoff + i * phentsize)
        if kind == 1:
            loads.append((vaddr, offset, filesz))
    image = bytearray(max(v + f for v, _, f in loads))
    for vaddr, offset, filesz in loads:
        image[vaddr:vaddr + filesz] = elf[offset:offset + filesz]
    return bytes(image)


def find(image, text):
    pattern = [None if b == '??' else int(b, 16) for b in text.split()]
    # longest run of fixed bytes
    best, run_start = (0, 0), None
    for i, b in enumerate(pattern + [None]):
        if b is not None and run_start is None:
            run_start = i
        if b is None and run_start is not None:
            if i - run_start > best[1] - best[0]:
                best = (run_start, i)
            run_start = None
    a, b = best
    anchor = bytes(pattern[a:b])
    found, at = [], image.find(anchor)
    while at >= 0:
        s = at - a
        if s >= 0 and s + len(pattern) <= len(image) and all(
                p is None or image[s + i] == p for i, p in enumerate(pattern)):
            found.append(s)
        at = image.find(anchor, at + 1)
    return found


def unlimited_fps(image):
    """[(image offset, bytes)] that remove the game's frame wait, or raise LookupError."""
    sites = find(image, LIMITER)
    if len(sites) != 1:
        raise LookupError('frame limiter code not found' if not sites else 'frame limiter code found twice')
    base = sites[0]
    jbe = base + SPIN_JBE
    disp, = struct.unpack_from('<i', image, jbe + 2)
    return [(base + SLEEP_JB, b'\xeb\x20'),
            (jbe, b'\xe9' + struct.pack('<i', disp + 1) + b'\x90')]


def write_patches(path, writes):
    blob = struct.pack('<8sQQ', b'G3PATCH2', EBOOT_BASE, len(writes))
    for offset, data in writes:
        blob += struct.pack('<QQ', offset, len(data)) + data
    Path(path).write_bytes(blob)


def patch_audio_runtime(core_path):
    """Patch the Ponytail / SpartanPort runtime binary to fix ATRAC9 circular ring-buffer
    streaming frame loops, dialogue voice transitions, and audio underrun popping."""
    core = Path(core_path)
    if not core.is_file():
        return False, "core binary not found"
    data = bytearray(core.read_bytes())
    changes = []

    # 1. Patch A: Safety Queue Cushion & Smooth Silence Filler (Fix Audio Clicking / Popping)
    # Location: sceAudioOutOutputs at 0x14000bd59 (file offset 0xb159)
    # Original:
    #   lea esi, [r12 + r12]          (43 8d 34 24) -> 512 samples / 10.6ms
    #   call SDL_GetAudioStreamQueued (e8 fe 91 3f 00)
    #   cmp eax, r12d                 (44 39 e0)    -> 256 samples / 5.3ms
    #   jge +0x15                     (7d 15)
    # Replacement:
    #   lea esi, [r12 + r12*4]        (43 8d 34 a4) -> 1280 samples / 26.6ms cushion threshold
    #   call SDL_GetAudioStreamQueued (e8 fe 91 3f 00)
    #   cmp eax, esi                  (39 f0)       -> compare against 1280 sample threshold
    #   nop                           (90)
    #   jge +0x15                     (7d 15)
    sig_a_orig = bytes.fromhex("438d3424e8fe913f004439e07d15")
    sig_a_patched = bytes.fromhex("438d34a4e8fe913f0039f0907d15")
    idx_a = data.find(sig_a_orig)
    if idx_a != -1:
        data[idx_a:idx_a + len(sig_a_patched)] = sig_a_patched
        changes.append("audio buffer queue cushion (1280 samples / smooth filler)")
    elif sig_a_patched in data:
        changes.append("audio buffer queue cushion already active")

    # 2. Patch B: Dialogue Voice State Transition Flush & Sync (Fix Voice Line Looping / Repeat)
    # Location: sceNgs2VoiceControl at 0x140017fab (file offset 0x173ab)
    # Original:
    #   mov dword ptr [rdi + 0x14], eax (89 47 14)
    #   jmp 0x140017c90                 (e9 dd fc ff ff)
    # Hook:
    #   jmp 0x140407796                 (e9 e6 f7 3e 00) -> jumps to code cave at 0x406b96
    #   nop; nop; nop                   (90 90 90)
    # Cave Stub (83 bytes at 0x140407796 / file 0x406b96):
    #   mov [rdi + 0x14], eax
    #   cmp eax, 2                      (PLAY state)
    #   je +70                          (jump to jmp 0x140017c90)
    #   mov [rdi + 0x1904], 0           (reset read offset in ATRAC9 buffer)
    #   mov [rdi + 0x1908], 0           (reset remaining samples in block)
    #   mov [rdi + 0x1910], 0           (reset decoded bytes)
    #   mov [rdi + 0x1918], 0           (reset pending flag)
    #   mov [rdi + 0x18fc], 0           (reset underrun count)
    #   mov [rdi + 0x1c0c], 0           (reset waveform block index)
    #   mov [rdi + 0x1c10], 0           (reset loop iteration)
    #   jmp 0x140017c90
    sig_b_orig = bytes.fromhex("894714e9ddfcffff")
    sig_b_hook = bytes.fromhex("e9e6f73e00909090")
    cave_off = 0x406b96
    cave_va = 0x140407796
    target_ret_va = 0x140017c90
    stub_disp = target_ret_va - (cave_va + 78 + 5)
    stub_b = (
        bytes.fromhex("894714") +
        bytes.fromhex("83f802") +
        bytes.fromhex("7446") +
        bytes.fromhex("c7870419000000000000") +
        bytes.fromhex("c7870819000000000000") +
        bytes.fromhex("c7871019000000000000") +
        bytes.fromhex("c7871819000000000000") +
        bytes.fromhex("c787fc18000000000000") +
        bytes.fromhex("c7870c1c000000000000") +
        bytes.fromhex("c787101c000000000000") +
        b"\xe9" + struct.pack("<i", stub_disp)
    )

    idx_b = data.find(sig_b_orig)
    if idx_b != -1:
        data[idx_b:idx_b + len(sig_b_hook)] = sig_b_hook
        data[cave_off:cave_off + len(stub_b)] = stub_b
        changes.append("dialogue voice transition queue flush & sync")
    elif sig_b_hook in data and stub_b in data:
        changes.append("dialogue voice flush already active")

    # 3. Patch C: ATRAC9 Streaming Ring-Buffer Loop Bypass (Existing)
    orig_pattern = bytes.fromhex(
        "c7860419000000000000"
        "c7861019000000000000"
        "c7861819000000000000"
        "c786fc18000000000000"
        "eb7e"
    )
    replacement = b"\xe9\xa3\x00\x00\x00" + b"\x90" * 37
    idx_c = data.find(orig_pattern)
    if idx_c != -1:
        data[idx_c:idx_c + len(replacement)] = replacement
        changes.append("ATRAC9 streaming ring-buffer loop bypass")
    elif b"\xe9\xa3\x00\x00\x00" + b"\x90" * 10 in data:
        changes.append("ATRAC9 ring-buffer loop bypass already active")

    if changes:
        core.write_bytes(data)
        return True, "; ".join(changes)
    return False, "no patch targets found"


def build(elf_path, out_path, unlimited, core_path=None):
    writes = []
    notes = []
    image = eboot_image(Path(elf_path).read_bytes())
    if unlimited:
        try:
            writes += unlimited_fps(image)
            notes.append('unlimited fps')
        except LookupError as error:
            notes.append(f'unlimited fps skipped: {error}')
    if core_path:
        ok, msg = patch_audio_runtime(core_path)
        if ok:
            notes.append(f'audio: {msg}')
    write_patches(out_path, writes)
    return writes, notes


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('elf')
    ap.add_argument('out')
    ap.add_argument('--unlimited-fps', action='store_true')
    a = ap.parse_args()
    writes, notes = build(a.elf, a.out, a.unlimited_fps)
    for offset, data in writes:
        print(f'  {offset + EBOOT_BASE:#x}: {data.hex()}')
    print('Patches:', ', '.join(notes) or 'none', f'({len(writes)} writes)')
