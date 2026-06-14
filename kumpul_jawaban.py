import os
import re
import csv
import time
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_ollama import OllamaLLM

start = time.time()
load_dotenv(dotenv_path='.env', override=True)

graph = Neo4jGraph(
    url=os.getenv('NEO4J_URI'),
    username=os.getenv('NEO4J_USERNAME'),
    password=os.getenv('NEO4J_PASSWORD'),
    database=os.getenv('NEO4J_DATABASE')
)

llm_ollama = OllamaLLM(model='gemma3:4b')

# ─── Dataset: pertanyaan + reference dari konteks graph ───────────────────────
# Reference = konteks yang diambil dari Knowledge Graph (bukan teks naratif)
# Ini agar Context Precision RAGAS bisa dihitung dengan benar

REF_BANJIR = (
    '- banjir berkaitan dengan: wilayah, zona rawan banjir, sisa-sisa kotoran, arus air, langkah antisipasi\n'
    '- zona rawan banjir berkaitan dengan: bantuan perumahan/shelter, fasilitas kesehatan terdekat\n'
    '- wilayah banjir berkaitan dengan: air banjir\n'
    '- air banjir berkaitan dengan: gedung/rumah, mencuci tangan, makanan\n'
    '- saluran air banjir berkaitan dengan: dampaknya'
)

REF_LONGSOR = (
    '- Tanah Longsor berkaitan dengan: Daerah Rawan Bencana, runtuhan batuan, Fondasi, Drainase, Jangkar\n'
    '- wilayah longsor berkaitan dengan: kondisi tanah yang labil\n'
    '- Material Longsor berkaitan dengan: Material Longsor\n'
    '- Sistem Peringatan Dini Longsor berkaitan dengan: beberapa wilayah, waspada, Tanah Longsor, zona evakuasi'
)

REF_GEMPA = (
    '- gempa bumi susulan berkaitan dengan: tetap waspada\n'
    '- Gempa Bumi berkaitan dengan: Daerah Rawan Gempa Bumi, Kerusakan, Jalan, Jembatan, Bangunan\n'
    '- Informasi Gempa Bumi berkaitan dengan: Kedalaman Gempa, Potensi Tsunami, Titik Pusat Gempa Bumi, Parameter Gempa Bumi'
)

REF_ANGIN = (
    '- Angin Puting Beliung berkaitan dengan: Angin Kencang, Bangunan kokoh, Infrastruktur, Rumah\n'
    '- Angin Kencang berkaitan dengan: Bogor, Infrastruktur, Rumah, Bangunan kokoh, Angin Puting Beliung\n'
    '- angin berkaitan dengan: kebakaran hutan\n'
    '- angin kencang berkaitan dengan: penyebaran api'
)

REF_ERUPSI = (
    '- gunungapi berkaitan dengan: abu vulkanik\n'
    '- Gunung Berapi berkaitan dengan: Danau Kawah\n'
    '- Gunung Api berkaitan dengan: Kabupaten Bogor\n'
    '- Gunung Salak berkaitan dengan: Kabupaten Bogor\n'
    '- Gunung Gede berkaitan dengan: Kabupaten Bogor'
)

REF_ABU = (
    '- abu vulkanik berkaitan dengan: atap rumah atau bangunan, mengurangi terpapar\n'
    '- hujan abu lebat berkaitan dengan: Kawasan rawan\n'
    '- Hujan Abu berkaitan dengan: Erupsi Gunung Api\n'
    '- material jatuhan berupa hujan abu lebat berkaitan dengan: KRB I'
)

REF_KARHUTLA_BESAR = (
    '- kebakaran berkaitan dengan: peralatan yang menggunakan listrik\n'
    '- kebakaran hutan dan lahan berkaitan dengan: hutan, partikulat (PM10), kerusakan, perlindungan, angin\n'
    '- Posko Kebakaran berkaitan dengan: pihak terkait'
)

REF_KARHUTLA_KECIL = (
    '- karhutla berkaitan dengan: lahan, partikulat (PM10)'
)

