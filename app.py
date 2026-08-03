from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_ollama import OllamaLLM
import os
import re
import sqlite3
import difflib

# ─── VERSI: v5 (29 Jul 2026) ────────────────────────────────────────────────
# Fitur di versi ini: kontak darurat hardcode, deteksi tipe definisi/lokasi/
# dampak/prosedural, retrieval berbasis dokumen (bukan cuma nama entitas),
# instruksi dampak diperketat (larang "efek negatif lainnya"), DAN filter
# konteks berdasar properti e.fase eksplisit dari graph.
# ⚠️ Fitur e.fase BARU JALAN kalau KG sudah di-re-ingest pakai ingest_data.py
#    & ingest_tambahan.py versi terbaru (yang juga generate field "fase").
# ────────────────────────────────────────────────────────────────────────────

load_dotenv()

app = Flask(__name__)

graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD"),
    database=os.getenv("NEO4J_DATABASE")
)
llm = OllamaLLM(model="gemma3:4b")

# ─── Kontak darurat (hardcode) ─────────────────────────────────────────────────
# Data safety-critical: nomor telepon TIDAK boleh diambil dari graph/LLM,
# karena tabel di nomor_darurat.pdf berantakan saat diekstrak PyMuPDF
# (kolom nomor urut, nama institusi, dan nomor telepon kepisah dan gampang
# ke-pasangkan salah). Daftar ini sudah diverifikasi manual oleh Tia,
# jadi dijadikan sumber tunggal yang pasti benar, bypass total dari graph.
KONTAK_DARURAT = [
    ("Call Center BPBD Kab. Bogor", "0812-1010-9002"),
    ("Pusdatin BPBD Kab. Bogor",    "0851-7530-9567"),
    ("Bogor Siaga",                 "112"),
    ("Damkar Kab. Bogor",           "021-8753547"),
    ("Pusdalops BNPB",              "0812-1237575"),
    ("Palang Merah Indonesia",      "021-4207051"),
    ("BMKG",                        "021-6546318"),
    ("PVMBG",                       "022-7272606"),
    ("Kementerian Sosial",          "0821-11300911"),
    ("Polisi",                      "110"),
    ("Pemadam Kebakaran",           "113"),
    ("SAR / Basarnas",              "115"),
    ("Ambulans",                    "118 / 119"),
    ("PLN",                         "123"),
    ("Penerangan",                  "108"),
]

FRASA_KONTAK_DARURAT = [
    'nomor darurat', 'kontak darurat', 'nomor telepon darurat',
    'nomor yang harus dihubungi', 'nomor yang bisa dihubungi',
    'hotline', 'call center', 'nomor yang dihubungi',
]

# Jawaban hardcode buat gempa bumi di luar/dalam ruangan. Ini KHUSUS karena
# terbukti berulang kali salah walau udah dikasih instruksi prompt DAN
# filter konteks -- kemungkinan besar "berlindung di bawah meja" itu
# pengetahuan gempa yang sangat umum/universal, sampai-sampai LLM tetap
# "mengingatnya" dari pelatihannya sendiri meski konteks yang dikasih
# sudah dibersihkan dari entitas indoor. Demi keamanan (ini info
# keselamatan nyawa), jawabannya di-hardcode langsung dari isi persis
# Gempa_Bumi.pdf, bypass LLM generation sepenuhnya.
JAWABAN_GEMPA_LUAR_RUANGAN = (
    "Berikut yang harus dilakukan saat gempa bumi terjadi di LUAR ruangan:\n"
    "1. Waspada kemungkinan pecahan kaca, genteng, atau material lain yang jatuh.\n"
    "2. Tetap lindungi kepala Anda.\n"
    "3. Segera menuju ke lapangan terbuka.\n"
    "4. Jangan berdiri dekat tiang, pohon, sumber listrik, atau gedung yang berpotensi roboh."
)
JAWABAN_GEMPA_DALAM_RUANGAN = (
    "Berikut yang harus dilakukan saat gempa bumi terjadi di DALAM ruangan:\n"
    "1. Berlindung di bawah meja yang kuat untuk menghindari benda jatuh dan jendela kaca.\n"
    "2. Lindungi kepala dengan bantal atau helm, atau berdirilah di bawah pintu.\n"
    "3. Bila sudah terasa aman, segera lari keluar rumah.\n"
    "4. Jangan gunakan lift saat terasa guncangan -- gunakan tangga darurat."
)


def format_kontak_darurat():
    lines = ["Berikut daftar nomor kontak darurat BPBD Kabupaten Bogor:"]
    for i, (nama, nomor) in enumerate(KONTAK_DARURAT, 1):
        lines.append(f"{i}. {nama}: {nomor}")
    return "\n".join(lines)

# ─── Keyword maps ──────────────────────────────────────────────────────────────

KEYWORDS_SPESIFIK = {
    'angin':      'Angin_Kencang.pdf',
    'puting':     'Angin_Kencang.pdf',
    'banjir':     'Banjir.pdf',
    'gempa':      'Gempa_Bumi.pdf',
    'longsor':    'Tanah_Longsor.pdf',
    'erupsi':     'Erupsi_Gunung_Api.pdf',
    'gunung':     'Erupsi_Gunung_Api.pdf',
    'vulkanik':   'Erupsi_Gunung_Api.pdf',
    'abu':        'Erupsi_Gunung_Api.pdf',
    'lava':       'Erupsi_Gunung_Api.pdf',
    'lahar':      'Erupsi_Gunung_Api.pdf',
    'karhutla':   'Karhutla.pdf',
    'kebakaran':  'Karhutla.pdf',
    'kekeringan': 'Kekeringan.pdf',
    'pergeseran': 'Pergeseran_Tanah.pdf',
    'darurat':        'nomor_darurat.pdf',
    'kesiapsiagaan':  'kesiapsiagaan.pdf',
}

KEYWORDS_UMUM = ['mitigasi', 'bencana', 'evakuasi', 'kumpul']

# Frasa penanda tipe pertanyaan Definisi-Teori
FRASA_DEFINISI = [
    'apa itu', 'apa yang dimaksud', 'apakah yang dimaksud', 'pengertian',
    'definisi', 'arti dari', 'artinya apa', 'jelaskan tentang', 'apa maksud',
    'apa pengertian', 'apa perbedaan', 'perbedaan antara',
]

