"""
Diagnostik cepat: cek apakah cache_jawaban.db bisa diakses dan berisi data,
dari lokasi yang SAMA seperti tempat app.py dijalankan.

Jalankan: py diagnostik_cache.py
"""
import sqlite3
import os

DB_PATH = "cache_jawaban.db"

print(f"Folder kerja sekarang: {os.getcwd()}")
print(f"Mencari database di: {os.path.abspath(DB_PATH)}")
print(f"File ada? {os.path.exists(DB_PATH)}")

if os.path.exists(DB_PATH):
    ukuran_kb = os.path.getsize(DB_PATH) / 1024
    print(f"Ukuran file: {ukuran_kb:.1f} KB")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
try:
    cur.execute("SELECT COUNT(*) FROM cache_jawaban")
    jumlah = cur.fetchone()[0]
    print(f"\nJumlah baris di tabel cache_jawaban: {jumlah}")
    if jumlah > 0:
        cur.execute("SELECT pertanyaan FROM cache_jawaban LIMIT 3")
        print("Contoh 3 pertanyaan yang ada:")
        for row in cur.fetchall():
            print("  -", row[0])
    else:
        print("⚠️  Tabelnya ADA tapi KOSONG (0 baris) -- berarti ini database yang beda dari yang diisi init_database.py!")
except sqlite3.OperationalError as e:
    print(f"\n❌ Error: {e}")
    print("Kemungkinan tabel cache_jawaban belum pernah dibuat di file ini.")
conn.close()