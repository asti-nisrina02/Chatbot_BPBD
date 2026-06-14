import os
import re
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph

load_dotenv(dotenv_path='.env', override=True)

graph = Neo4jGraph(
    url=os.getenv('NEO4J_URI'),
    username=os.getenv('NEO4J_USERNAME'),
    password=os.getenv('NEO4J_PASSWORD'),
    database=os.getenv('NEO4J_DATABASE')
)

KEYWORDS_SPESIFIK = {
    'angin': 'Angin_Kencang.pdf', 'banjir': 'Banjir.pdf',
    'gempa': 'Gempa_Bumi.pdf', 'longsor': 'Tanah_Longsor.pdf',
    'erupsi': 'Erupsi_Gunung_Api.pdf', 'gunung': 'Erupsi_Gunung_Api.pdf',
    'vulkanik': 'Erupsi_Gunung_Api.pdf', 'abu': 'Erupsi_Gunung_Api.pdf',
    'lava': 'Erupsi_Gunung_Api.pdf', 'karhutla': 'Karhutla.pdf',
    'kebakaran': 'Karhutla.pdf', 'kekeringan': 'Kekeringan.pdf',
    'pergeseran': 'Pergeseran_Tanah.pdf',
}
KEYWORDS_UMUM = ['mitigasi', 'bencana', 'darurat', 'evakuasi']

def cari_konteks_graph(pertanyaan):
    pertanyaan_bersih = re.sub(r'[^\w\s]', ' ', pertanyaan.lower())
    words = pertanyaan_bersih.split()
    keywords_spesifik = [k for k in words if k in KEYWORDS_SPESIFIK]
    keywords_umum = [k for k in words if k in KEYWORDS_UMUM]
    keywords = keywords_spesifik if keywords_spesifik else keywords_umum
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
        keluar = [r for r in item['relasi_keluar'] if r and '-> None' not in r]
        if keluar:
            targets = [r.split('-> ')[1] for r in keluar if '-> ' in r]
            if targets:
                lines.append(f'• {entitas} berkaitan dengan: {", ".join(targets[:5])}')
    return '\n'.join(lines) if lines else 'Tidak ada konteks ditemukan.'

