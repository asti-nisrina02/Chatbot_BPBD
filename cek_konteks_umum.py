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
    'angin': 'Angin_Kencang.pdf', 'puting': 'Angin_Kencang.pdf',
    'banjir': 'Banjir.pdf', 'gempa': 'Gempa_Bumi.pdf',
    'longsor': 'Tanah_Longsor.pdf', 'erupsi': 'Erupsi_Gunung_Api.pdf',
    'gunung': 'Erupsi_Gunung_Api.pdf', 'vulkanik': 'Erupsi_Gunung_Api.pdf',
    'abu': 'Erupsi_Gunung_Api.pdf', 'lava': 'Erupsi_Gunung_Api.pdf',
    'karhutla': 'Karhutla.pdf', 'kebakaran': 'Karhutla.pdf',
    'kekeringan': 'Kekeringan.pdf', 'pergeseran': 'Pergeseran_Tanah.pdf',
}
KEYWORDS_UMUM = ['mitigasi', 'bencana', 'darurat', 'evakuasi', 'kumpul', 'kesiapsiagaan']

def cari_konteks_graph(pertanyaan):
    pertanyaan_bersih = re.sub(r'[^\w\s]', ' ', pertanyaan.lower())
    words = pertanyaan_bersih.split()
    print(f"DEBUG - words: {words}")  # tambahkan ini
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
                lines.append(f'- {entitas} berkaitan dengan: {", ".join(targets[:5])}')
    return '\n'.join(lines) if lines else 'Tidak ada konteks ditemukan.'

pertanyaan_test = [
    "Apa itu mitigasi bencana?",
    "Apa peran BPBD dalam penanggulangan bencana?",
    "Apa yang dimaksud dengan kesiapsiagaan bencana?",
    "Berapa nomor darurat yang harus dihubungi saat bencana?",
    "Apa itu titik kumpul dan apa fungsinya?",
    "Apa yang dimaksud dengan jalur evakuasi?",
    "Apa saja tahapan pasca bencana?",
]

for p in pertanyaan_test:
    konteks = cari_konteks_graph(p)
    print(f"\n{'='*60}")
    print(f"Q: {p}")
    print(f"Konteks:\n{konteks}")