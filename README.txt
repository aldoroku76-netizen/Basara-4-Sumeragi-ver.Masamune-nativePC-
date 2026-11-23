Basara 4 PC - by Timotius (v1.0.9)
==================================
Sengoku Basara 4 Sumeragi (PS4, CUSA01159) running natively on Windows x64.
Free software, GNU GPL v2 or later. Credits: NOTICE.md. No game files are included.
GitHub: https://github.com/aldoroku76-netizen/Basara-4-Sumeragi-ver.Masamune-nativePC-

What's new in v1.0.9
  - Graphics fixes:
    * Fixed AMD integrated GPU screen darkening during ultimate attacks at 540p and 1080p.
    * Fixed doubled/ghosted picture during cutscenes across GPUs and iGPUs (including stages that
      enter a boss cutscene at native 1080p).
    * Fixed menu cursor glow and selection highlight alignment at 720p, 1080p, and 1440p.
    * Fixed 480p right-edge smearing by rounding internal render width to the game's 20x20 tile
      grid (860x480).
  - Crash reports & Vulkan 1.3 check:
    * Readable crash dumps are written to user\crash\ when the game crashes.
    * The launcher checks for Vulkan 1.3 support before starting and warns if your driver is too old.
    * The crash diagnostic dialog now fits on smaller screens (1366x768) with scrollable details.
  - Force Stop:
    * First click on "Stop Game" asks the game window to close cleanly so saves can finish.
    * Second click ("Force Stop") immediately terminates the process if it is frozen.
  - Tracer & Report (F11):
    * "Tracer" replaces "Audio debug log" and records both graphics and audio logs.
    * Press F11 in-game while Tracer is ticked to capture a broken frame, then click "Report (F11)"
      in the launcher to create a privacy-masked .zip report (< 9 MB) in user\reports\.
    * Keeps up to 20 report sessions automatically and cleans stale unbundled trace files on startup.
  - Unified Controller Mapping GUI:
    * "Control Gamepad" now opens a single graphical window with live stick crosshairs, step-by-step
      button binding, stick calibration, and manual presets (no command-prompt window).
    * Automatically backs up and restores your previous mapping if closed before saving.
  - High-DPI & 125%/150% Windows scaling:
    * Mouse-wheel scrolling on the left settings column keeps PLAY GAME reachable on smaller displays.
  - Upgrading from v1.0.9-beta or earlier:
    * Simply extract over your existing launcher folder. Your saves in user\savedata\ are kept.

How to play
  1. Put your own game dump (the folder that contains eboot.bin) in "game\", or press
     "Browse" in the launcher and choose it somewhere else.
  2. Open "Sengoku Basara 4.exe" and press PLAY GAME. The first start prepares the game image from
     eboot.bin (about a minute). It is redone automatically if eboot.bin changes.
  "Play Sengoku Basara 4.cmd" starts the game straight away with the last settings.

Requirements
  Windows 10 (1903+) or 11, 64-bit. A CPU with AVX. A graphics card with Vulkan 1.3 and a current
  driver.

Folder contents
  Sengoku Basara 4.exe   launcher: display, resolution, upscaling, frame rate, controller, DLC, cheats
  bin\        the runtime (basara4-core.exe), the controller mapper and their DLLs
  game\       the game dump (e.g. game\CUSA01159\eboot.bin)
  out\        the prepared game image (made automatically)
  user\       saves, shader cache, basara4.ini, last_run.log, crash\, reports\, captures\
  scripts\    the image preparation scripts
  launcher\   the launcher source

Launcher options
  Display mode      Windowed, Borderless, Exclusive
  Resolution        360p, 480p (860x480), 540p, 720p, 900p, 1080p Native, 1440p, 1800p, 4K
  Upscaling         Off, or FSR 1 (sharper)
  Frame limit       60 (default), 90, 120, 144, 165, 240, Unlimited
  VSync, sharpening (RCAS), anisotropic filtering 2x-16x
  Diagnostics       Tracer (Render + Audio + F11 capture), Audio WAV Capture, Report (F11)
  Controller        Control Gamepad (No-Console GUI), KBM Controls, Analog Mode, Reset Mapping
  Utilities         Cheats & Mods, Manage DLC, Open Log, Audio Log, Open Saves
  Credits           shows NOTICE.md

Extracted DLC
  Use "Manage DLC" to choose the parent folder containing extracted add-on folders (such as DLC\).
  The flexible scanner recursively finds every add-on containing sce_sys\param.sfo. Raw PKG files
  are not opened or decrypted.

In-game shortcuts
  Insert, or R3 + L2 on the controller: open in-game menu.
  F11 (when Tracer is ticked): capture diagnostic frame for Report (F11).
  F12: take a screenshot.

Reporting problems
  Tick "Tracer" in the launcher, start the game, press F11 if you see a visual bug, then close the
  game and click "Report (F11)". Attach the generated user\reports\basara4-report-*.zip to GitHub
  Issues: https://github.com/aldoroku76-netizen/Basara-4-Sumeragi-ver.Masamune-nativePC-/issues
