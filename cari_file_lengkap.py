"""
Scan semua file CSV yang namanya mirip 'jawaban_dataset' di folder ini,
dan cek masing-masing: berapa baris, berapa yang ERROR, biar ketauan
file mana yang paling lengkap (0 error, 99 baris) dan yang PALING BARU.

Jalankan: py cari_file_lengkap.py
"""
import csv
import glob
import os
from datetime import datetime

kandidat = glob.glob("*.csv")
kandidat = sorted(set(kandidat))

if not kandidat:
    print("Gak ketemu file CSV apapun di folder ini.")
else:
    print(f"Ketemu {len(kandidat)} file CSV, dicek satu-satu:\n")
    hasil = []
    for nama_file in kandidat:
        try:
            with open(nama_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if "question" not in (reader.fieldnames or []) or "answer" not in (reader.fieldnames or []):
                print(f"[BUKAN FORMAT JAWABAN] {nama_file}")
                continue
            total = len(rows)
            error = sum(1 for r in rows if "ERROR" in str(r.get("answer", "")))
            kosong = sum(1 for r in rows if not str(r.get("answer", "")).strip())
            ukuran_kb = os.path.getsize(nama_file) / 1024
            mtime = os.path.getmtime(nama_file)
            waktu_ubah = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            status = "LENGKAP" if (total == 99 and error == 0) else "belum lengkap"
            hasil.append((mtime, nama_file, status, total, error, kosong, ukuran_kb, waktu_ubah))
        except Exception as e:
            print(f"[GAGAL DIBACA] {nama_file} -> {e}")

    hasil.sort(key=lambda x: -x[0])
    print("Diurutkan dari yang PALING BARU diubah ke yang paling lama:\n")
    for mtime, nama_file, status, total, error, kosong, ukuran_kb, waktu_ubah in hasil:
        tanda = "OK " if status == "LENGKAP" else "!! "
        print(f"{tanda} {nama_file}")
        print(f"    -> {total} baris, {error} ERROR, {kosong} kosong, {ukuran_kb:.0f} KB, diubah terakhir: {waktu_ubah}")
        print()