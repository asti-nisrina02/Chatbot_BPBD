from dotenv import load_dotenv
load_dotenv()
import os
from langchain_community.llms import Ollama
from langchain_neo4j import Neo4jGraph
import os

# 1. Konfigurasi Database & Model
URL = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PWD = os.getenv("NEO4J_PASSWORD")
MODEL_NAME = "gemma3:1b"

print(f"🔄 Menghubungkan ke Neo4j dan memuat model {MODEL_NAME}...")

try:
    graph = Neo4jGraph(url=URL, username=USER, password=PWD, database=os.getenv("NEO4J_DATABASE"))
    llm = Ollama(model=MODEL_NAME)
    print("✅ Sistem Siap! Mari berdiskusi tentang mitigasi Bogor.\n")
except Exception as e:
    print(f"❌ Error saat inisialisasi: {e}")
    exit()

def cari_konteks_rag(pertanyaan):
    # Ambil beberapa keyword penting
    keywords = pertanyaan.lower().split()
    keyword = next((k for k in keywords if k in ['angin', 'banjir', 'gempa', 'longsor', 'erupsi', 'karhutla', 'kekeringan']), keywords[-1])
    
    query = """
    MATCH (d:Dokumen)
    WHERE toLower(d.nama) CONTAINS $keyword
    RETURN d.isi AS teks, d.nama AS sumber
    LIMIT 1
    """
    results = graph.query(query, params={"keyword": keyword})
    return results

def tanya_chatbot(pertanyaan):
    """Fungsi utama untuk menghasilkan jawaban"""
    konteks_data = cari_konteks_rag(pertanyaan)
    
    if not konteks_data:
        # Jika tidak ada kata kunci spesifik, tetap ambil Dasar Hukum Perbup
        konteks_data = graph.query("MATCH (d:Dokumen {tipe: 'Produk Hukum'}) RETURN d.isi AS teks, d.nama AS sumber LIMIT 1")

    # Gabungkan teks untuk dikirim ke Gemma
    referensi = "\n\n".join([r['teks'] for r in konteks_data])
    sumber_file = ", ".join(list(set([r['sumber'] for r in konteks_data])))

    prompt = f"""
    Kamu adalah asisten mitigasi bencana BPBD Kabupaten Bogor yang ramah dan mudah dipahami masyarakat awam.
    Gunakan bahasa yang sederhana, hindari istilah teknis berlebihan.
    Gunakan referensi resmi berikut:
    ---
    {referensi}
    ---
    Pertanyaan: {pertanyaan}

    Jawab singkat, padat, dan jelas per fase (Pra, Saat, Pasca Bencana).
    Maksimal 5 poin per fase.
    """
    
    respon = llm.invoke(prompt)
    return f"\n🤖 Gemma 3:\n{respon}\n\n📚 Sumber: {sumber_file}\n"

# 2. Loop Interaksi Chat
if __name__ == "__main__":
    print("-" * 50)
    print("Ketik 'keluar' atau 'exit' untuk mengakhiri chat.")
    print("-" * 50)
    
    while True:
        user_msg = input("Asti (User): ")
        if user_msg.lower() in ['keluar', 'exit', 'quit']:
            print("Sampai jumpa, Asti! Semangat skripsinya! ✨")
            break
        
        if user_msg.strip() == "":
            continue
            
        hasil = tanya_chatbot(user_msg)
        print(hasil)
        print("-" * 50)