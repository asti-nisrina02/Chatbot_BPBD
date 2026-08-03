"""
Batch-test 99 pertanyaan ke chatbot BOGORSiaga yang jalan lokal.

CARA PAKAI:
1. Pastikan app.py (versi v4, dengan fitur fase) LAGI JALAN di terminal lain
   (biasanya di http://127.0.0.1:5000)
2. Pastikan soal_99.csv ada di folder yang sama dengan script ini
3. Jalankan: py batch_test_99.py
4. Tunggu sampai selesai (99 pertanyaan x waktu respons LLM lokal,
   perkiraan bisa 10-30 menit tergantung kecepatan Ollama di komputer kamu)
5. Hasilnya akan tersimpan di hasil_test_99.csv — bisa dibuka di Excel,
   tinggal isi kolom "Sesuai?" dan "Catatan/Koreksi" secara manual sambil
   baca "Jawaban Chatbot (Baru)"

Kalau URL Flask kamu beda (bukan localhost:5000), ubah BASE_URL di bawah.
"""
import csv
import os
import time
import requests

BASE_URL = "http://127.0.0.1:5000/chat"
INPUT_CSV = "soal_99.csv"
OUTPUT_CSV = "hasil_test_99.csv"
JEDA_ANTAR_REQUEST = 1   # detik, biar gak membanjiri Ollama/Neo4j sekaligus
REQUEST_TIMEOUT = 300    # detik (5 menit) — konteks sekarang lebih besar
                         # (retrieval berbasis dokumen bisa narik puluhan
                         # entitas sekaligus), jadi gemma3:4b butuh waktu
                         # lebih lama dibanding versi lama.


def tanya(pertanyaan, timeout=REQUEST_TIMEOUT, max_retry=1):
    """Kirim satu pertanyaan ke endpoint /chat, dengan retry kalau gagal.
    max_retry=1 (gak ada retry) karena kalau timeout itu biasanya emang
    LLM-nya lelet, bukan error sesaat — retry cuma bikin nunggu 2x lipat."""
    for percobaan in range(1, max_retry + 1):
        try:
            resp = requests.post(
                BASE_URL,
                json={"pertanyaan": pertanyaan},
                timeout=timeout
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("jawaban", ""), data.get("sumber", "")
        except Exception as e:
            print(f"    [percobaan {percobaan}/{max_retry}] gagal: {e}")
            if percobaan < max_retry:
                time.sleep(3)
    return "[ERROR: gagal dapat respons setelah retry]", ""


def sudah_dikerjakan():
    """Cek No berapa aja yang udah ada di OUTPUT_CSV dari run sebelumnya
    (buat resume kalau proses sempat keputus di tengah jalan)."""
    if not os.path.exists(OUTPUT_CSV):
        return set()
    with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
        return {row["No"] for row in csv.DictReader(f)}


def main():
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    total = len(reader)
    selesai_sebelumnya = sudah_dikerjakan()

    fieldnames = ["No", "Jenis Bencana", "Pertanyaan", "Jawaban Chatbot (Baru)",
                  "Sumber", "Sesuai?", "Catatan/Koreksi"]

    if selesai_sebelumnya:
        print(f"Ketemu {len(selesai_sebelumnya)} hasil dari run sebelumnya di {OUTPUT_CSV}, lanjutin dari situ...")
        mode = "a"  # append, gak nulis ulang dari awal
    else:
        print(f"Mulai run baru...")
        mode = "w"

    print(f"Memuat {total} pertanyaan dari {INPUT_CSV}...")
    print(f"Mengirim ke {BASE_URL}\n")

    # Tulis hasil SEGERA setelah tiap pertanyaan selesai (bukan nunggu semua
    # 99 kelar) — penting buat run semalaman yang lama (~7 jam), biar kalau
    # laptop mati/error di tengah jalan, hasil yang udah kepakai TETAP
    # tersimpan sampai pertanyaan terakhir yang sempat diproses.
    with open(OUTPUT_CSV, mode, encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
            f_out.flush()

        waktu_mulai_total = time.time()

        for i, row in enumerate(reader, 1):
            no = row["No"]
            jenis = row["Jenis Bencana"]
            pertanyaan = row["Pertanyaan"]

            if no in selesai_sebelumnya:
                print(f"[{i}/{total}] No.{no} — SKIP (udah ada dari run sebelumnya)")
                continue

            print(f"[{i}/{total}] No.{no} ({jenis}): {pertanyaan}")
            waktu_mulai = time.time()
            jawaban, sumber = tanya(pertanyaan)
            durasi = time.time() - waktu_mulai
            print(f"    -> selesai dalam {durasi:.1f}s | sumber: {sumber}")

            writer.writerow({
                "No": no,
                "Jenis Bencana": jenis,
                "Pertanyaan": pertanyaan,
                "Jawaban Chatbot (Baru)": jawaban,
                "Sumber": sumber,
                "Sesuai?": "",
                "Catatan/Koreksi": "",
            })
            f_out.flush()  # paksa tersimpan ke disk sekarang juga

            time.sleep(JEDA_ANTAR_REQUEST)

        durasi_total = time.time() - waktu_mulai_total

    print(f"\nSelesai dalam {durasi_total/60:.1f} menit.")
    print(f"Hasil tersimpan di: {OUTPUT_CSV}")
    print("Buka file itu di Excel buat review manual (isi kolom Sesuai? & Catatan/Koreksi).")


if __name__ == "__main__":
    main()