# Frasa penanda tipe pertanyaan Lokasi-Wilayah
FRASA_LOKASI = [
    'dimana', 'di mana', 'wilayah mana', 'daerah mana', 'kecamatan mana',
    'desa mana', 'lokasi mana', 'daerah rawan', 'wilayah rawan',
    'titik kumpul', 'daerah yang rawan', 'wilayah yang rawan',
]

# Frasa penanda tipe pertanyaan Dampak/Bahaya (BUKAN prosedural per-fase,
# walaupun sering kebawa kata 'saat' yang salah ke-detect sebagai fase,
# misal "apa bahaya abu vulkanik SAAT erupsi" — itu nanya dampak, bukan
# "apa yang dilakukan pas fase Saat Bencana")
FRASA_DAMPAK = [
    'apa bahaya', 'apa dampak', 'apa efek', 'apa risiko', 'apa resiko',
    'bahaya apa saja', 'dampak apa saja', 'seberapa bahaya', 'apa akibat',
]

# Frasa penanda tipe pertanyaan Larangan (nanya apa yang TIDAK BOLEH
# dilakukan). Ini beda dari prosedural biasa — kalau gak dibedakan, LLM
# suka salah nyampur poin ANJURAN sebagai kalau poin LARANGAN (misal "tetap
# berada di bawah meja" itu anjuran, bukan larangan, tapi bisa ketuker).
FRASA_LARANGAN = [
    'tidak boleh', 'tidak diperbolehkan', 'dilarang', 'apa yang tidak',
    'hal yang harus dihindari', 'apa saja yang tidak boleh', 'jangan apa saja',
    'apa yang harus dihindari', 'pantangan',
]

# Peta fase dari teks pertanyaan
KEYWORDS_FASE = {
    'sebelum':     'Pra Bencana',
    'persiapan':   'Pra Bencana',
    'pra':         'Pra Bencana',
    'mencegah':    'Pra Bencana',
    'mitigasi':    'Pra Bencana',
    'saat':        'Saat Bencana',
    'ketika':      'Saat Bencana',
    'terjadi':     'Saat Bencana',
    'berlangsung': 'Saat Bencana',
    'setelah':     'Pasca Bencana',
    'pasca':       'Pasca Bencana',
    'sesudah':     'Pasca Bencana',
    'pemulihan':   'Pasca Bencana',
}


# ─── Helper: ekstrak keyword dan fase ─────────────────────────────────────────

def ekstrak_keywords(pertanyaan: str):
    bersih = re.sub(r'[^\w\s]', ' ', pertanyaan.lower())
    words  = bersih.split()

    spesifik = [k for k in words if k in KEYWORDS_SPESIFIK]
    umum     = [k for k in words if k in KEYWORDS_UMUM]
    fase     = next((KEYWORDS_FASE[k] for k in words if k in KEYWORDS_FASE), None)

    return spesifik, umum, fase


def deteksi_tipe_pertanyaan(pertanyaan: str):
    """
    Mengembalikan salah satu: 'definisi', 'lokasi', 'dampak', 'larangan',
    atau 'prosedural'. Urutan pengecekan penting: frasa yang lebih spesifik
    dicek lebih dulu. Ini mencegah kata 'saat' yang muncul insidental dalam
    kalimat (misal "bahaya X saat Y") salah ke-detect sebagai penanda fase.
    """
    kata = pertanyaan.lower().strip()

    if any(frasa in kata for frasa in FRASA_DEFINISI):
        return 'definisi'
    if any(frasa in kata for frasa in FRASA_LOKASI):
        return 'lokasi'
    if any(frasa in kata for frasa in FRASA_LARANGAN):
        return 'larangan'
    if any(frasa in kata for frasa in FRASA_DAMPAK):
        return 'dampak'
    return 'prosedural'


# ─── Graph traversal ───────────────────────────────────────────────────────────

def cari_konteks_graph(pertanyaan: str):
    spesifik, umum, _ = ekstrak_keywords(pertanyaan)

    # ── Kasus 1: ada keyword spesifik → tahu persis dokumen targetnya.
    # Ambil SEMUA entitas yang tersambung ke dokumen itu (bukan cuma yang
    # namanya cocok keyword). Ini penting buat dokumen yang isinya banyak
    # entitas "generik" (nomor telepon, nama institusi) yang gak akan
    # pernah match by nama, kayak nomor_darurat.pdf.
    # Perhatikan: relasi Dokumen->Entitas beda nama antar 2 script ingest
    # (MEMILIKI_ENTITAS dari ingest_data.py, MEMBAHAS dari ingest_tambahan.py),
    # makanya di sini dicek dua-duanya sekaligus pakai sintaks A|B.
    if spesifik:
        dokumen_target  = list(dict.fromkeys(KEYWORDS_SPESIFIK[k] for k in spesifik))
        kondisi_dokumen = " OR ".join([f"d.nama = '{d}'" for d in dokumen_target])

        query_relasi = f"""
        MATCH (d:Dokumen)-[:MEMBAHAS|MEMILIKI_ENTITAS]->(e:Entitas)
        WHERE {kondisi_dokumen}
        OPTIONAL MATCH (e)-[r]->(target:Entitas)
        OPTIONAL MATCH (source:Entitas)-[r2]->(e)
        RETURN DISTINCT
            e.nama AS entitas,
            e.deskripsi AS deskripsi,
            e.fase AS fase,
            collect(DISTINCT type(r) + ' -> ' + target.nama) AS relasi_keluar,
            collect(DISTINCT source.nama + ' -> ' + type(r2)) AS relasi_masuk
        """
        query_dokumen = f"""
        MATCH (d:Dokumen)
        WHERE {kondisi_dokumen}
        RETURN DISTINCT d.nama AS sumber, d.tipe AS tipe
        """
        return graph.query(query_relasi), graph.query(query_dokumen)

    # ── Kasus 2: cuma ada keyword umum, atau gak ada keyword sama sekali.
    # Gak tahu dokumen spesifik targetnya, jadi tetap cari by nama entitas.
    keywords = umum
    if not keywords:
        semua  = list(KEYWORDS_SPESIFIK.keys()) + KEYWORDS_UMUM
        bersih = re.sub(r'[^\w\s]', ' ', pertanyaan.lower())
        keywords = [w for w in bersih.split() if any(k in w for k in semua)]
        if not keywords:
            return [], []

    kondisi_entitas = " OR ".join([f"toLower(e.nama) CONTAINS '{k}'" for k in keywords])

    query_relasi = f"""
    MATCH (e:Entitas)
    WHERE {kondisi_entitas}
    OPTIONAL MATCH (e)-[r]->(target:Entitas)
    OPTIONAL MATCH (source:Entitas)-[r2]->(e)
    RETURN 
        e.nama AS entitas,
        e.deskripsi AS deskripsi,
        e.fase AS fase,
        collect(DISTINCT type(r) + ' -> ' + target.nama) AS relasi_keluar,
        collect(DISTINCT source.nama + ' -> ' + type(r2)) AS relasi_masuk
    """

    query_dokumen = f"""
    MATCH (d:Dokumen)-[:MEMBAHAS|MEMILIKI_ENTITAS]->(e:Entitas)
    WHERE {kondisi_entitas}
    RETURN DISTINCT d.nama AS sumber, d.tipe AS tipe
    """

    return graph.query(query_relasi), graph.query(query_dokumen)


