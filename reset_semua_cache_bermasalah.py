"""
Gabungan pembersih cache -- hapus SEMUA entry yang perlu digenerate ulang
pakai fix-fix terbaru (filter kontaminasi UU/harta + koreksi gempa
luar/dalam ruangan). Jalankan ini SEKALI sebelum build_ragas_dataset.py,
biar hasil generate ulang beneran pakai versi app.py yang paling baru,
bukan jawaban lama yang masih nyangkut di cache.

Jalankan: py reset_semua_cache_bermasalah.py
"""
import sqlite3

DB_PATH = "cache_jawaban.db"

# Kelompok 1: kena kontaminasi UU 24/2007 / boilerplate harta-dokumentasi
PERTANYAAN_KONTAMINASI = [
    "Apa bahaya yang mengintai saat banjir?",
    "Apa yang harus dilakukan setelah gempa bumi?",
    "Bagaimana cara mempersiapkan diri sebelum gempa bumi?",
    "Apa saja yang harus ada dalam tas darurat gempa?",
    "Apakah Kabupaten Bogor rawan gempa bumi?",
    "Apa yang harus dilakukan setelah gempa bumi berhenti?",
    "Apa perlengkapan yang dibutuhkan saat terjadi karhutla?",
    "Bagaimana cara melaporkan kebakaran hutan yang ditemukan?",
    "Apa yang harus dilakukan setelah kebakaran hutan padam?",
    "Apa dampak bencana kekeringan bagi masyarakat?",
    "Apa dampak pergeseran tanah terhadap infrastruktur?",
    "Apa yang dilakukan BPBD saat terjadi pergeseran tanah?",
    "Apa yang harus dilakukan saat terjadi pergeseran tanah?",
    "Apa itu pergeseran tanah?",
    "Apakah pergeseran tanah bisa berkembang menjadi longsor?",
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

total_dihapus = 0

for p in PERTANYAAN_KONTAMINASI:
    cur.execute("DELETE FROM cache_jawaban WHERE pertanyaan = ?", (p,))
    total_dihapus += cur.rowcount

# Kelompok 2: gempa luar/dalam ruangan (pakai LIKE biar nangkep variasi kalimat)
cur.execute("""
    DELETE FROM cache_jawaban
    WHERE pertanyaan_normalized LIKE '%luar ruangan%'
       OR pertanyaan_normalized LIKE '%dalam ruangan%'
""")
total_dihapus += cur.rowcount

conn.commit()
conn.close()

print(f"✅ Selesai! Total {total_dihapus} entry cache bermasalah sudah dihapus.")
print("\nLangkah selanjutnya:")
print("  1. Restart app.py (kalau belum)")
print("  2. Jalankan: py build_ragas_dataset.py")
print("     -> ini akan generate ULANG pertanyaan-pertanyaan yang barusan dihapus")
print("        (butuh waktu lebih lama buat yang ini, ~5 menit per soal, sisanya")
print("        yang sudah benar tetap instan dari cache)")