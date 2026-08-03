"""
Regenerate jawaban untuk pertanyaan TERTENTU di jawaban_dataset.csv, lewat
endpoint /chat yang sama seperti chat interface (jadi hasilnya PASTI sama
kayak yang kamu tes manual). Beda dari retry_gagal_ragas.py yang cuma
ngerjain baris ber-status ERROR -- ini bisa dipaksa update baris manapun
walau isinya "sukses" tapi ternyata salah/perlu di-refresh.

Jalankan: py regenerate_baris_tertentu.py
"""
import requests
import pandas as pd
import time

BASE_URL = "http://127.0.0.1:5000/chat"
CSV_PATH = "jawaban_dataset.csv"
REQUEST_TIMEOUT = 400

# Daftar pertanyaan yang MAU dipaksa regenerate ulang (isi manual di sini)
PERTANYAAN_REGENERATE = [
    "Apa bahaya yang mengintai saat banjir?",
    "Apa saja yang harus ada dalam tas darurat gempa?",
    "Apakah Kabupaten Bogor rawan gempa bumi?",
    "Apa perlengkapan yang dibutuhkan saat terjadi karhutla?",
    "Apa dampak bencana kekeringan bagi masyarakat?",
    "Apa dampak pergeseran tanah terhadap infrastruktur?",
]


def tanya(pertanyaan, timeout=REQUEST_TIMEOUT):
    resp = requests.post(BASE_URL, json={"pertanyaan": pertanyaan, "debug": True}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jawaban", ""), data.get("konteks", "")


def main():
    df = pd.read_csv(CSV_PATH)
    df["question"] = df["question"].astype(str).str.strip()

    for p in PERTANYAAN_REGENERATE:
        idx = df.index[df["question"] == p.strip()]
        if len(idx) == 0:
            print(f"⚠️  Pertanyaan gak ketemu di CSV: {p}")
            continue
        print(f"Regenerate: {p}")
        t0 = time.time()
        jawaban, konteks = tanya(p)
        durasi = time.time() - t0
        df.loc[idx, "answer"] = jawaban
        df.loc[idx, "context"] = konteks
        print(f"  -> selesai dalam {durasi:.1f}s")
        print(f"  -> jawaban baru: {jawaban[:150]}...")
        time.sleep(1)

    df.to_csv(CSV_PATH, index=False)
    print(f"\n✅ Selesai! {CSV_PATH} sudah diupdate.")


if __name__ == "__main__":
    main()