REF_KEKERINGAN = (
    '- Kekeringan berkaitan dengan: Penyakit, Kekeringan, Air bersih, Waduk/embung, Sumur resapan/biopori'
)

REF_PERGESERAN = (
    '- pergeseran tanah berkaitan dengan: area berbahaya, evakuasi dini, memeriksa regulasi setempat, bantuan, tinggal di area yang rawan pergeseran tanah\n'
    '- Pergeseran Tanah berkaitan dengan: Infrastruktur, Jalan, Jembatan, Bangunan, Masyarakat'
)

REF_PERGESERAN_LONGSOR = (
    '- pergeseran tanah berkaitan dengan: area berbahaya, evakuasi dini, memeriksa regulasi setempat, bantuan, tinggal di area yang rawan pergeseran tanah\n'
    '- Pergeseran Tanah berkaitan dengan: Infrastruktur, Jalan, Jembatan, Bangunan, Masyarakat\n'
    '- Tanah Longsor berkaitan dengan: Daerah Rawan Bencana, runtuhan batuan, Fondasi, Drainase, Jangkar\n'
    '- wilayah longsor berkaitan dengan: kondisi tanah yang labil\n'
    '- Sistem Peringatan Dini Longsor berkaitan dengan: beberapa wilayah, waspada, Tanah Longsor, zona evakuasi'
)

REF_BENCANA_UMUM = (
    '- bencana berkaitan dengan: air banjir\n'
    '- PetaBencana.id berkaitan dengan: informasi\n'
    '- tas siaga bencana berkaitan dengan: air minum, makanan\n'
    '- Pusat Vulkanologi dan Mitigasi Bencana Geologi (PVMBG) berkaitan dengan: Geologi\n'
    '- Pra Bencana berkaitan dengan: Pergeseran Tanah\n'
    '- Mitigasi bencana berkaitan dengan: Tahap prabencana\n'
    '- Daerah Rawan Bencana berkaitan dengan: Pemukiman'
)

REF_EVAKUASI = (
    '- evakuasi berkaitan dengan: tempat tinggi, daerah yang lebih tinggi, rute evakuasi\n'
    '- skenario evakuasi berkaitan dengan: dukungan logistik\n'
    '- zona evakuasi berkaitan dengan: wilayah'
)

REF_TITIK_KUMPUL = (
    '- titik kumpul berkaitan dengan: evakuasi, zona evakuasi'
)

REF_LAHAR_DINGIN = (
    '- lahar dingin berkaitan dengan: lahar, curah hujan, Aliran Lahar'
)

REF_PUTING_BERULANG = (
    '- Angin Puting Beliung berkaitan dengan: Angin Kencang, Bangunan kokoh, Infrastruktur, Rumah\n'
    '- Angin Kencang berkaitan dengan: Bogor, Infrastruktur, Rumah, Bangunan kokoh, Angin Puting Beliung'
)