# Entitas nama kota yang sering muncul di dokumen cuma sebagai info latar
# belakang ("Jakarta rentan banjir") bukan poin tindakan, tapi berulang
# kali ke-tag fase secara keliru saat ekstraksi (noise LLM extractor kecil)
# sehingga malah menang prioritas di atas aksi yang sebenarnya. Daripada
# re-ingest ulang cuma buat isu ini, di-exclude langsung di level kode.
NAMA_KOTA_BUKAN_TINDAKAN = {
    'jakarta', 'depok', 'tangerang', 'bekasi', 'surabaya', 'bandung', 'bogor',
}

# Entitas generik dari definisi umum UU No. 24/2007 (bencana.pdf) yang sering
# "bocor" jadi jawaban buat pertanyaan spesifik jenis bencana lain (misal
# "apa dampak kekeringan" malah dijawab "korban jiwa, kerusakan lingkungan,
# dampak psikologis" — itu definisi UMUM bencana, bukan dampak spesifik).
# Serta entitas boilerplate "harta & dokumentasi" yang terus berulang di
# hampir semua dokumen sumber (poin "12" di tiap PDF) dan sering nyasar ke
# pertanyaan yang gak relevan sama sekali (klaim asuransi/dokumentasi foto).
ENTITAS_NOISE_UMUM = {
    'korban jiwa manusia', 'kerusakan lingkungan', 'kerugian harta benda',
    'dampak psikologis', 'harta dan kepemilikan', 'harta kita',
    'catatan harta', 'foto', 'dokumentasi, catatan harta',
}

# Kata kunci yang nunjukin entitas itu spesifik buat situasi DI DALAM/DI LUAR
# ruangan. Dipakai buat nyaring konteks gempa bumi -- soalnya dokumen sumber
# gak misahin tegas dua situasi ini (sama-sama fase "Saat Bencana"), jadi
# instruksi prompt doang gak cukup, konteksnya sendiri perlu difilter biar
# LLM gak "digoda" info yang salah konteks.
KATA_KUNCI_DALAM_RUANGAN = ['meja', 'lift', 'tangga darurat', 'jendela', 'dinding bangunan', 'interphone']
KATA_KUNCI_LUAR_RUANGAN = ['lapangan terbuka', 'tiang', 'papan reklame', 'sumber listrik', 'gedung', 'pecahan kaca', 'genteng', 'pohon']


