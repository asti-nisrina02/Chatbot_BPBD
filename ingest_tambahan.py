import os
import fitz
import json
import time  # ← tambah ini
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_ollama import OllamaLLM


load_dotenv()

graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD"),
    database=os.getenv("NEO4J_DATABASE")
)

llm = OllamaLLM(model="gemma3:4b")
CHUNK_SIZE = 1500

def chunk_text(text, chunk_size=CHUNK_SIZE):
    words = text.split()
    chunks = []
    current = []
    current_len = 0
    for word in words:
        current_len += len(word) + 1
        current.append(word)
        if current_len >= chunk_size:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
    if current:
        chunks.append(" ".join(current))
    return chunks

def ekstrak_entitas_relasi(teks, nama_file, chunk_index=0):
    prompt = f"""
Dari teks berikut tentang mitigasi bencana, ekstrak entitas dan relasi penting.
Untuk setiap entitas, sertakan juga deskripsi singkat (1 kalimat, berdasarkan teks 
yang diberikan saja, JANGAN mengarang) yang menjelaskan apa itu entitas tersebut 
dalam konteks teks ini. Jika teks tidak menjelaskan entitas itu secara langsung, 
kosongkan deskripsi ("").

Jawab HANYA dalam format JSON seperti ini, tidak ada teks lain:
{{
  "entitas": [
    {{"nama": "entitas1", "deskripsi": "penjelasan singkat entitas1 sesuai teks", "fase": "Pra Bencana"}},
    {{"nama": "entitas2", "deskripsi": "", "fase": ""}}
  ],
  "relasi": [
    {{"dari": "entitas1", "relasi": "NAMA_RELASI", "ke": "entitas2"}}
  ]
}}

Field "fase" HARUS diisi salah satu dari 4 pilihan berikut, berdasarkan konteks
kalimat tempat entitas itu disebut:
- "Pra Bencana"  → kalau entitas itu soal persiapan/pencegahan SEBELUM bencana terjadi
- "Saat Bencana" → kalau entitas itu soal tindakan SELAMA bencana berlangsung
- "Pasca Bencana" → kalau entitas itu soal pemulihan SETELAH bencana selesai
- ""             → kalau entitas itu BUKAN tindakan spesifik-fase (misal definisi
                     umum, nama tempat, nama lembaga, penyebab bencana, istilah teknis)
JANGAN menebak-nebak kalau teks tidak menyebutkan konteks fase secara jelas — 
lebih baik kosongkan ("") daripada salah.

Contoh relasi yang relevan: MEMICU, MENCEGAH, TERJADI_DI, MENGHARUSKAN, 
MELIBATKAN, DIKELOLA_OLEH, BERDAMPAK_PADA, MEMBUTUHKAN, BERKAITAN_DENGAN

Teks:
{teks}
"""
    hasil = llm.invoke(prompt)
    try:
        start = hasil.find('{')
        end = hasil.rfind('}') + 1
        json_str = hasil[start:end]
        return json.loads(json_str)
    except:
        print(f"Gagal parse JSON untuk {nama_file} chunk {chunk_index}")
        return {"entitas": [], "relasi": []}

FASE_VALID = {"Pra Bencana", "Saat Bencana", "Pasca Bencana"}

def gabung_hasil(list_hasil):
    """Gabungkan hasil ekstraksi dari semua chunk, hapus duplikat.
    Entitas berupa dict {"nama", "deskripsi", "fase"}. Kalau ada beberapa chunk
    menyebut entitas yang sama, deskripsi/fase non-kosong PERTAMA yang dipakai."""
    entitas_map = {}  # nama -> {"deskripsi": ..., "fase": ...}
    semua_relasi = []
    relasi_set = set()

    for hasil in list_hasil:
        for e in hasil.get("entitas", []):
            if isinstance(e, str):
                nama, deskripsi, fase = e.strip(), "", ""
            elif isinstance(e, dict):
                nama = str(e.get("nama", "")).strip()
                deskripsi = str(e.get("deskripsi", "") or "").strip()
                fase = str(e.get("fase", "") or "").strip()
                if fase not in FASE_VALID:
                    fase = ""
            else:
                continue

            if not nama:
                continue

            if nama not in entitas_map:
                entitas_map[nama] = {"deskripsi": deskripsi, "fase": fase}
            else:
                if not entitas_map[nama]["deskripsi"] and deskripsi:
                    entitas_map[nama]["deskripsi"] = deskripsi
                if not entitas_map[nama]["fase"] and fase:
                    entitas_map[nama]["fase"] = fase

        for r in hasil.get("relasi", []):
            dari   = r.get("dari")
            relasi = r.get("relasi")
            ke     = r.get("ke")
            if not dari or not relasi or not ke:
                continue
            key = (str(dari).strip(), str(relasi).strip(), str(ke).strip())
            if key not in relasi_set:
                relasi_set.add(key)
                semua_relasi.append({
                    "dari": str(dari).strip(),
                    "relasi": str(relasi).strip(),
                    "ke": str(ke).strip()
                })

    semua_entitas = [
        {"nama": n, "deskripsi": v["deskripsi"], "fase": v["fase"]}
        for n, v in entitas_map.items()
    ]
    return {"entitas": semua_entitas, "relasi": semua_relasi}