pertanyaan_dataset = [
    # ── Banjir (15 pertanyaan) ──────────────────────────────────────────────
    {'question': 'Apa yang harus dilakukan saat terjadi banjir?', 'reference': REF_BANJIR},
    {'question': 'Bagaimana cara mempersiapkan diri sebelum banjir terjadi?', 'reference': REF_BANJIR},
    {'question': 'Apa yang dilakukan pasca bencana banjir?', 'reference': REF_BANJIR},
    {'question': 'Apa itu banjir?', 'reference': REF_BANJIR},
    {'question': 'Apa penyebab banjir di Kabupaten Bogor?', 'reference': REF_BANJIR},
    {'question': 'Apa yang dimaksud dengan daerah rawan banjir?', 'reference': REF_BANJIR},
    {'question': 'Bagaimana cara mencegah banjir di lingkungan sekitar?', 'reference': REF_BANJIR},
    {'question': 'Apa itu sistem peringatan dini banjir?', 'reference': REF_BANJIR},
    {'question': 'Apa yang harus dilakukan saat banjir mulai datang?', 'reference': REF_BANJIR},
    {'question': 'Apakah boleh menerobos banjir dengan kendaraan?', 'reference': REF_BANJIR},
    {'question': 'Apa bahaya yang mengintai saat banjir?', 'reference': REF_BANJIR},
    {'question': 'Bagaimana cara menyelamatkan diri jika terjebak banjir di dalam rumah?', 'reference': REF_BANJIR},
    {'question': 'Apa yang harus dilakukan setelah banjir surut?', 'reference': REF_BANJIR},
    {'question': 'Penyakit apa yang sering muncul setelah banjir?', 'reference': REF_BANJIR},
    {'question': 'Bagaimana cara memastikan air minum aman setelah banjir?', 'reference': REF_BANJIR},

    # ── Tanah Longsor (13 pertanyaan) ──────────────────────────────────────
    {'question': 'Bagaimana cara mitigasi tanah longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apa yang harus dilakukan saat terjadi tanah longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apa yang dilakukan setelah tanah longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apa itu tanah longsor?', 'reference': REF_LONGSOR},
    {'question': 'Mengapa Kabupaten Bogor sangat rawan longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apa tanda-tanda akan terjadi tanah longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apa upaya pencegahan longsor yang bisa dilakukan masyarakat?', 'reference': REF_LONGSOR},
    {'question': 'Kapan waktu paling rawan terjadinya longsor di Bogor?', 'reference': REF_LONGSOR},
    {'question': 'Ke arah mana harus berlari saat ada longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apa yang harus dilakukan jika tertimbun longsor?', 'reference': REF_LONGSOR},
    {'question': 'Bagaimana cara menolong korban longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apa yang harus diwaspadai setelah longsor?', 'reference': REF_LONGSOR},
    {'question': 'Apakah warga boleh kembali ke rumah setelah longsor?', 'reference': REF_LONGSOR},

    # ── Gempa Bumi (13 pertanyaan) ─────────────────────────────────────────
    {'question': 'Apa langkah evakuasi saat gempa bumi?', 'reference': REF_GEMPA},
    {'question': 'Apa yang harus dilakukan setelah gempa bumi?', 'reference': REF_GEMPA},
    {'question': 'Bagaimana cara mempersiapkan diri sebelum gempa bumi?', 'reference': REF_GEMPA},
    {'question': 'Apa itu gempa bumi?', 'reference': REF_GEMPA},
    {'question': 'Apa penyebab gempa bumi?', 'reference': REF_GEMPA},
    {'question': 'Apa saja yang harus ada dalam tas darurat gempa?', 'reference': REF_GEMPA},
    {'question': 'Apakah Kabupaten Bogor rawan gempa bumi?', 'reference': REF_GEMPA},
    {'question': 'Apa yang harus dilakukan saat gempa bumi terjadi di dalam ruangan?', 'reference': REF_GEMPA},
    {'question': 'Apa yang harus dilakukan saat gempa bumi terjadi di luar ruangan?', 'reference': REF_GEMPA},
    {'question': 'Apa yang tidak boleh dilakukan saat gempa bumi?', 'reference': REF_GEMPA},
    {'question': 'Apa yang harus dilakukan setelah gempa bumi berhenti?', 'reference': REF_GEMPA},
    {'question': 'Apa itu gempa susulan?', 'reference': REF_GEMPA},
    {'question': 'Bagaimana cara membantu korban gempa yang terluka?', 'reference': REF_GEMPA},

    # ── Angin Kencang (10 pertanyaan) ──────────────────────────────────────
    {'question': 'Bagaimana cara mempersiapkan diri sebelum bencana angin kencang?', 'reference': REF_ANGIN},
    {'question': 'Apa dampak angin kencang terhadap infrastruktur?', 'reference': REF_ANGIN},
    {'question': 'Apa yang harus dilakukan saat terjadi angin kencang?', 'reference': REF_ANGIN},
    {'question': 'Apa itu angin puting beliung?', 'reference': REF_ANGIN},
    {'question': 'Kapan angin puting beliung sering terjadi di Bogor?', 'reference': REF_ANGIN},
    {'question': 'Apa tanda-tanda akan terjadi angin puting beliung?', 'reference': REF_ANGIN},
    {'question': 'Bagaimana cara mempersiapkan rumah agar tahan angin puting beliung?', 'reference': REF_ANGIN},
    {'question': 'Apa yang harus dilakukan saat terjadi angin puting beliung?', 'reference': REF_ANGIN},
    {'question': 'Apa yang harus dilakukan setelah angin puting beliung?', 'reference': REF_ANGIN},
    {'question': 'Apakah puting beliung bisa terjadi lagi di lokasi yang sama?', 'reference': REF_PUTING_BERULANG},

    # ── Erupsi Gunung Api (13 pertanyaan) ─────────────────────────────────
    {'question': 'Apa yang dilakukan pasca bencana erupsi gunung api?', 'reference': REF_ERUPSI},
    {'question': 'Apa bahaya abu vulkanik saat erupsi gunung api?', 'reference': REF_ABU},
    {'question': 'Bagaimana cara mitigasi erupsi gunung api?', 'reference': REF_ERUPSI},
    {'question': 'Gunung berapi apa saja yang ada di sekitar Kabupaten Bogor?', 'reference': REF_ERUPSI},
    {'question': 'Apa itu status gunung berapi dan apa tingkatannya?', 'reference': REF_ERUPSI},
    {'question': 'Apa tanda-tanda gunung berapi akan meletus?', 'reference': REF_ERUPSI},
    {'question': 'Bagaimana cara mempersiapkan diri jika tinggal dekat gunung berapi?', 'reference': REF_ERUPSI},
    {'question': 'Apa yang harus dilakukan saat gunung berapi meletus?', 'reference': REF_ERUPSI},
    {'question': 'Apa yang harus dilakukan saat terjadi hujan abu vulkanik?', 'reference': REF_ABU},
    {'question': 'Bagaimana cara melindungi pernapasan dari abu vulkanik?', 'reference': REF_ABU},
    {'question': 'Apakah abu vulkanik berbahaya bagi kesehatan?', 'reference': REF_ABU},
    {'question': 'Kapan warga boleh kembali ke rumah setelah gunung meletus?', 'reference': REF_ERUPSI},
    {'question': 'Apa itu lahar dingin dan kapan biasanya terjadi?', 'reference': REF_LAHAR_DINGIN},

    # ── Karhutla (8 pertanyaan) ────────────────────────────────────────────
    {'question': 'Apa yang harus dilakukan saat terjadi kebakaran hutan dan lahan?', 'reference': REF_KARHUTLA_BESAR},
    {'question': 'Bagaimana cara mencegah penyebaran api saat karhutla?', 'reference': REF_KARHUTLA_KECIL},
    {'question': 'Apa perlengkapan yang dibutuhkan saat terjadi karhutla?', 'reference': REF_KARHUTLA_KECIL},
    {'question': 'Apa penyebab utama kebakaran hutan dan lahan?', 'reference': REF_KARHUTLA_BESAR},
    {'question': 'Bagaimana cara melindungi diri dari asap kebakaran hutan?', 'reference': REF_KARHUTLA_BESAR},
    {'question': 'Apa dampak karhutla bagi kesehatan masyarakat?', 'reference': REF_KARHUTLA_KECIL},
    {'question': 'Bagaimana cara melaporkan kebakaran hutan yang ditemukan?', 'reference': REF_KARHUTLA_BESAR},
    {'question': 'Apa yang harus dilakukan setelah kebakaran hutan padam?', 'reference': REF_KARHUTLA_BESAR},

    # ── Kekeringan (10 pertanyaan) ─────────────────────────────────────────
    {'question': 'Bagaimana cara menghadapi bencana kekeringan?', 'reference': REF_KEKERINGAN},
    {'question': 'Apa sumber air yang bisa dimanfaatkan saat kekeringan?', 'reference': REF_KEKERINGAN},
    {'question': 'Bagaimana cara mendapatkan informasi saat terjadi kekeringan?', 'reference': REF_KEKERINGAN},
    {'question': 'Apa dampak bencana kekeringan bagi masyarakat?', 'reference': REF_KEKERINGAN},
    {'question': 'Bagaimana cara menghemat air saat kekeringan?', 'reference': REF_KEKERINGAN},
    {'question': 'Apa yang harus dilakukan petani saat musim kekeringan?', 'reference': REF_KEKERINGAN},
    {'question': 'Bagaimana cara mencegah kekeringan di tingkat rumah tangga?', 'reference': REF_KEKERINGAN},
    {'question': 'Apa yang dilakukan pemerintah saat terjadi bencana kekeringan?', 'reference': REF_KEKERINGAN},
    {'question': 'Apa tanda-tanda awal terjadinya kekeringan?', 'reference': REF_KEKERINGAN},
    {'question': 'Bagaimana cara memanen air hujan untuk menghadapi kekeringan?', 'reference': REF_KEKERINGAN},

    # ── Pergeseran Tanah (10 pertanyaan) ───────────────────────────────────
    {'question': 'Bagaimana cara mitigasi pergeseran tanah?', 'reference': REF_PERGESERAN},
    {'question': 'Apa dampak pergeseran tanah terhadap infrastruktur?', 'reference': REF_PERGESERAN},
    {'question': 'Apa yang harus dilakukan saat terjadi pergeseran tanah?', 'reference': REF_PERGESERAN},
    {'question': 'Apa itu pergeseran tanah?', 'reference': REF_PERGESERAN},
    {'question': 'Apa tanda-tanda terjadinya pergeseran tanah?', 'reference': REF_PERGESERAN},
    {'question': 'Apakah pergeseran tanah bisa berkembang menjadi longsor?', 'reference': REF_PERGESERAN_LONGSOR},
    {'question': 'Bagaimana cara memantau pergeseran tanah di sekitar rumah?', 'reference': REF_PERGESERAN},
    {'question': 'Apa yang dilakukan BPBD saat terjadi pergeseran tanah?', 'reference': REF_PERGESERAN},
    {'question': 'Bagaimana cara memperkuat bangunan di daerah rawan pergeseran tanah?', 'reference': REF_PERGESERAN},
    {'question': 'Apa perbedaan pergeseran tanah dan tanah longsor?', 'reference': REF_PERGESERAN_LONGSOR},

    # ── Umum/BPBD (7 pertanyaan) ───────────────────────────────────────────
    {'question': 'Apa itu mitigasi bencana?', 'reference': REF_BENCANA_UMUM},
    {'question': 'Apa peran BPBD dalam penanggulangan bencana?', 'reference': REF_BENCANA_UMUM},
    {'question': 'Apa yang dimaksud dengan kesiapsiagaan bencana?', 'reference': REF_BENCANA_UMUM},
    {'question': 'Berapa nomor darurat yang harus dihubungi saat bencana?', 'reference': REF_BENCANA_UMUM},
    {'question': 'Apa itu titik kumpul dan apa fungsinya?', 'reference': REF_TITIK_KUMPUL},
    {'question': 'Apa yang dimaksud dengan jalur evakuasi?', 'reference': REF_EVAKUASI},
    {'question': 'Apa saja tahapan pasca bencana?', 'reference': REF_BENCANA_UMUM},
]