def format_konteks(hasil_relasi, hasil_dokumen, fase_filter=None, max_entitas=25,
                    exclude_kota=True, konteks_ruangan=None):
    """
    fase_filter: kalau diisi (misal 'Saat Bencana'), cuma entitas yang
    fase-nya cocok ATAU gak berfase spesifik (umum/definisi) yang ditampilkan.
    Ini bikin jawaban fase-spesifik jauh lebih fokus & gak nyampur fase lain,
    karena sekarang fase entitas eksplisit dari graph, bukan tebakan LLM.

    max_entitas: batas jumlah entitas yang dimasukkan ke prompt. Penting
    buat performa — sejak retrieval berbasis dokumen (ambil SEMUA entitas
    terkait dokumen), dokumen besar (Banjir.pdf 68 entitas, kesiapsiagaan.pdf
    76 entitas) bisa bikin prompt kepanjangan & LLM lokal jadi sangat lambat
    (bisa timeout). Entitas yang PUNYA deskripsi diprioritaskan duluan
    karena paling informatif, sisanya (cuma nama/relasi) dipotong duluan.

    exclude_kota: default True, buang entitas nama kota generik dari
    NAMA_KOTA_BUKAN_TINDAKAN. Set False buat pertanyaan tipe 'lokasi' yang
    justru butuh info kota/wilayah.

    konteks_ruangan: 'dalam' / 'luar' / None. Kalau diisi, buang entitas yang
    isinya spesifik buat situasi LAWANNYA (misal konteks_ruangan='luar' buang
    entitas soal "meja"/"lift"). Ini SELAIN instruksi prompt -- dua lapis
    pertahanan biar LLM gak ketemu info yang salah konteks sama sekali,
    bukan cuma disuruh mengabaikannya.
    """
    # Filter fase dulu, baru urutkan pakai prioritas 2 tingkat:
    # 1) entitas yang fase-nya PERSIS cocok sama fase_filter menang duluan
    #    (entitas umum/tanpa fase, kayak "Jakarta rentan banjir", kalah
    #    prioritas — itu cuma info latar belakang, bukan tindakan fase itu)
    # 2) di antara yang sama prioritasnya, yang punya deskripsi menang
    #    (lebih informatif daripada cuma nama tanpa penjelasan)
    kandidat = []
    for item in hasil_relasi:
        nama = (item.get('entitas') or '').strip().lower()
        deskripsi_lower = (item.get('deskripsi') or '').strip().lower()

        # Noise umum (UU generik + boilerplate harta/dokumentasi) SELALU
        # di-exclude, gak peduli tipe pertanyaan — ini murni noise, gak
        # pernah jadi jawaban yang relevan di 99 soal uji coba.
        if nama in ENTITAS_NOISE_UMUM:
            continue

        # Filter indoor/outdoor kalau pertanyaan spesifik minta salah satunya
        gabungan = f"{nama} {deskripsi_lower}"
        if konteks_ruangan == 'luar' and any(k in gabungan for k in KATA_KUNCI_DALAM_RUANGAN):
            continue
        if konteks_ruangan == 'dalam' and any(k in gabungan for k in KATA_KUNCI_LUAR_RUANGAN):
            continue

        if exclude_kota:
            if nama in NAMA_KOTA_BUKAN_TINDAKAN:
                continue
            # Entitas LAIN yang deskripsinya sendiri isinya cuma daftar kota
            # (misal entitas "wilayah terdampak" dengan deskripsi "Jakarta,
            # Bogor, Depok, ... mengalami banjir") — hitung berapa nama kota
            # dari blacklist yang muncul di teks deskripsinya; kalau 2+,
            # anggap itu cuma daftar kota juga, buang.
            jumlah_kota_disebut = sum(1 for k in NAMA_KOTA_BUKAN_TINDAKAN if k in deskripsi_lower)
            if jumlah_kota_disebut >= 2:
                continue

        fase = (item.get('fase') or '').strip()
        if fase_filter and fase and fase != fase_filter:
            continue
        kandidat.append(item)

    def prioritas(item):
        fase = (item.get('fase') or '').strip()
        ada_deskripsi = bool((item.get('deskripsi') or '').strip())
        skor_fase = 0 if (fase_filter and fase == fase_filter) else 1
        skor_deskripsi = 0 if ada_deskripsi else 1
        return (skor_fase, skor_deskripsi)

    kandidat.sort(key=prioritas)
    kandidat = kandidat[:max_entitas]

    lines = []
    for item in kandidat:
        entitas   = item['entitas']
        deskripsi = (item.get('deskripsi') or '').strip()
        fase      = (item.get('fase') or '').strip()
        keluar    = [r for r in item['relasi_keluar'] if r and '-> None' not in r]
        masuk     = [r for r in item['relasi_masuk']  if r and 'None ->' not in r]

        label = f"[{fase}] " if fase else "[Umum] "

        # Deskripsi faktual entitas ditulis DULUAN, ini yang sebelumnya hilang
        # total dan bikin soal definisi/fakta spesifik selalu gagal dijawab.
        if deskripsi:
            lines.append(f"• {label}{entitas}: {deskripsi}")

        if keluar:
            targets = [r.split('-> ')[1] for r in keluar if '-> ' in r]
            if targets:
                lines.append(f"• {label}{entitas} berkaitan dengan: {', '.join(targets[:5])}")
        if masuk:
            sources = [r.split(' ->')[0] for r in masuk if ' ->' in r]
            if sources:
                lines.append(f"• {label}{entitas} terkait dengan: {', '.join(sources[:3])}")

    return "\n".join(lines) if lines else ""


# ─── Fungsi utama chatbot ──────────────────────────────────────────────────────

# Frasa definisi umum UU No. 24/2007 yang kadang muncul di jawaban meski
# entitasnya sudah di-blacklist dari konteks (kemungkinan besar model
# "mengingatnya" dari pengetahuan pelatihannya sendiri, bukan dari konteks
# yang dikirim). Ini SAFETY NET terakhir: kalau prompt instruction gagal
# mencegahnya, baris yang mengandung frasa ini dibuang total dari jawaban
# final sebelum ditampilkan ke pengguna -- gak bergantung pada kepatuhan
# LLM terhadap instruksi, jadi hasilnya pasti (deterministik).
FRASA_KONTAMINASI_UU = [
    'korban jiwa manusia', 'kerusakan lingkungan', 'kerugian harta benda',
    'dampak psikologis',
]


def bersihkan_kontaminasi_uu(teks: str) -> str:
    """Buang baris (poin/kalimat) yang mengandung frasa definisi umum UU
    24/2007 yang tidak relevan dengan pertanyaan spesifik jenis bencana,
    lalu rapikan ulang nomor urut poin yang tersisa (mis. dari 3,4,5,6
    yang tersisa jadi 1,2,3,4) biar gak lompat-lompat."""
    baris_bersih = []
    for baris in teks.split('\n'):
        baris_lower = baris.lower()
        if any(frasa in baris_lower for frasa in FRASA_KONTAMINASI_UU):
            continue  # buang baris ini, lanjut ke baris berikutnya
        baris_bersih.append(baris)
    hasil = '\n'.join(baris_bersih).strip()
    if not hasil:
        return teks  # jaga-jaga: kalau semua baris kebuang, kembalikan versi asli

    # Renumber ulang poin bernomor ("1.", "2.", dst di awal baris) secara
    # berurutan, biar gak ada nomor yang lompat akibat baris yang dibuang.
    nomor_baru = 1
    baris_final = []
    for baris in hasil.split('\n'):
        m = re.match(r'^(\d+)\.(\s+)(.*)', baris)
        if m:
            baris_final.append(f"{nomor_baru}.{m.group(2)}{m.group(3)}")
            nomor_baru += 1
        else:
            baris_final.append(baris)
    return '\n'.join(baris_final)


