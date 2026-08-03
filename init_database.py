"""
Inisialisasi database cache_jawaban.db dari jawaban_dataset.csv (99 pasangan
tanya-jawab final yang udah dites dan divalidasi).

Database ini yang bikin chatbot bisa jawab dalam hitungan MILIDETIK buat
pertanyaan yang udah pernah/mirip ditanyakan, alih-alih nunggu ~279 detik
proses generate ulang lewat Gemma3:4b tiap kali.

CARA PAKAI (jalankan SEKALI SAJA sebelum start app.py):
    py init_database.py

Kalau mau reset database dari nol (misal abis update jawaban_dataset.csv),
hapus dulu file cache_jawaban.db yang lama, baru jalanin ulang script ini.
"""
import sqlite3
import csv
import re
import os

DB_PATH = "cache_jawaban.db"
CSV_PATH = "jawaban_dataset.csv"
SOAL_CSV_PATH = "soal_99.csv"  # buat ambil info "Jenis Bencana" -> nama PDF sumber

# Peta Jenis Bencana (dari soal_99.csv) -> nama file PDF sumber
JENIS_KE_SUMBER = {
    "Banjir": "Banjir.pdf",
    "Tanah Longsor": "Tanah_Longsor.pdf",
    "Gempa Bumi": "Gempa_Bumi.pdf",
    "Angin Kencang": "Angin_Kencang.pdf",
    "Erupsi Gunung Api": "Erupsi_Gunung_Api.pdf",
    "Karhutla": "Karhutla.pdf",
    "Kekeringan": "Kekeringan.pdf",
    "Pergeseran Tanah": "Pergeseran_Tanah.pdf",
    "Umum/BPBD": "bencana.pdf, kesiapsiagaan.pdf",
}


def normalisasi(teks: str) -> str:
    """Samakan format teks biar perbandingan gak kepeleset gara-gara
    kapitalisasi/spasi/tanda baca (misal 'Apa itu Banjir?' vs 'apa itu banjir')."""
    teks = teks.lower().strip()
    teks = re.sub(r'[^\w\s]', '', teks)  # buang tanda baca
    teks = re.sub(r'\s+', ' ', teks)     # rapikan spasi ganda
    return teks


def muat_peta_sumber():
    """Baca soal_99.csv (kalau ada) buat dapetin peta pertanyaan -> nama file sumber."""
    peta = {}
    if not os.path.exists(SOAL_CSV_PATH):
        print(f"⚠️  {SOAL_CSV_PATH} tidak ditemukan -- kolom sumber akan dikosongkan.")
        return peta
    with open(SOAL_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pertanyaan = row.get("Pertanyaan", "").strip()
            jenis = row.get("Jenis Bencana", "").strip()
            if pertanyaan and jenis:
                peta[normalisasi(pertanyaan)] = JENIS_KE_SUMBER.get(jenis, "")
    return peta


def main():
    if not os.path.exists(CSV_PATH):
        print(f"❌ File {CSV_PATH} tidak ditemukan. Pastikan file ini ada di folder yang sama.")
        return

    if os.path.exists(DB_PATH):
        print(f"⚠️  Database {DB_PATH} sudah ada. Hapus dulu file ini kalau mau reset dari nol.")
        respon = input("Lanjutkan dan TAMBAHKAN data baru ke database yang ada? (y/n): ")
        if respon.lower() != 'y':
            print("Dibatalkan.")
            return

    peta_sumber = muat_peta_sumber()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cache_jawaban (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pertanyaan TEXT NOT NULL,
            pertanyaan_normalized TEXT NOT NULL,
            jawaban TEXT NOT NULL,
            sumber TEXT,
            konteks TEXT,
            asal TEXT DEFAULT 'dataset_awal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pertanyaan_normalized
        ON cache_jawaban(pertanyaan_normalized)
    """)

    jumlah = 0
    jumlah_ada_sumber = 0
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pertanyaan = row.get("question", "").strip()
            jawaban = row.get("answer", "").strip()
            konteks = row.get("context", "").strip()
            if not pertanyaan or not jawaban or "ERROR" in jawaban:
                continue
            sumber = peta_sumber.get(normalisasi(pertanyaan), "")
            if sumber:
                jumlah_ada_sumber += 1
            cur.execute("""
                INSERT INTO cache_jawaban (pertanyaan, pertanyaan_normalized, jawaban, sumber, konteks, asal)
                VALUES (?, ?, ?, ?, ?, 'dataset_awal')
            """, (pertanyaan, normalisasi(pertanyaan), jawaban, sumber, konteks))
            jumlah += 1

    conn.commit()
    conn.close()
    print(f"✅ Selesai! {jumlah} pasangan tanya-jawab dimasukkan ke {DB_PATH}")
    print(f"   ({jumlah_ada_sumber} di antaranya berhasil dapat info sumber PDF)")


if __name__ == "__main__":
    main()