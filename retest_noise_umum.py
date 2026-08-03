"""
Retest CEPAT: cuma 11 pertanyaan yang kemarin kena kontaminasi entitas UU
24/2007 / boilerplate harta-dokumentasi, buat verifikasi apakah fix
ENTITAS_NOISE_UMUM di app.py beneran jalan sekarang.

PENTING SEBELUM JALANIN:
1. STOP app.py yang lagi jalan (Ctrl+C).
2. JALANIN ULANG: py app.py -- ini WAJIB, Flask gak auto-reload kalau file
   app.py diedit sementara prosesnya masih yang lama.
3. Baru jalanin script ini: py retest_noise_umum.py

Hasilnya diprint ke layar (gak nulis csv), tinggal baca manual apakah
4 entitas noise (korban jiwa manusia, kerusakan lingkungan, kerugian
harta benda, dampak psikologis) atau boilerplate harta/foto masih muncul.
"""
import requests
import time

BASE_URL = "http://127.0.0.1:5000/chat"
REQUEST_TIMEOUT = 400

SOAL_TARGET = [
    (11, "Apa bahaya yang mengintai saat banjir?"),
    (31, "Bagaimana cara mempersiapkan diri sebelum gempa bumi?"),
    (35, "Apakah Kabupaten Bogor rawan gempa bumi?"),
    (66, "Bagaimana cara mencegah penyebaran api saat karhutla?"),
    (70, "Apa dampak karhutla bagi kesehatan masyarakat?"),
    (71, "Bagaimana cara melaporkan kebakaran hutan yang ditemukan?"),
    (72, "Apa yang harus dilakukan setelah kebakaran hutan padam?"),
    (76, "Apa dampak bencana kekeringan bagi masyarakat?"),
    (84, "Apa dampak pergeseran tanah terhadap infrastruktur?"),
    (89, "Bagaimana cara memantau pergeseran tanah di sekitar rumah?"),
    (90, "Apa yang dilakukan BPBD saat terjadi pergeseran tanah?"),
]

NOISE_KEYWORDS = [
    "korban jiwa manusia", "kerusakan lingkungan", "kerugian harta benda",
    "dampak psikologis", "harta dan kepemilikan", "harta kita",
    "catatan harta", "dokumentasikan", "mendokumentasikan",
]


def tanya(pertanyaan, timeout=REQUEST_TIMEOUT):
    try:
        resp = requests.post(BASE_URL, json={"pertanyaan": pertanyaan}, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("jawaban", "")
    except Exception as e:
        return f"[ERROR: {e}]"


def main():
    print(f"Retest {len(SOAL_TARGET)} pertanyaan yang kena noise UU/harta...\n")
    hasil_bersih = 0
    hasil_masih_noise = 0

    for no, pertanyaan in SOAL_TARGET:
        print(f"[No.{no}] {pertanyaan}")
        waktu_mulai = time.time()
        jawaban = tanya(pertanyaan)
        durasi = time.time() - waktu_mulai

        jawaban_lower = jawaban.lower()
        noise_ketemu = [kw for kw in NOISE_KEYWORDS if kw in jawaban_lower]

        if noise_ketemu:
            print(f"    ⚠️  MASIH ADA NOISE: {noise_ketemu}")
            hasil_masih_noise += 1
        else:
            print(f"    ✅ BERSIH dari noise UU/harta")
            hasil_bersih += 1

        print(f"    ({durasi:.1f}s) Jawaban: {jawaban[:200]}...")
        print()
        time.sleep(1)

    print("=" * 60)
    print(f"HASIL: {hasil_bersih}/{len(SOAL_TARGET)} bersih, {hasil_masih_noise}/{len(SOAL_TARGET)} masih ada noise")
    print("=" * 60)


if __name__ == "__main__":
    main()