def normalize_nama(s):
    """Normalisasi nama entitas jadi lowercase + strip whitespace,
    biar 'Banjir', 'banjir', 'BANJIR' selalu jadi satu node yang sama."""
    return s.strip().lower() if s else s


def simpan_ke_graph(data, nama_file, tipe):
    graph.query("""
        MERGE (d:Dokumen {nama: $nama})
        SET d.tipe = $tipe, d.status = 'Verified'
    """, params={"nama": nama_file, "tipe": tipe})

    for entitas in data.get("entitas", []):
        nama = entitas.get("nama", "") if isinstance(entitas, dict) else entitas
        deskripsi = entitas.get("deskripsi", "") if isinstance(entitas, dict) else ""
        fase = entitas.get("fase", "") if isinstance(entitas, dict) else ""
        nama = normalize_nama(nama)
        if not nama:
            continue
        graph.query("""
            MERGE (e:Entitas {nama: $nama})
            ON CREATE SET e.deskripsi = $deskripsi, e.fase = $fase
            ON MATCH SET
                e.deskripsi = CASE WHEN e.deskripsi IS NULL OR e.deskripsi = '' THEN $deskripsi ELSE e.deskripsi END,
                e.fase = CASE WHEN e.fase IS NULL OR e.fase = '' THEN $fase ELSE e.fase END
            WITH e
            MATCH (d:Dokumen {nama: $dokumen})
            MERGE (d)-[:MEMBAHAS]->(e)
        """, params={"nama": nama, "deskripsi": deskripsi, "fase": fase, "dokumen": nama_file})

    for rel in data.get("relasi", []):
        if not rel.get("dari") or not rel.get("ke") or not rel.get("relasi"):
            continue
        nama_relasi = rel["relasi"].upper().replace(" ", "_")
        dari = normalize_nama(rel["dari"])
        ke   = normalize_nama(rel["ke"])
        try:
            graph.query("""
                MERGE (a:Entitas {nama: $dari})
                MERGE (b:Entitas {nama: $ke})
                WITH a, b
                CALL apoc.merge.relationship(a, $relasi, {}, {}, b, {})
                YIELD rel
                RETURN rel
            """, params={
                "dari": dari,
                "ke": ke,
                "relasi": nama_relasi
            })
        except Exception as e:
            print(f"Gagal simpan relasi: {dari} -[{nama_relasi}]-> {ke}: {e}")

def ingest_pdf_baru(file_path, file_name):
    """Ingest 1 file PDF baru TANPA menghapus data lama"""
    try:
        start_file = time.time()  # ← timer per file mulai
        print(f"\nMemproses {file_name}...")
        doc = fitz.open(file_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()

        tipe = "Panduan Umum"
        chunks = chunk_text(full_text)
        print(f"Dibagi menjadi {len(chunks)} chunk...")

        semua_hasil = []
        for i, chunk in enumerate(chunks):
            print(f"Ekstraksi chunk {i+1}/{len(chunks)}...")
            hasil = ekstrak_entitas_relasi(chunk, file_name, i)
            semua_hasil.append(hasil)

        data_final = gabung_hasil(semua_hasil)
        print(f"Menyimpan ke Neo4j...")
        simpan_ke_graph(data_final, file_name, tipe)

        end_file = time.time()  # ← timer per file selesai
        durasi_file = end_file - start_file
        print(f"Selesai! ({len(data_final['entitas'])} entitas unik, {len(data_final['relasi'])} relasi unik)")
        print(f"⏱️ Waktu ingest {file_name}: {durasi_file:.1f} detik ({durasi_file/60:.1f} menit)")

        return durasi_file  # ← kembalikan durasi untuk ditotal

    except Exception as e:
        print(f"Gagal memproses {file_name}: {e}")
        return 0.0

if __name__ == "__main__":
    # ⚠️ TIDAK ADA penghapusan data lama!
    folder_baru = "data/data_baru"
    
    files = [f for f in os.listdir(folder_baru) if f.endswith('.pdf')]
    if not files:
        print("Tidak ada file PDF di folder ./data_baru")
    else:
        print(f"Memproses {len(files)} file PDF baru...")

        start_total = time.time()  # ← timer total mulai

        durasi_per_file = {}
        for f in files:
            durasi = ingest_pdf_baru(os.path.join(folder_baru, f), f)
            durasi_per_file[f] = durasi

        end_total = time.time()  # ← timer total selesai
        total_detik = end_total - start_total
        total_menit = total_detik / 60

        print("\n" + "=" * 50)
        print("📊 RINGKASAN WAKTU INGEST TAMBAHAN")
        print("=" * 50)
        for fname, dur in durasi_per_file.items():
            print(f"  {fname:<35} {dur:>6.1f} detik ({dur/60:.1f} menit)")
        print("-" * 50)
        print(f"  {'TOTAL (3 dok tambahan)':<35} {total_detik:>6.1f} detik ({total_menit:.1f} menit)")
        print("=" * 50)
        print("\n✅ Selesai! Cek Neo4j untuk lihat entitas baru.")