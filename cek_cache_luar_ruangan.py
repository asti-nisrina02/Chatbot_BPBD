"""
Cek spesifik: apakah pertanyaan soal gempa "di luar ruangan" ada tersimpan
di cache, dan kalau ada, isinya apa. Ini buat mastiin apakah jawaban salah
yang muncul itu dari CACHE LAMA (perlu dihapus) atau dari GENERATE BARU
(berarti prompt fix-nya belum manjur).

Jalankan: py cek_cache_luar_ruangan.py
"""
import sqlite3

DB_PATH = "cache_jawaban.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
    SELECT pertanyaan, jawaban, asal, created_at
    FROM cache_jawaban
    WHERE pertanyaan_normalized LIKE '%luar ruangan%'
""")
hasil = cur.fetchall()
conn.close()

if not hasil:
    print("❌ TIDAK ADA entry 'luar ruangan' di cache.")
    print("   Berarti jawaban yang kamu lihat itu HASIL GENERATE BARU (bukan cache lama)")
    print("   -> artinya prompt fix-nya belum manjur ke Gemma3:4b, perlu diperkuat lagi.")
else:
    print(f"✅ Ketemu {len(hasil)} entry 'luar ruangan' di cache:\n")
    for pertanyaan, jawaban, asal, created_at in hasil:
        print(f"Pertanyaan : {pertanyaan}")
        print(f"Asal       : {asal} (dibuat: {created_at})")
        print(f"Jawaban    : {jawaban[:200]}...")
        print()
    print("-> Ini CACHE LAMA yang belum dihapus. Perlu di-hapus manual biar")
    print("   digenerate ulang pakai prompt fix yang baru.")