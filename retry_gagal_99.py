"""
Retry HANYA pertanyaan yang gagal (ERROR) di hasil_test_99.csv, tanpa
mengulang dari awal. Update baris yang berhasil di-retry, baris yang udah
sukses sebelumnya TIDAK disentuh.

CARA PAKAI:
1. RESTART app.py dulu (stop, jalanin ulang) — biar Ollama/Flask fresh,
   gak numpuk beban dari run 7 jam sebelumnya.
2. Pastikan hasil_test_99.csv ada di folder yang sama dengan script ini.
3. Jalankan: py retry_gagal_99.py
4. Hasilnya langsung nge-update hasil_test_99.csv di tempat yang sama
   (baris yang berhasil di-retry akan ke-replace, baris lain gak berubah).
"""
import csv
import time
import requests

BASE_URL = "http://127.0.0.1:5000/chat"
CSV_FILE = "hasil_test_99.csv"
REQUEST_TIMEOUT = 480  # 8 menit — lebih longgar lagi buat jaga-jaga
JEDA_ANTAR_REQUEST = 2


def tanya(pertanyaan, timeout=REQUEST_TIMEOUT):
    try:
        resp = requests.post(BASE_URL, json={"pertanyaan": pertanyaan}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("jawaban", ""), data.get("sumber", "")
    except Exception as e:
        print(f"    gagal lagi: {e}")
        return "[ERROR: gagal dapat respons setelah retry]", ""


def main():
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        fieldnames = csv.DictReader(f).fieldnames
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    gagal = [r for r in rows if "ERROR" in r["Jawaban Chatbot (Baru)"]]
    print(f"Ketemu {len(gagal)} pertanyaan yang gagal, akan di-retry...\n")

    for idx, row in enumerate(rows, 1):
        if "ERROR" not in row["Jawaban Chatbot (Baru)"]:
            continue

        print(f"[Retry {gagal.index(row)+1}/{len(gagal)}] No.{row['No']}: {row['Pertanyaan']}")
        waktu_mulai = time.time()
        jawaban, sumber = tanya(row["Pertanyaan"])
        durasi = time.time() - waktu_mulai
        print(f"    -> selesai dalam {durasi:.1f}s | sumber: {sumber}")

        row["Jawaban Chatbot (Baru)"] = jawaban
        row["Sumber"] = sumber

        # Simpan ulang SELURUH file tiap kali 1 retry selesai, biar progress
        # gak hilang kalau keputus di tengah retry.
        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        time.sleep(JEDA_ANTAR_REQUEST)

    masih_gagal = [r for r in rows if "ERROR" in r["Jawaban Chatbot (Baru)"]]
    print(f"\nSelesai retry. Masih gagal: {len(masih_gagal)}")
    if masih_gagal:
        print("Nomor yang masih gagal:", [r["No"] for r in masih_gagal])
    print(f"Hasil sudah ter-update di: {CSV_FILE}")


if __name__ == "__main__":
    main()