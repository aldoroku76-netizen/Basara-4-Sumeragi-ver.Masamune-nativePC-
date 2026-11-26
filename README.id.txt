Basara 4 PC - oleh Timotius (v1.0.9)
====================================
Copyright (c) 2026 Timotius
Sengoku Basara 4 Sumeragi (PS4, CUSA01159) berjalan secara native di Windows x64.
Perangkat lunak bebas, GNU GPL v2 atau versi lebih baru. Kredit: NOTICE.md. Tidak termasuk file game.
GitHub: https://github.com/aldoroku76-netizen/Basara-4-Sumeragi-ver.Masamune-nativePC-

Pembaruan di v1.0.9
  - Perbaikan Grafis:
    * Memperbaiki layar menjadi gelap saat serangan Basara/Ultimate pada iGPU AMD di resolusi 540p & 1080p.
    * Memperbaiki tampilan gambar ganda (doubled picture) saat cutscene pada berbagai GPU/iGPU,
      termasuk stage boss yang masuk ke cutscene pada resolusi native 1080p.
    * Memperbaiki posisi glow kursor dan highlight menu utama/jeda pada resolusi 720p, 1080p, dan 1440p.
    * Memperbaiki artefak/smear di tepi kanan pada resolusi 480p dengan menyelaraskan lebar render
      ke grid tile 20x20 game (860x480).
  - Laporan Crash & Pemeriksaan Vulkan 1.3:
    * Crash dump yang mudah dibaca kini disimpan otomatis ke folder user\crash\.
    * Launcher memeriksa dukungan driver Vulkan 1.3 sebelum game dimulai dan menampilkan jendela
      peringatan bertema dark-navy & merah samurai dengan daftar GPU, versi Vulkan, serta tautan
      driver resmi NVIDIA/AMD/Intel (tetap memberi opsi untuk melanjutkan).
    * Jendela diagnostik crash kini pas di layar kecil (1366x768) dengan panel rincian yang dapat di-scroll.
  - Hentikan Paksa (Force Stop Dua Tahap):
    * Klik pertama pada "Hentikan Game" meminta jendela game menutup secara normal agar save data aman.
    * Klik kedua ("Paksa Berhenti") langsung menghentikan proses game jika macet/not responding.
  - Tracer & Laporan (F11):
    * Opsi "Tracer" menggantikan "Log Debug Audio" dan merekam log grafis sekaligus audio.
    * Tekan F11 di dalam game saat Tracer aktif untuk menangkap frame yang bermasalah, lalu klik
      "Laporan (F11)" di launcher untuk membuat paket .zip (< 9 MB) di user\reports\ dengan nama
      pengguna Windows yang sudah disamarkan secara otomatis.
    * Menyimpan maksimal 20 sesi laporan terakhir dan membersihkan file trace lama saat launcher dibuka.
  - GUI Pemetaan Kontroler Terpadu (Tanpa Jendela CMD):
    * Tombol "Atur Gamepad" kini membuka jendela grafis langsung di launcher dengan visualisasi analog
      real-time, wizard tombol langkah-demi-langkah, kalibrasi stik, dan preset manual.
    * Otomatis mencadangkan dan memulihkan mapping sebelumnya jika jendela ditutup sebelum disimpan.
  - Dukungan High-DPI (Scaling Windows 125% / 150%):
    * Kolom pengaturan kiri dapat di-scroll dengan roda mouse pada layar laptop sehingga tombol
      MAINKAN GAME selalu terjangkau.
  -Catatan Upgrade dari v1.0.9-beta atau versi lama:
    * Cukup ekstrak ke folder launcher Anda. Save data di user\savedata\ tetap aman.

Cara Bermain
  1. Letakkan hasil dump game Anda (folder yang berisi eboot.bin, misalnya CUSA01159) di dalam folder
     "game\", atau klik "Pilih Folder..." di launcher.
  2. Buka "Sengoku Basara 4.exe" lalu tekan MAINKAN GAME. Saat pertama kali dijalankan, launcher akan
     menyiapkan image game dari eboot.bin (sekitar 1 menit).
  "Play Sengoku Basara 4.cmd" langsung menjalankan game dengan pengaturan terakhir.

Spesifikasi Minimum
  Windows 10 (1903+) atau Windows 11 64-bit, prosesor dengan dukungan AVX, serta kartu grafis (GPU)
  dengan dukungan Vulkan 1.3 dan driver terbaru.

Isi Folder
  Sengoku Basara 4.exe   launcher: tampilan, resolusi, upscaling, batas FPS, kontroler, DLC, cheat
  bin\        runtime utama (basara4-core.exe), mapper kontroler, dan file DLL
  game\       folder dump game (contoh: game\CUSA01159\eboot.bin)
  out\        image game yang telah disiapkan (dibuat otomatis)
  user\       save data, shader cache, basara4.ini, last_run.log, crash\, reports\, captures\
  scripts\    skrip persiapan image game
  launcher\   kode sumber launcher

Pintasan di Dalam Game (In-Game)
  Insert, atau R3 + L2 pada stik: membuka menu overlay di dalam game.
  F11 (saat Tracer dicentang): menangkap frame diagnostik untuk Laporan (F11).
  F12: mengambil tangkapan layar (screenshot).

Melaporkan Masalah (Bug Report)
  Centang "Tracer" di launcher, jalankan game, tekan F11 saat bug visual muncul, lalu tutup game
  dan klik "Laporan (F11)". Lampirkan file user\reports\basara4-report-*.zip ke GitHub Issues:
  https://github.com/aldoroku76-netizen/Basara-4-Sumeragi-ver.Masamune-nativePC-/issues
