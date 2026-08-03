"""
Hapus entry cache buat pertanyaan gempa luar/dalam ruangan, biar next time
ditanya, sistem pakai jawaban HARDCODE yang baru (bukan cache lama yang salah).

Jalankan: py hapus_cache_gempa_ruangan.py
"""
import sqlite3

DB_PATH = "cache_jawaban.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
    DELETE FROM cache_jawaban
    WHERE pertanyaan_normalized LIKE '%luar ruangan%'
       OR pertanyaan_normalized LIKE '%dalam ruangan%'
""")
dihapus = cur.rowcount
conn.commit()
conn.close()

print(f"✅ Selesai! {dihapus} entry cache (gempa luar/dalam ruangan) dihapus.")
print("   Pertanyaan ini sekarang akan pakai jawaban HARDCODE yang baru,")
print("   dan hasilnya INSTAN (gak perlu nunggu GraphRAG generate).")