# Ambil semua pertanyaan dari kumpul_jawaban.py
pertanyaan_list = [
    "Apa yang harus dilakukan saat terjadi banjir?",
    "Bagaimana cara mempersiapkan diri sebelum banjir terjadi?",
    "Apa yang dilakukan pasca bencana banjir?",
    "Apa itu banjir?",
    "Apa penyebab banjir di Kabupaten Bogor?",
    "Apa yang dimaksud dengan daerah rawan banjir?",
    "Bagaimana cara mencegah banjir di lingkungan sekitar?",
    "Apa itu sistem peringatan dini banjir?",
    "Apa yang harus dilakukan saat banjir mulai datang?",
    "Apakah boleh menerobos banjir dengan kendaraan?",
    "Apa bahaya yang mengintai saat banjir?",
    "Bagaimana cara menyelamatkan diri jika terjebak banjir di dalam rumah?",
    "Apa yang harus dilakukan setelah banjir surut?",
    "Penyakit apa yang sering muncul setelah banjir?",
    "Bagaimana cara memastikan air minum aman setelah banjir?",
    "Bagaimana cara mitigasi tanah longsor?",
    "Apa yang harus dilakukan saat terjadi tanah longsor?",
    "Apa yang dilakukan setelah tanah longsor?",
    "Apa itu tanah longsor?",
    "Mengapa Kabupaten Bogor sangat rawan longsor?",
    "Apa tanda-tanda akan terjadi tanah longsor?",
    "Apa upaya pencegahan longsor yang bisa dilakukan masyarakat?",
    "Kapan waktu paling rawan terjadinya longsor di Bogor?",
    "Ke arah mana harus berlari saat ada longsor?",
    "Apa yang harus dilakukan jika tertimbun longsor?",
    "Bagaimana cara menolong korban longsor?",
    "Apa yang harus diwaspadai setelah longsor?",
    "Apakah warga boleh kembali ke rumah setelah longsor?",
    "Apa langkah evakuasi saat gempa bumi?",
    "Apa yang harus dilakukan setelah gempa bumi?",
    "Bagaimana cara mempersiapkan diri sebelum gempa bumi?",
    "Apa itu gempa bumi?",
    "Apa penyebab gempa bumi?",
    "Apa saja yang harus ada dalam tas darurat gempa?",
    "Apakah Kabupaten Bogor rawan gempa bumi?",
    "Apa yang harus dilakukan saat gempa bumi terjadi di dalam ruangan?",
    "Apa yang harus dilakukan saat gempa bumi terjadi di luar ruangan?",
    "Apa yang tidak boleh dilakukan saat gempa bumi?",
    "Apa yang harus dilakukan setelah gempa bumi berhenti?",
    "Apa itu gempa susulan?",
    "Bagaimana cara membantu korban gempa yang terluka?",
    "Bagaimana cara mempersiapkan diri sebelum bencana angin kencang?",
    "Apa dampak angin kencang terhadap infrastruktur?",
    "Apa yang harus dilakukan saat terjadi angin kencang?",
    "Apa itu angin puting beliung?",
    "Kapan angin puting beliung sering terjadi di Bogor?",
    "Apa tanda-tanda akan terjadi angin puting beliung?",
    "Bagaimana cara mempersiapkan rumah agar tahan angin puting beliung?",
    "Apa yang harus dilakukan saat terjadi angin puting beliung?",
    "Apa yang harus dilakukan setelah angin puting beliung?",
    "Apakah puting beliung bisa terjadi lagi di lokasi yang sama?",
    "Apa yang dilakukan pasca bencana erupsi gunung api?",
    "Apa bahaya abu vulkanik saat erupsi gunung api?",
    "Bagaimana cara mitigasi erupsi gunung api?",
    "Gunung berapi apa saja yang ada di sekitar Kabupaten Bogor?",
    "Apa itu status gunung berapi dan apa tingkatannya?",
    "Apa tanda-tanda gunung berapi akan meletus?",
    "Bagaimana cara mempersiapkan diri jika tinggal dekat gunung berapi?",
    "Apa yang harus dilakukan saat gunung berapi meletus?",
    "Apa yang harus dilakukan saat terjadi hujan abu vulkanik?",
    "Bagaimana cara melindungi pernapasan dari abu vulkanik?",
    "Apakah abu vulkanik berbahaya bagi kesehatan?",
    "Kapan warga boleh kembali ke rumah setelah gunung meletus?",
    "Apa itu lahar dingin dan kapan biasanya terjadi?",
    "Apa yang harus dilakukan saat terjadi kebakaran hutan dan lahan?",
    "Bagaimana cara mencegah penyebaran api saat karhutla?",
    "Apa perlengkapan yang dibutuhkan saat terjadi karhutla?",
    "Apa penyebab utama kebakaran hutan dan lahan?",
    "Bagaimana cara melindungi diri dari asap kebakaran hutan?",
    "Apa dampak karhutla bagi kesehatan masyarakat?",
    "Bagaimana cara melaporkan kebakaran hutan yang ditemukan?",
    "Apa yang harus dilakukan setelah kebakaran hutan padam?",
    "Bagaimana cara menghadapi bencana kekeringan?",
    "Apa sumber air yang bisa dimanfaatkan saat kekeringan?",
    "Bagaimana cara mendapatkan informasi saat terjadi kekeringan?",
    "Apa dampak bencana kekeringan bagi masyarakat?",
    "Bagaimana cara menghemat air saat kekeringan?",
    "Apa yang harus dilakukan petani saat musim kekeringan?",
    "Bagaimana cara mencegah kekeringan di tingkat rumah tangga?",
    "Apa yang dilakukan pemerintah saat terjadi bencana kekeringan?",
    "Apa tanda-tanda awal terjadinya kekeringan?",
    "Bagaimana cara memanen air hujan untuk menghadapi kekeringan?",
    "Bagaimana cara mitigasi pergeseran tanah?",
    "Apa dampak pergeseran tanah terhadap infrastruktur?",
    "Apa yang harus dilakukan saat terjadi pergeseran tanah?",
    "Apa itu pergeseran tanah?",
    "Apa tanda-tanda terjadinya pergeseran tanah?",
    "Apakah pergeseran tanah bisa berkembang menjadi longsor?",
    "Bagaimana cara memantau pergeseran tanah di sekitar rumah?",
    "Apa yang dilakukan BPBD saat terjadi pergeseran tanah?",
    "Bagaimana cara memperkuat bangunan di daerah rawan pergeseran tanah?",
    "Apa perbedaan pergeseran tanah dan tanah longsor?",
    "Apa itu mitigasi bencana?",
    "Apa peran BPBD dalam penanggulangan bencana?",
    "Apa yang dimaksud dengan kesiapsiagaan bencana?",
    "Berapa nomor darurat yang harus dihubungi saat bencana?",
    "Apa itu titik kumpul dan apa fungsinya?",
    "Apa yang dimaksud dengan jalur evakuasi?",
    "Apa saja tahapan pasca bencana?",
]

print("# Copy hasil ini ke pertanyaan_dataset sebagai reference\n")
for p in pertanyaan_list:
    konteks = cari_konteks_graph(p)
    print(f"# Q: {p}")
    print(f"# Reference: {repr(konteks)}")
    print()