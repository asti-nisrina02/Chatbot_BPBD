import os
import fitz
import json
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
folder_path = "./data"
CHUNK_SIZE = 1500  # karakter per chunk

def chunk_text(text, chunk_size=CHUNK_SIZE):
    """Bagi teks jadi potongan-potongan kecil"""
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
    """Ekstrak entitas dan relasi dari satu chunk teks"""
    prompt = f"""
Dari teks berikut tentang mitigasi bencana, ekstrak entitas dan relasi penting.
Jawab HANYA dalam format JSON seperti ini, tidak ada teks lain:
{{
  "entitas": ["entitas1", "entitas2", "entitas3"],
  "relasi": [
    {{"dari": "entitas1", "relasi": "NAMA_RELASI", "ke": "entitas2"}},
    {{"dari": "entitas2", "relasi": "NAMA_RELASI", "ke": "entitas3"}}
  ]
}}

Contoh relasi yang relevan untuk mitigasi: MEMICU, MENCEGAH, TERJADI_DI, 
MENGHARUSKAN, MELIBATKAN, DIKELOLA_OLEH, BERDAMPAK_PADA, MEMBUTUHKAN

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
        print(f" Gagal parse JSON untuk {nama_file} chunk {chunk_index}")
        return {"entitas": [], "relasi": []}

def gabung_hasil(list_hasil):
    """Gabungkan hasil ekstraksi dari semua chunk, hapus duplikat"""
    semua_entitas = set()
    semua_relasi = []
    relasi_set = set()
    
    for hasil in list_hasil:
        for e in hasil.get("entitas", []):
            semua_entitas.add(e.strip())
        
        for r in hasil.get("relasi", []):
            key = (r["dari"].strip(), r["relasi"].strip(), r["ke"].strip())
            if key not in relasi_set:
                relasi_set.add(key)
                semua_relasi.append({
                    "dari": r["dari"].strip(),
                    "relasi": r["relasi"].strip(),
                    "ke": r["ke"].strip()
                })
    
    return {"entitas": list(semua_entitas), "relasi": semua_relasi}

def simpan_ke_graph(data, nama_file, tipe):
    """Simpan entitas dan relasi ke Neo4j"""
    graph.query("""
        MERGE (d:Dokumen {nama: $nama})
        SET d.tipe = $tipe, d.status = 'Verified'
    """, params={"nama": nama_file, "tipe": tipe})
    
    for entitas in data.get("entitas", []):
        if not entitas:
            continue
        graph.query("""
            MERGE (e:Entitas {nama: $nama})
            WITH e
            MATCH (d:Dokumen {nama: $dokumen})
            MERGE (d)-[:MEMILIKI_ENTITAS]->(e)
        """, params={"nama": entitas, "dokumen": nama_file})
    
    for rel in data.get("relasi", []):
        if not rel.get("dari") or not rel.get("ke") or not rel.get("relasi"):
            continue
        nama_relasi = rel["relasi"].upper().replace(" ", "_")
        try:
            graph.query("""
                MERGE (a:Entitas {nama: $dari})
                MERGE (b:Entitas {nama: $ke})
                WITH a, b
                CALL apoc.merge.relationship(a, $relasi, {}, {}, b, {})
                YIELD rel
                RETURN rel
            """, params={
                "dari": rel["dari"],
                "ke": rel["ke"],
                "relasi": nama_relasi
            })
        except Exception as e:
            print(f" Gagal simpan relasi: {rel['dari']} -[{nama_relasi}]-> {rel['ke']}: {e}")

def ingest_pdf(file_path, file_name):
    try:
        print(f"\nMemproses {file_name}...")
        doc = fitz.open(file_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        
        # Tentukan tipe dokumen
        tipe = "Produk Hukum" if "produk" in file_name.lower() else "Panduan Mitigasi"
        
        # Chunking teks
        chunks = chunk_text(full_text)
        print(f" Dibagi menjadi {len(chunks)} chunk...")
        
        # Ekstrak dari setiap chunk
        semua_hasil = []
        for i, chunk in enumerate(chunks):
            print(f" Ekstraksi chunk {i+1}/{len(chunks)}...")
            hasil = ekstrak_entitas_relasi(chunk, file_name, i)
            semua_hasil.append(hasil)
        
        # Gabungkan & deduplikasi
        data_final = gabung_hasil(semua_hasil)
        
        print(f" Menyimpan ke Neo4j...")
        simpan_ke_graph(data_final, file_name, tipe)
        
        print(f" Selesai! ({len(data_final['entitas'])} entitas unik, {len(data_final['relasi'])} relasi unik)")
    
    except Exception as e:
        print(f" Gagal memproses {file_name}: {e}")

if __name__ == "__main__":
    print("Membersihkan data lama di Neo4j...")
    graph.query("MATCH (n) DETACH DELETE n")
    print("Data lama dihapus!\n")
    
    files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
    if not files:
        print("Tidak ada file PDF di folder /data.")
    else:
        print(f"Memproses {len(files)} file PDF...")
        for f in files:
            ingest_pdf(os.path.join(folder_path, f), f)
        print("\n Selesai! Cek Neo4j untuk lihat graph-nya.")