def tanya_chatbot(pertanyaan: str):
    kata = pertanyaan.lower().strip()

    # Sapaan / basa-basi (hanya jika tidak ada keyword bencana)
    ada_keyword = any(k in kata for k in list(KEYWORDS_SPESIFIK.keys()) + KEYWORDS_UMUM)
    if not ada_keyword:
        if any(s in kata for s in ['halo', 'hi', 'hai', 'haloo', 'hallo', 'hey']):
            return ("Halo! Selamat datang di layanan chatbot mitigasi bencana "
                    "BPBD Kabupaten Bogor. Ada yang bisa saya bantu? 🙏", "", "")
        if any(s in kata for s in ['makasih', 'terima kasih', 'thanks', 'ok', 'selesai', 'cukup']):
            return ("Sama-sama! Jika ada pertanyaan lain seputar mitigasi bencana, "
                    "jangan ragu untuk bertanya ya. 🙏", "", "")

    # Gempa bumi luar/dalam ruangan: bypass graph & LLM total, jawab langsung
    # dari data hardcode. Ini demi keamanan (info keselamatan nyawa), karena
    # terbukti berulang kali salah walau sudah dikasih instruksi prompt DAN
    # filter konteks -- LLM tetap "mengingat" versi indoor dari pengetahuan
    # umumnya sendiri.
    if 'gempa' in kata and 'luar ruangan' in kata:
        return (JAWABAN_GEMPA_LUAR_RUANGAN, "Gempa_Bumi.pdf", "")
    if 'gempa' in kata and 'dalam ruangan' in kata:
        return (JAWABAN_GEMPA_DALAM_RUANGAN, "Gempa_Bumi.pdf", "")

    # Kontak darurat: bypass graph & LLM total, jawab langsung dari data
    # hardcode yang sudah diverifikasi. Ini demi keamanan/akurasi mutlak,
    # karena tabel sumbernya (nomor_darurat.pdf) rusak saat diekstrak.
    if any(frasa in kata for frasa in FRASA_KONTAK_DARURAT):
        return (format_kontak_darurat(), "nomor_darurat.pdf", "")

    # Ambil konteks dari graph
    hasil_relasi, hasil_dokumen = cari_konteks_graph(pertanyaan)

    if not hasil_relasi and not hasil_dokumen:
        return (
            "Maaf, saya tidak menemukan informasi terkait pertanyaan Anda "
            "dalam dokumen yang tersedia. Silakan hubungi BPBD Kabupaten Bogor "
            "untuk informasi lebih lanjut.",
            "",
            ""
        )

    # Deteksi tipe pertanyaan dan fase LEBIH DULU, sebelum format_konteks,
    # biar kalau pertanyaan minta fase spesifik / tipe lokasi, context bisa
    # difilter/disesuaikan (pakai label e.fase eksplisit dari graph, bukan
    # tebakan LLM lagi; dan exclude_kota dimatikan khusus tipe lokasi).
    tipe = deteksi_tipe_pertanyaan(pertanyaan)
    _, _, fase = ekstrak_keywords(pertanyaan)

    exclude_kota = (tipe != 'lokasi')

    # Deteksi kalau pertanyaan spesifik soal DI DALAM/DI LUAR ruangan (paling
    # sering relevan buat gempa bumi), biar konteksnya difilter sesuai
    pertanyaan_lower_cek = pertanyaan.lower()
    if 'luar ruangan' in pertanyaan_lower_cek:
        konteks_ruangan = 'luar'
    elif 'dalam ruangan' in pertanyaan_lower_cek:
        konteks_ruangan = 'dalam'
    else:
        konteks_ruangan = None

    konteks_awal = format_konteks(hasil_relasi, hasil_dokumen, exclude_kota=exclude_kota, konteks_ruangan=konteks_ruangan)
    sumber_file = (", ".join([d['sumber'] for d in hasil_dokumen])
                   if hasil_dokumen else "Basis data mitigasi BPBD Kab. Bogor")

    fase_filter = fase if (tipe not in ('definisi', 'lokasi', 'dampak') and fase) else None
    konteks = format_konteks(hasil_relasi, hasil_dokumen, fase_filter=fase_filter, exclude_kota=exclude_kota, konteks_ruangan=konteks_ruangan)
    # Fallback: kalau filter fase bikin konteks kosong (misal semua entitas
    # yang ke-retrieve gak ada yang match), pakai versi tanpa filter dulu
    # daripada bikin chatbot bilang "tidak tersedia" secara keliru.
    if not konteks.strip() and konteks_awal.strip():
        konteks = konteks_awal

    if tipe == 'definisi':
        instruksi_fase = """Pertanyaan ini bersifat DEFINISI/TEORI, bukan prosedural.
Jawab dengan menjelaskan pengertian/konsep yang ditanyakan secara singkat, jelas, dan padat (maksimal 4 kalimat).
JANGAN membagi jawaban ke dalam fase Pra Bencana / Saat Bencana / Pasca Bencana.
JANGAN memberikan langkah-langkah tindakan kecuali diminta.
PENTING: cek dulu apakah ADA entitas di konteks di atas yang deskripsinya SECARA LANGSUNG
menjelaskan istilah yang ditanyakan. Kalau tidak ada entitas dengan deskripsi yang cocok
persis dengan istilah tersebut, JANGAN mengarang definisi sendiri dari entitas-entitas lain
yang cuma terkait secara tidak langsung — katakan dengan jujur bahwa dokumen tidak
menjelaskan istilah tersebut secara eksplisit, baru sebutkan informasi terkait yang tersedia
(kalau ada) sebagai konteks tambahan."""

    elif tipe == 'lokasi':
        instruksi_fase = """Pertanyaan ini bersifat LOKASI/WILAYAH.
Jawab dengan menyebutkan nama wilayah/kecamatan/desa secara spesifik HANYA jika tersedia dalam informasi di atas.
JANGAN membagi jawaban ke dalam fase Pra Bencana / Saat Bencana / Pasca Bencana.
Jika informasi lokasi spesifik tidak tersedia dalam data, katakan dengan jujur bahwa data tersebut tidak tersedia dan sarankan menghubungi BPBD Kabupaten Bogor."""

    elif tipe == 'dampak':
        instruksi_fase = """Pertanyaan ini menanyakan BAHAYA/DAMPAK/RISIKO, bukan langkah tindakan per fase.
Sebutkan SETIAP bahaya/dampak spesifik yang disebutkan dalam informasi di atas secara eksplisit dan konkret.
JANGAN menggabungkan atau meringkas beberapa bahaya jadi frasa umum seperti "efek negatif lainnya",
"dampak buruk lainnya", atau sejenisnya — sebutkan satu per satu apa bahayanya secara jelas.
Format wajib: list bernomor 1., 2., dst, maksimal 5 poin, satu bahaya spesifik per poin.
JANGAN membagi jawaban ke dalam fase Pra Bencana / Saat Bencana / Pasca Bencana.
JANGAN menulis embel-embel seperti "jawaban untuk fase X" — langsung jawab dampaknya saja.
Kata 'saat' dalam pertanyaan ini adalah bagian dari kalimat biasa, BUKAN penanda fase."""

    elif tipe == 'larangan':
        instruksi_fase = f"""Pertanyaan ini menanyakan LARANGAN — hal yang TIDAK BOLEH/DILARANG dilakukan{f' saat fase {fase}' if fase else ''}.
Setiap baris informasi di atas SUDAH ditandai label [Pra Bencana]/[Saat Bencana]/[Pasca Bencana]/[Umum].
HANYA sebutkan hal-hal yang jelas berupa LARANGAN/HAL YANG HARUS DIHINDARI berdasarkan informasi di atas.
PENTING: banyak informasi di atas berupa ANJURAN (hal yang DISARANKAN dilakukan), BUKAN larangan —
JANGAN salah menyebutkan anjuran sebagai larangan. Contoh: "berlindung di bawah meja" itu ANJURAN
(hal yang harus dilakukan), bukan larangan.
Kalau informasi larangan eksplisit tidak tersedia dalam data di atas, katakan dengan jujur bahwa
informasi spesifik soal larangan tidak tersedia — JANGAN memaksakan anjuran jadi larangan.
Format: list bernomor 1., 2., dst, maksimal 5 poin, tiap poin diawali "Jangan..." atau "Hindari...\""""

    elif fase:
        instruksi_fase = f"""Pertanyaan ini HANYA menanyakan fase {fase}.
Setiap baris informasi di atas SUDAH ditandai label [Pra Bencana]/[Saat Bencana]/[Pasca Bencana]/[Umum]
oleh sistem — gunakan label itu apa adanya, JANGAN menebak sendiri fase suatu informasi.
Jawab HANYA pakai informasi yang berlabel [{fase}] atau [Umum], maksimal 5 poin singkat, penomoran mulai dari 1.
JANGAN menyebutkan atau mencampur informasi berlabel fase lain sama sekali.
JANGAN masukkan info lokasi/kota/wilayah yang PERNAH terdampak bencana (misal daftar nama kota)
sebagai poin tindakan — itu bukan instruksi, itu cuma informasi latar belakang, abaikan kalau muncul."""

    else:
        instruksi_fase = """Pertanyaan ini bersifat PROSEDURAL dan tidak menyebutkan fase tertentu.
Setiap baris informasi di atas SUDAH ditandai label [Pra Bencana]/[Saat Bencana]/[Pasca Bencana]/[Umum]
oleh sistem — gunakan label itu apa adanya buat nentuin taruh di fase mana, JANGAN menebak sendiri.
Jawab singkat dan jelas, bagi PERSIS ke dalam 3 fase berikut, dalam urutan ini:
**Pra Bencana:**
**Saat Bencana:**
**Pasca Bencana:**

Aturan ketat:
- Setiap fase MAKSIMAL 3 poin — kalau datanya cuma cukup buat 1 atau 2 poin, tulis segitu aja,
  JANGAN dipaksa jadi 3 poin dengan mengarang atau mengulang.
- Penomoran mulai dari 1 di tiap fase.
- Jangan tulis jumlah poin dalam judul fase.
- Taruh info berlabel [Umum] di fase yang paling relevan berdasarkan isinya, JANGAN taruh sembarang.
- Jangan campur informasi antar fase (misal info berlabel [Pra Bencana] tidak boleh muncul di bagian Saat Bencana).
- KALAU untuk salah satu fase BENAR-BENAR TIDAK ADA informasi relevan sama sekali di atas:
  JANGAN tulis heading fase itu, JANGAN tulis "Informasi tidak tersedia" berulang-ulang per poin —
  cukup LEWATI/HILANGKAN seluruh bagian fase tersebut dari jawaban. Cukup tampilkan fase yang
  memang punya informasi. Kalau semua 3 fase kosong baru bilang jujur datanya tidak tersedia sama sekali.
- JANGAN masukkan info lokasi/kota/wilayah yang PERNAH terdampak bencana (misal daftar nama kota)
  sebagai poin tindakan — itu bukan instruksi, itu cuma informasi latar belakang, abaikan kalau muncul."""

    # ─── Koreksi tambahan buat kasus spesifik yang HISTORIS sering keliru ──
    # (ditemukan lewat validasi manual 99 soal: gempa dalam/luar ruangan
    # tertukar, dan pergeseran tanah sering disamakan/dicampur sama tanah
    # longsor padahal dua fenomena berbeda menurut dokumen sumber)
    instruksi_koreksi = ""
    pertanyaan_lower = pertanyaan.lower()

    if 'luar ruangan' in pertanyaan_lower:
        instruksi_koreksi += """

KOREKSI PENTING: Pertanyaan ini spesifik soal situasi DI LUAR RUANGAN.
JANGAN berikan instruksi "berlindung di bawah meja" atau instruksi lain untuk DI DALAM ruangan.
Untuk DI LUAR ruangan, fokus HANYA ke: segera menuju lapangan terbuka, menjauhi tiang/pohon/sumber
listrik/gedung yang berpotensi roboh, dan waspada pecahan kaca/genteng/material lain yang jatuh."""
    elif 'dalam ruangan' in pertanyaan_lower:
        instruksi_koreksi += """

KOREKSI PENTING: Pertanyaan ini spesifik soal situasi DI DALAM RUANGAN.
JANGAN berikan instruksi "menuju lapangan terbuka" (itu untuk DI LUAR ruangan).
Untuk DI DALAM ruangan, fokus HANYA ke: berlindung di bawah meja yang kuat, lindungi kepala dengan
bantal/helm atau berdiri di bawah pintu, dan jangan gunakan lift (pakai tangga darurat)."""

    if 'pergeseran tanah' in pertanyaan_lower:
        instruksi_koreksi += """

KOREKSI PENTING soal PERGESERAN TANAH (sering tertukar dengan TANAH LONGSOR, padahal beda fenomena):
Pergeseran tanah = perpindahan lapisan tanah TANPA kehilangan kontinuitas (horizontal/vertikal, bentuk
lereng relatif tidak berubah signifikan). Tanah longsor = pergerakan TIBA-TIBA dan CEPAT sejumlah besar
tanah ke bawah lereng disertai pemisahan dan jatuhnya materi tanah secara besar-besaran. JANGAN
mendefinisikan salah satu pakai definisi yang lain. JANGAN menyatakan pergeseran tanah "dapat berkembang
menjadi" tanah longsor -- dokumen sumber TIDAK menyatakan itu, keduanya fenomena berbeda, bukan tahapan
dari satu ke yang lain. Kalau ditanya soal keselamatan saat kejadian pergeseran tanah, arahkan untuk
SEGERA MENGHUBUNGI pihak berwenang (pemerintah daerah/polisi/petugas penyelamat) -- BUKAN menjauhi
atau menghindari mereka."""

    prompt = f"""Kamu adalah asisten mitigasi bencana BPBD Kabupaten Bogor yang ramah dan mudah dipahami masyarakat awam.
Gunakan bahasa yang sederhana, hindari istilah teknis berlebihan.
Jawab HANYA berdasarkan informasi di bawah ini.

ATURAN FORMAT PENTING: Bagian "Informasi dari basis data mitigasi" di bawah ini pakai format
internal untuk sistem, BUKAN untuk ditampilkan ke pengguna. Formatnya seperti:
"• [Pra Bencana] nama_entitas: deskripsi" atau "• [Umum] nama_entitas berkaitan dengan: X, Y, Z".
Tanda kurung siku seperti [Pra Bencana], [Saat Bencana], [Pasca Bencana], [Umum], tanda bullet "•",
dan frasa "berkaitan dengan:" itu SEMUA cuma label internal buat sistem — JANGAN PERNAH menyalin
simbol-simbol itu ke jawabanmu dengan cara apapun.

Contoh SALAH (jangan seperti ini):
"1. [Umum] Lindungi mata dengan kacamata pelindung."
"2. [Saat Bencana] jakarta terkait dengan: banjir – Jakarta mengalami banjir."
"3. Pergeseran tanah berkaitan dengan: kerusakan pada struktur bangunan."

Contoh BENAR (tulis seperti ini):
"1. Lindungi mata dengan kacamata pelindung."
"3. Pergeseran tanah dapat menyebabkan kerusakan pada struktur bangunan."

PENTING SEKALI: kalau sebuah entitas di konteks CUMA punya relasi (format "X berkaitan dengan: Y, Z")
TANPA deskripsi yang jelas, JANGAN menyalin mentah format itu ke jawabanmu. Ubah jadi kalimat sebab-akibat
atau penjelasan natural (misal "X berkaitan dengan: Y" menjadi "X dapat menyebabkan/melibatkan/berdampak
pada Y" -- sesuaikan kata kerja penghubungnya dengan konteks kalimat, bukan asal salin frasa
"berkaitan dengan"). Kalau informasi yang tersedia untuk entitas itu terlalu sedikit/tidak jelas
hubungannya, lebih baik LEWATI entitas itu daripada memaksakan kalimat yang tidak jelas maknanya.

Tulis ulang semua informasi dengan kalimat natural buatanmu sendiri, seolah kamu menjelaskan
langsung ke masyarakat awam — tanpa embel-embel label/tag apapun.

Informasi dari basis data mitigasi:
---
{konteks}
---

Pertanyaan: {pertanyaan}

{instruksi_fase}
{instruksi_koreksi}
"""

    respon = llm.invoke(prompt)
    respon = bersihkan_kontaminasi_uu(respon)
    return respon, sumber_file, konteks


