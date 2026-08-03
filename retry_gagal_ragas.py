"""
Retry HANYA pertanyaan yang gagal (ERROR) di jawaban_dataset.csv, update
di tempat tanpa mengulang dari awal.

CARA PAKAI:
1. RESTART app.py dulu (fresh Ollama, gak numpuk beban).
2. Pastikan jawaban_dataset.csv ada di folder yang sama dengan script ini.
3. Jalankan: py retry_gagal_ragas.py
4. Hasilnya langsung nge-update jawaban_dataset.csv di tempat yang sama.
"""
import csv
import time
import requests

BASE_URL = "http://127.0.0.1:5000/chat"
CSV_FILE = "jawaban_dataset.csv"
REQUEST_TIMEOUT = 600  # 10 menit, lebih longgar lagi
JEDA_ANTAR_REQUEST = 2


def tanya_debug(pertanyaan, timeout=REQUEST_TIMEOUT):
    try:
        resp = requests.post(
            BASE_URL,
            json={"pertanyaan": pertanyaan, "debug": True},
            timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("jawaban", ""), data.get("konteks", "")
    except Exception as e:
        print(f"    gagal lagi: {e}")
        return "[ERROR: gagal dapat respons setelah retry]", ""


def main():
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        fieldnames = csv.DictReader(f).fieldnames
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    gagal = [r for r in rows if "ERROR" in str(r["answer"])]
    print(f"Ketemu {len(gagal)} pertanyaan yang gagal, akan di-retry...\n")

    for row in rows:
        if "ERROR" not in str(row["answer"]):
            continue

        idx_gagal = gagal.index(row) + 1
        print(f"[Retry {idx_gagal}/{len(gagal)}] {row['question']}")
        waktu_mulai = time.time()
        jawaban, konteks = tanya_debug(row["question"])
        durasi = time.time() - waktu_mulai
        print(f"    -> selesai dalam {durasi:.1f}s")

        row["answer"] = jawaban
        row["context"] = konteks

        # Simpan ulang SELURUH file tiap kali 1 retry selesai
        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        time.sleep(JEDA_ANTAR_REQUEST)

    masih_gagal = [r for r in rows if "ERROR" in str(r["answer"])]
    print(f"\nSelesai retry. Masih gagal: {len(masih_gagal)}")
    if masih_gagal:
        print("Pertanyaan yang masih gagal:")
        for r in masih_gagal:
            print(" -", r["question"])
    print(f"jawaban_dataset.csv sudah ter-update.")


if __name__ == "__main__":
    main()