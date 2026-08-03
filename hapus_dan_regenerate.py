"""
Gabungan: hapus entry cache buat pertanyaan tertentu, LALU langsung
regenerate via /chat (yang otomatis bakal ke-generate ulang lewat GraphRAG
karena cache-nya baru aja dihapus), dan update jawaban_dataset.csv.

Ini menghindari masalah berulang: regenerate gak ngefek kalau cache-nya
belum dihapus duluan. Versi ini TAHAN TIMEOUT -- kalau 1 pertanyaan gagal
(timeout/error), script lanjut ke pertanyaan berikutnya, dan progress
disimpan tiap kali ada yang BERHASIL (bukan nunggu semua selesai).

Jalankan: py hapus_dan_regenerate.py
Kalau ada yang gagal di akhir, tinggal jalankan lagi -- yang sudah
berhasil gak akan diulang (cache-nya udah keisi jawaban baru).
"""
import sqlite3
import requests
import pandas as pd
import time

DB_PATH = "cache_jawaban.db"
BASE_URL = "http://127.0.0.1:5000/chat"
CSV_PATH = "jawaban_dataset.csv"
REQUEST_TIMEOUT = 600  # dinaikkan dari 400 -- beberapa pertanyaan (yang narik
# konteks dari 2 dokumen sekaligus, misal gempa + nomor_darurat) butuh waktu
# lebih lama dan konsisten mepet/lewat batas 400 detik

# Daftar pertanyaan yang mau di-refresh total (hapus cache + generate ulang)
# -- tinggal yang masih gagal aja di percobaan terakhir, yang lain udah berhasil
PERTANYAAN_REFRESH = [
    "Apa saja yang harus ada dalam tas darurat gempa?",
    "Apakah Kabupaten Bogor rawan gempa bumi?",
    "Apa dampak pergeseran tanah terhadap infrastruktur?",
]


def hapus_dari_cache(pertanyaan):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM cache_jawaban WHERE pertanyaan = ?", (pertanyaan,))
    jumlah = cur.rowcount
    conn.commit()
    conn.close()
    return jumlah


def tanya(pertanyaan, timeout=REQUEST_TIMEOUT):
    resp = requests.post(BASE_URL, json={"pertanyaan": pertanyaan, "debug": True}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jawaban", ""), data.get("konteks", "")


def main():
    df = pd.read_csv(CSV_PATH)
    df["question"] = df["question"].astype(str).str.strip()

    berhasil = []
    gagal = []

    for p in PERTANYAAN_REFRESH:
        print(f"=== {p} ===")
        dihapus = hapus_dari_cache(p)
        print(f"  Cache dihapus: {dihapus} entry")

        idx = df.index[df["question"] == p.strip()]
        if len(idx) == 0:
            print(f"  ⚠️  Pertanyaan gak ketemu di CSV, dilewati.")
            gagal.append(p)
            continue

        try:
            t0 = time.time()
            jawaban, konteks = tanya(p)
            durasi = time.time() - t0
            df.loc[idx, "answer"] = jawaban
            df.loc[idx, "context"] = konteks
            df.to_csv(CSV_PATH, index=False)  # simpan LANGSUNG tiap berhasil, jangan nunggu semua
            print(f"  ✅ Selesai dalam {durasi:.1f}s, langsung disimpan ke CSV")
            print(f"  Jawaban baru: {jawaban[:150]}...")
            berhasil.append(p)
        except requests.exceptions.RequestException as e:
            print(f"  ❌ GAGAL (timeout/error): {e}")
            print(f"  -> Dilewati, lanjut ke pertanyaan berikutnya. Coba jalankan ulang script ini nanti buat retry.")
            gagal.append(p)

        print()
        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"Selesai! Berhasil: {len(berhasil)}/{len(PERTANYAAN_REFRESH)}")
    if gagal:
        print(f"Masih gagal ({len(gagal)}): jalankan ulang 'py hapus_dan_regenerate.py' buat retry otomatis:")
        for p in gagal:
            print(f"  - {p}")
    else:
        print("Semua berhasil! jawaban_dataset.csv sudah lengkap ter-update.")


if __name__ == "__main__":
    main()