# ─── Flask routes ──────────────────────────────────────────────────────────────

# ─── CACHE DATABASE (biar respons cepat, maksimal <3 detik) ───────────────
# Pertanyaan yang sudah pernah/mirip ditanyakan diambil langsung dari SQLite
# (cache_jawaban.db) tanpa perlu generate ulang lewat Gemma3:4b (yang makan
# waktu ~279 detik). Database ini diisi awal dari 99 pasangan tanya-jawab
# final (lewat init_database.py) dan terus bertambah otomatis tiap ada
# pertanyaan baru yang berhasil dijawab.
DB_PATH = "cache_jawaban.db"
AMBANG_KEMIRIPAN = 0.75  # seberapa mirip (0-1) pertanyaan baru dianggap "sama" dgn yang di cache
# Diturunkan dari 0.85 -> 0.75 supaya paraphrase wajar (mis. "saat kebakaran
# hutan" vs "saat terjadi kebakaran hutan dan lahan") tetap ke-match. Ini
# AMAN diturunkan karena sudah ada pengecekan fase terpisah (lihat
# cari_di_cache) yang mencegah pertanyaan beda fase ikut ke-cocokkan
# meskipun teksnya mirip -- jadi longgarnya threshold teks gak bikin
# resiko ketuker fase kayak sebelumnya.


