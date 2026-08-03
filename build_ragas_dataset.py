"""
Generate jawaban_dataset.csv BARU buat evaluasi RAGAS, pakai app.py v5.
Kolom question/answer/context diambil FRESH dari app.py yang terbaru,
kolom reference diambil dari jawaban_dataset_lama.csv (ground truth gak
berubah, cuma answer & context yang perlu di-refresh).

CARA PAKAI:
1. Pastikan app.py (v5, yang punya mode debug di /chat) LAGI JALAN.
2. Pastikan soal_99.csv dan jawaban_dataset_lama.csv ada di folder yang sama.
3. Jalankan: py build_ragas_dataset.py
4. Hasilnya tersimpan di jawaban_dataset.csv — siap dipakai evaluasi.py.

Punya fitur resume sama kayak batch_test_99.py — kalau keputus di tengah
jalan, tinggal jalanin ulang, otomatis skip yang udah selesai.
"""
import csv
import os
import time
import requests

BASE_URL = "http://127.0.0.1:5000/chat"
SOAL_CSV = "soal_99.csv"
REFERENSI_CSV = "jawaban_dataset_lama.csv"
OUTPUT_CSV = "jawaban_dataset.csv"
REQUEST_TIMEOUT = 480
JEDA_ANTAR_REQUEST = 2


def tanya_debug(pertanyaan, timeout=REQUEST_TIMEOUT):
    """Kirim ke /chat dengan debug=True biar konteks mentah ikut dikirim balik."""
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
        print(f"    gagal: {e}")
        return "[ERROR: gagal dapat respons]", ""


def muat_referensi():
    """Bikin lookup dict question -> reference dari file lama."""
    with open(REFERENSI_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {row["question"].strip(): row["reference"] for row in rows}


def sudah_dikerjakan():
    if not os.path.exists(OUTPUT_CSV):
        return set()
    with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
        return {row["question"].strip() for row in csv.DictReader(f)}


def main():
    with open(SOAL_CSV, "r", encoding="utf-8") as f:
        soal_rows = list(csv.DictReader(f))

    referensi = muat_referensi()
    print(f"Referensi (ground truth) dimuat: {len(referensi)} soal")

    total = len(soal_rows)
    selesai_sebelumnya = sudah_dikerjakan()

    fieldnames = ["question", "answer", "context", "reference"]

    if selesai_sebelumnya:
        print(f"Ketemu {len(selesai_sebelumnya)} hasil dari run sebelumnya, lanjutin...")
        mode = "a"
    else:
        print("Mulai run baru...")
        mode = "w"

    print(f"Mengirim ke {BASE_URL} (mode debug, biar konteks ikut kekirim)\n")

    with open(OUTPUT_CSV, mode, encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
            f_out.flush()

        waktu_mulai_total = time.time()

        for i, row in enumerate(soal_rows, 1):
            pertanyaan = row["Pertanyaan"].strip()

            if pertanyaan in selesai_sebelumnya:
                print(f"[{i}/{total}] SKIP (udah ada): {pertanyaan}")
                continue

            ref = referensi.get(pertanyaan, "")
            if not ref:
                print(f"[{i}/{total}] ⚠️  WARNING: gak ketemu reference buat: {pertanyaan}")

            print(f"[{i}/{total}] {pertanyaan}")
            waktu_mulai = time.time()
            jawaban, konteks = tanya_debug(pertanyaan)
            durasi = time.time() - waktu_mulai
            print(f"    -> selesai dalam {durasi:.1f}s")

            writer.writerow({
                "question": pertanyaan,
                "answer": jawaban,
                "context": konteks,
                "reference": ref,
            })
            f_out.flush()

            time.sleep(JEDA_ANTAR_REQUEST)

        durasi_total = time.time() - waktu_mulai_total

    print(f"\nSelesai dalam {durasi_total/60:.1f} menit.")
    print(f"Hasil tersimpan di: {OUTPUT_CSV}")
    print("File ini siap dipakai langsung sebagai input evaluasi.py")


if __name__ == "__main__":
    main()