# ─── Keywords ──────────────────────────────────────────────────────────────────
KEYWORDS_SPESIFIK = {
    'angin':      'Angin_Kencang.pdf',
    'banjir':     'Banjir.pdf',
    'gempa':      'Gempa_Bumi.pdf',
    'longsor':    'Tanah_Longsor.pdf',
    'erupsi':     'Erupsi_Gunung_Api.pdf',
    'gunung':     'Erupsi_Gunung_Api.pdf',
    'vulkanik':   'Erupsi_Gunung_Api.pdf',
    'abu':        'Erupsi_Gunung_Api.pdf',
    'lava':       'Erupsi_Gunung_Api.pdf',
    'karhutla':   'Karhutla.pdf',
    'kebakaran':  'Karhutla.pdf',
    'kekeringan': 'Kekeringan.pdf',
    'pergeseran': 'Pergeseran_Tanah.pdf',
}
KEYWORDS_UMUM = ['mitigasi', 'bencana', 'darurat', 'evakuasi']

# ─── Fungsi graph traversal ────────────────────────────────────────────────────
def cari_konteks_graph(pertanyaan):
    pertanyaan_bersih = re.sub(r'[^\w\s]', ' ', pertanyaan.lower())
    words = pertanyaan_bersih.split()
    keywords_spesifik = [k for k in words if k in KEYWORDS_SPESIFIK]
    keywords_umum     = [k for k in words if k in KEYWORDS_UMUM]
    keywords          = keywords_spesifik if keywords_spesifik else keywords_umum
    if not keywords:
        semua = list(KEYWORDS_SPESIFIK.keys()) + KEYWORDS_UMUM
        keywords = [w for w in words if any(k in w for k in semua)]
        if not keywords:
            return 'Tidak ada konteks ditemukan.'
    kondisi = ' OR '.join([f"toLower(e.nama) CONTAINS '{k}'" for k in keywords])
    hasil_relasi = graph.query(f"""
        MATCH (e:Entitas)
        WHERE {kondisi}
        OPTIONAL MATCH (e)-[r]->(target:Entitas)
        RETURN e.nama AS entitas,
               collect(DISTINCT type(r) + ' -> ' + target.nama) AS relasi_keluar
    """)
    lines = []
    for item in hasil_relasi:
        entitas = item['entitas']
        keluar  = [r for r in item['relasi_keluar'] if r and '-> None' not in r]
        if keluar:
            targets = [r.split('-> ')[1] for r in keluar if '-> ' in r]
            if targets:
                lines.append(f'- {entitas} berkaitan dengan: {", ".join(targets[:5])}')
    return '\n'.join(lines) if lines else 'Tidak ada konteks ditemukan.'