def normalisasi(teks: str) -> str:
    """Samakan format teks biar perbandingan gak kepeleset gara-gara
    kapitalisasi/spasi/tanda baca (misal 'Apa itu Banjir?' vs 'apa itu banjir')."""
    teks = teks.lower().strip()
    teks = re.sub(r'[^\w\s]', '', teks)
    teks = re.sub(r'\s+', ' ', teks)
    return teks


def pastikan_tabel_cache_ada():
    """Jaga-jaga: buat tabel cache kalau belum ada (misal init_database.py
    belum pernah dijalankan), biar app.py gak crash."""
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
            asal TEXT DEFAULT 'otomatis',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pertanyaan_normalized ON cache_jawaban(pertanyaan_normalized)")
    conn.commit()
    conn.close()


def deteksi_dokumen_target(teks: str):
    """Deteksi dokumen/jenis bencana spesifik dari teks pertanyaan, pakai
    KEYWORDS_SPESIFIK yang sama dengan yang dipakai retrieval utama.
    Dipakai buat mencegah cache fuzzy-match ketuker jenis bencana yang
    beda (misal 'dampak pergeseran tanah' vs 'dampak angin kencang' --
    dua kalimat itu strukturnya mirip banget, cuma beda 1-2 kata, jadi
    gampang lolos ambang kemiripan teks kalau gak dicek jenis bencananya)."""
    teks_lower = teks.lower()
    for kata_kunci, dokumen in KEYWORDS_SPESIFIK.items():
        if kata_kunci in teks_lower:
            return dokumen
    return None


