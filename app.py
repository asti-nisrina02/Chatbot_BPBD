from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_ollama import OllamaLLM
import os
import re

load_dotenv()

app = Flask(__name__)

graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD"),
    database=os.getenv("NEO4J_DATABASE")
)
llm = OllamaLLM(model="gemma3:1b")

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
    'karhutla':   'Karhutla.pdf',
    'kebakaran':  'Karhutla.pdf',
    'kekeringan': 'Kekeringan.pdf',
    'pergeseran': 'Pergeseran_Tanah.pdf',
}

KEYWORDS_UMUM = ['mitigasi', 'bencana', 'darurat', 'evakuasi']

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


# ─── Graph traversal ───────────────────────────────────────────────────────────

def cari_konteks_graph(pertanyaan: str):
    spesifik, umum, _ = ekstrak_keywords(pertanyaan)
    keywords = spesifik if spesifik else umum

    if not keywords:
        semua = list(KEYWORDS_SPESIFIK.keys()) + KEYWORDS_UMUM
        bersih = re.sub(r'[^\w\s]', ' ', pertanyaan.lower())
        keywords = [w for w in bersih.split() if any(k in w for k in semua)]
        if not keywords:
            return [], []

    kondisi_entitas = " OR ".join([f"toLower(e.nama) CONTAINS '{k}'" for k in keywords])

    if spesifik:
        dokumen_target  = [KEYWORDS_SPESIFIK[k] for k in spesifik]
        kondisi_dokumen = " OR ".join([f"d.nama = '{d}'" for d in dokumen_target])
    else:
        kondisi_dokumen = " OR ".join([f"toLower(e.nama) CONTAINS '{k}'" for k in keywords])

    query_relasi = f"""
    MATCH (e:Entitas)
    WHERE {kondisi_entitas}
    OPTIONAL MATCH (e)-[r]->(target:Entitas)
    OPTIONAL MATCH (source:Entitas)-[r2]->(e)
    RETURN 
        e.nama AS entitas,
        collect(DISTINCT type(r) + ' -> ' + target.nama) AS relasi_keluar,
        collect(DISTINCT source.nama + ' -> ' + type(r2)) AS relasi_masuk
    """

    query_dokumen = f"""
    MATCH (d:Dokumen)-[:MEMBAHAS]->(e:Entitas)
    WHERE {kondisi_dokumen}
    RETURN DISTINCT d.nama AS sumber, d.tipe AS tipe
    """

    return graph.query(query_relasi), graph.query(query_dokumen)


def format_konteks(hasil_relasi, hasil_dokumen):
    lines = []
    for item in hasil_relasi:
        entitas = item['entitas']
        keluar  = [r for r in item['relasi_keluar'] if r and '-> None' not in r]
        masuk   = [r for r in item['relasi_masuk']  if r and 'None ->' not in r]

        if keluar:
            targets = [r.split('-> ')[1] for r in keluar if '-> ' in r]
            if targets:
                lines.append(f"• {entitas} berkaitan dengan: {', '.join(targets[:5])}")
        if masuk:
            sources = [r.split(' ->')[0] for r in masuk if ' ->' in r]
            if sources:
                lines.append(f"• {entitas} terkait dengan: {', '.join(sources[:3])}")

    return "\n".join(lines) if lines else ""


# ─── Fungsi utama chatbot ──────────────────────────────────────────────────────

def tanya_chatbot(pertanyaan: str):
    kata = pertanyaan.lower().strip()

    # Sapaan / basa-basi (hanya jika tidak ada keyword bencana)
    ada_keyword = any(k in kata for k in list(KEYWORDS_SPESIFIK.keys()) + KEYWORDS_UMUM)
    if not ada_keyword:
        if any(s in kata for s in ['halo', 'hi', 'hai', 'haloo', 'hallo', 'hey']):
            return ("Halo! Selamat datang di layanan chatbot mitigasi bencana "
                    "BPBD Kabupaten Bogor. Ada yang bisa saya bantu? 🙏", "")
        if any(s in kata for s in ['makasih', 'terima kasih', 'thanks', 'ok', 'selesai', 'cukup']):
            return ("Sama-sama! Jika ada pertanyaan lain seputar mitigasi bencana, "
                    "jangan ragu untuk bertanya ya. 🙏", "")

    # Ambil konteks dari graph
    hasil_relasi, hasil_dokumen = cari_konteks_graph(pertanyaan)

    if not hasil_relasi and not hasil_dokumen:
        return (
            "Maaf, saya tidak menemukan informasi terkait pertanyaan Anda "
            "dalam dokumen yang tersedia. Silakan hubungi BPBD Kabupaten Bogor "
            "untuk informasi lebih lanjut.",
            ""
        )

    konteks = format_konteks(hasil_relasi, hasil_dokumen)
    sumber_file = (", ".join([d['sumber'] for d in hasil_dokumen])
                   if hasil_dokumen else "Basis data mitigasi BPBD Kab. Bogor")

    # Deteksi fase dari pertanyaan
    _, _, fase = ekstrak_keywords(pertanyaan)

    if fase:
        instruksi_fase = f"Jawab HANYA untuk fase {fase}. Maksimal 5 poin singkat."
    else:
        instruksi_fase = """Jawab singkat dan jelas. Bagi per fase:
**Pra Bencana:**
**Saat Bencana:**
**Pasca Bencana:**

Setiap fase maksimal 3 poin, penomoran mulai dari 1. Jangan tulis jumlah poin dalam judul fase."""

    prompt = f"""Kamu adalah asisten mitigasi bencana BPBD Kabupaten Bogor yang ramah dan mudah dipahami masyarakat awam.
Gunakan bahasa yang sederhana, hindari istilah teknis berlebihan.
Jawab HANYA berdasarkan informasi di bawah ini.

Informasi dari basis data mitigasi:
---
{konteks}
---

Pertanyaan: {pertanyaan}

{instruksi_fase}
"""

    respon = llm.invoke(prompt)
    return respon, sumber_file


# ─── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data       = request.get_json()
    pertanyaan = data.get("pertanyaan", "")
    if not pertanyaan.strip():
        return jsonify({"jawaban": "", "sumber": ""})
    jawaban, sumber = tanya_chatbot(pertanyaan)
    return jsonify({"jawaban": jawaban, "sumber": sumber})


if __name__ == "__main__":
    app.run(debug=True)