# ─── Fungsi generate jawaban ───────────────────────────────────────────────────
def dapatkan_jawaban(pertanyaan):
    konteks = cari_konteks_graph(pertanyaan)
    prompt  = f"""
Kamu adalah asisten mitigasi bencana BPBD Kabupaten Bogor.
Informasi dari basis data knowledge graph:
---
{konteks}
---
Pertanyaan: {pertanyaan}

ATURAN KETAT:
- Jawab HANYA berdasarkan informasi dari basis data di atas
- DILARANG menambahkan informasi yang tidak ada dalam basis data
- Jika informasi tidak tersedia, tulis "Tidak tersedia dalam basis data"
- Jawab singkat, maksimal 3 poin per fase
- Setiap poin maksimal 1 kalimat pendek
- Format: Pra Bencana / Saat Bencana / Pasca Bencana
"""
    return llm_ollama.invoke(prompt), konteks

# ─── Main ──────────────────────────────────────────────────────────────────────
print('🔄 Mengumpulkan jawaban chatbot...')
rows = []

for i, item in enumerate(pertanyaan_dataset, 1):
    try:
        print(f'  [{i:03d}/{len(pertanyaan_dataset)}] {item["question"]}')
        jawaban, konteks = dapatkan_jawaban(item['question'])
        rows.append({
            'question':  item['question'],
            'answer':    jawaban,
            'context':   konteks,
            'reference': item['reference'],
        })
        print(f'         ✅ Selesai')
    except Exception as e:
        print(f'         ❌ Error: {e} — dilewati')

with open('jawaban_dataset.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['question', 'answer', 'context', 'reference'])
    writer.writeheader()
    writer.writerows(rows)

end = time.time()
print(f'\n⏱️  Waktu proses : {end - start:.2f} detik ({(end-start)/60:.1f} menit)')
print(f'💾 Disimpan ke  : jawaban_dataset.csv')
print(f'📊 Total        : {len(rows)} pertanyaan')