def deteksi_ruangan(teks: str):
    """Deteksi apakah teks spesifik soal DI DALAM atau DI LUAR ruangan.
    None kalau gak nyebut keduanya."""
    tl = teks.lower()
    if 'luar ruangan' in tl:
        return 'luar'
    if 'dalam ruangan' in tl:
        return 'dalam'
    return None


def cari_di_cache(pertanyaan: str):
    """Cari jawaban di database cache. Return (jawaban, sumber, konteks) kalau
    ketemu pertanyaan yang persis sama atau mirip banget, None kalau enggak
    ketemu sama sekali (berarti harus generate baru lewat GraphRAG).

    PENTING: kalau pertanyaan baru & kandidat cache punya fase yang BEDA
    (misal satu nanya "saat" kejadian, satu lagi nanya "setelah/pasca"),
    ATAU punya jenis bencana/dokumen target yang BEDA (misal satu soal
    "pergeseran tanah", satu lagi soal "angin kencang"), ATAU beda konteks
    dalam/luar ruangan, fuzzy match DIBATALKAN meski teksnya mirip --
    soalnya beda konteks itu = beda maksud & beda jawaban yang benar,
    walau kata-katanya mirip. Berlaku juga buat EXACT match teks (bukan
    cuma fuzzy) karena "ruangan" ini krusial buat keselamatan.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT pertanyaan, pertanyaan_normalized, jawaban, sumber, konteks FROM cache_jawaban")
    semua = cur.fetchall()
    conn.close()

    if not semua:
        return None

    pertanyaan_norm = normalisasi(pertanyaan)
    _, _, fase_baru = ekstrak_keywords(pertanyaan)
    dokumen_baru = deteksi_dokumen_target(pertanyaan)
    ruangan_baru = deteksi_ruangan(pertanyaan)

    # 1. Exact match dulu (masih dicek ruangan-nya juga -- kalau ada entry
    # cache yang teksnya kebetulan persis sama tapi somehow salah tag,
    # ini jaring pengaman terakhir)
    for teks_asli, norm, jawaban, sumber, konteks in semua:
        if norm == pertanyaan_norm and deteksi_ruangan(teks_asli) == ruangan_baru:
            return jawaban, sumber, konteks

    # 2. Kalau gak ada exact match, cari kandidat yang paling MIRIP, tapi
    # cuma boleh dipakai kalau fase-nya JUGA cocok DAN jenis bencananya
    # JUGA cocok DAN konteks ruangannya JUGA cocok
    daftar_norm = [row[1] for row in semua]
    kandidat_mirip = difflib.get_close_matches(pertanyaan_norm, daftar_norm, n=5, cutoff=AMBANG_KEMIRIPAN)
    for kandidat_norm in kandidat_mirip:
        for teks_asli, norm, jawaban, sumber, konteks in semua:
            if norm == kandidat_norm:
                _, _, fase_kandidat = ekstrak_keywords(teks_asli)
                dokumen_kandidat = deteksi_dokumen_target(teks_asli)
                ruangan_kandidat = deteksi_ruangan(teks_asli)
                if fase_baru == fase_kandidat and dokumen_baru == dokumen_kandidat and ruangan_baru == ruangan_kandidat:
                    return jawaban, sumber, konteks
                # ada yang beda -> skip kandidat ini, coba kandidat lain

    return None


def simpan_ke_cache(pertanyaan: str, jawaban: str, sumber: str, konteks: str):
    """Simpan pasangan tanya-jawab baru ke database, biar pertanyaan yang
    sama/mirip berikutnya bisa langsung dijawab instan dari cache."""
    if "ERROR" in jawaban:
        return  # jangan simpan jawaban gagal ke cache
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cache_jawaban (pertanyaan, pertanyaan_normalized, jawaban, sumber, konteks, asal)
        VALUES (?, ?, ?, ?, ?, 'otomatis')
    """, (pertanyaan, normalisasi(pertanyaan), jawaban, sumber, konteks))
    conn.commit()
    conn.close()


pastikan_tabel_cache_ada()


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data       = request.get_json()
    pertanyaan = data.get("pertanyaan", "")
    debug      = data.get("debug", False)  # kalau True, ikutkan konteks mentah (buat evaluasi RAGAS)
    if not pertanyaan.strip():
        return jsonify({"jawaban": "", "sumber": ""})

    # Gempa luar/dalam ruangan: SELALU bypass cache sama sekali, langsung ke
    # tanya_chatbot() yang akan mengembalikan jawaban hardcode secara
    # deterministik. Ini demi keamanan (info keselamatan nyawa) -- gak mau
    # ambil resiko fuzzy-match cache ketuker luar/dalam ruangan lagi.
    kata_cek = pertanyaan.lower().strip()
    if 'gempa' in kata_cek and ('luar ruangan' in kata_cek or 'dalam ruangan' in kata_cek):
        jawaban, sumber, konteks = tanya_chatbot(pertanyaan)
        hasil = {"jawaban": jawaban, "sumber": sumber}
        if debug:
            hasil["konteks"] = konteks
        return jsonify(hasil)

    # 1) Coba cari di cache dulu -- kalau ketemu, jawab INSTAN (<1 detik)
    hasil_cache = cari_di_cache(pertanyaan)
    if hasil_cache is not None:
        jawaban, sumber, konteks = hasil_cache
        hasil = {"jawaban": jawaban, "sumber": sumber}
        if debug:
            hasil["konteks"] = konteks
        return jsonify(hasil)

    # 2) Gak ketemu di cache -> jalanin proses GraphRAG penuh (lambat, ~279 detik)
    jawaban, sumber, konteks = tanya_chatbot(pertanyaan)
    simpan_ke_cache(pertanyaan, jawaban, sumber, konteks)  # simpan buat next time

    hasil = {"jawaban": jawaban, "sumber": sumber}
    if debug:
        hasil["konteks"] = konteks
    return jsonify(hasil)


if __name__ == "__main__":
    app.run(debug=True)