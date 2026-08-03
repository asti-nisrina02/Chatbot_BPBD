"""
Hapus entry-entry TERTENTU dari cache_jawaban.db yang jawabannya masih versi
LAMA (sebelum ada fix koreksi faktual & filter kontaminasi terbaru). Setelah
dihapus, pertanyaan ini akan digenerate ULANG (lambat, sekali ini aja) pas
ditanya lagi, lalu otomatis tersimpan ke cache dengan jawaban yang BARU/benar.

Jalankan: py bersihkan_cache_lama.py
"""
import sqlite3

DB_PATH = "cache_jawaban.db"

# Pertanyaan yang perlu di-refresh -- sesuai 16 soal yang kena perbaikan
# hari ini (filter kontaminasi UU/harta + koreksi faktual gempa & pergeseran tanah)
PERTANYAAN_PERLU_REFRESH = [
    "Apa bahaya yang mengintai saat banjir?",
    "Apa yang harus dilakukan setelah gempa bumi?",
    "Bagaimana cara mempersiapkan diri sebelum gempa bumi?",
    "Apa saja yang harus ada dalam tas darurat gempa?",
    "Apakah Kabupaten Bogor rawan gempa bumi?",
    "Apa yang harus dilakukan saat gempa bumi terjadi di luar ruangan?",
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

dihapus = 0
for p in PERTANYAAN_PERLU_REFRESH:
    cur.execute("DELETE FROM cache_jawaban WHERE pertanyaan = ?", (p,))
    dihapus += cur.rowcount

conn.commit()
conn.close()

print(f"✅ Selesai! {dihapus} entry cache lama dihapus.")
print(f"   ({len(PERTANYAAN_PERLU_REFRESH)} pertanyaan ditargetkan -- kalau angkanya beda, mungkin")
print(f"   sebagian teksnya di database gak persis sama, cek manual kalau perlu)")
print("\nPertanyaan-pertanyaan ini akan digenerate ULANG (lambat, ~279 detik) pas")
print("ditanya lagi, lalu otomatis kesimpen ke cache dengan jawaban yang sudah diperbaiki.")