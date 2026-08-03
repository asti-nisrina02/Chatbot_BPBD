# BOGORSiaga — Chatbot Mitigasi Bencana Berbasis Knowledge Graph

Final year project (skripsi) untuk gelar sarjana Teknik Informatika, Universitas Ibn Khaldun (UIKA) Bogor.

Chatbot ini dibangun untuk membantu masyarakat Kabupaten Bogor mengakses informasi kesiapsiagaan dan mitigasi bencana secara interaktif, dengan basis pengetahuan yang diekstraksi dari Buku Saku Siaga Bencana BPBD Kabupaten Bogor (Cetakan Kedua, 2024) ke dalam sebuah Knowledge Graph.

## Fitur Utama

- Chatbot berbasis Flask yang menjawab pertanyaan seputar 8 jenis bencana: banjir, gempa bumi, angin kencang, erupsi gunung api, karhutla, kekeringan, pergeseran tanah, dan tanah longsor
- Basis pengetahuan berupa Knowledge Graph di Neo4j, dibangun dari ekstraksi entitas & relasi otomatis menggunakan LLM
- Klasifikasi pertanyaan ke dalam 5 kategori: definisi, lokasi, dampak, larangan, dan prosedural
- Evaluasi kualitas jawaban menggunakan framework RAGAS

## Tech Stack

- **LLM lokal:** Ollama + Gemma3:4b
- **Database graph:** Neo4j Desktop
- **Framework:** LangChain, Flask
- **Ekstraksi dokumen:** PyMuPDF
- **Evaluasi:** RAGAS v0.4.3

## Knowledge Graph

- **483 node** (472 `:Entitas` dengan properti nama/deskripsi/fase + 11 `:Dokumen`)
- **754 relasi**, 79 tipe relasi unik
- Sumber data: 11 dokumen PDF hasil pemecahan dari Buku Saku Siaga Bencana BPBD Kabupaten Bogor 2024

## Hasil Evaluasi (RAGAS, rata-rata 3 trial)

| Metrik | Skor |
|---|---|
| Faithfulness | 0.8707 |
| Context Precision | 0.8249 |
| Answer Relevancy* | 0.6732 |

*Answer Relevancy dihitung menggunakan manual cosine similarity proxy (bukan metrik resmi RAGAS) karena adanya known bug pada `embed_query` di RAGAS v0.4.3 saat menggunakan local embeddings.

## Struktur Project

```
├── data/                   # 11 dokumen sumber (PDF) per jenis bencana
├── templates/              # Template HTML untuk antarmuka chatbot
├── app.py                  # Entry point aplikasi Flask
├── ingest_data.py          # Script ekstraksi & ingest data ke Neo4j
├── init_database.py        # Inisialisasi skema database
├── evaluasi.py              # Script evaluasi RAGAS
└── jawaban_dataset.csv     # Dataset Q&A untuk evaluasi
```

## Cara Menjalankan

1. Install dependencies: `pip install -r requirements.txt`
2. Siapkan instance Neo4j lokal dan sesuaikan kredensial di file `.env`
3. Jalankan Ollama dengan model `gemma3:4b`
4. Ingest data: `python ingest_data.py`
5. Jalankan aplikasi: `python app.py`

## Catatan & Keterbatasan

- Rata-rata waktu respons chatbot saat ini masih ~279 detik/pertanyaan, dicatat sebagai catatan untuk pengembangan lebih lanjut
- ~3.5% node dalam Knowledge Graph tidak memiliki relasi ke entitas lain (hanya terhubung ke dokumen sumbernya) — karakteristik alami dari ekstraksi KG berbasis LLM, tidak memengaruhi kualitas retrieval karena retrieval bersifat berbasis dokumen
- Terdapat 14 dari 99 pertanyaan evaluasi yang topiknya belum tercakup dalam dokumen sumber; chatbot merespons dengan jujur bahwa informasi tidak tersedia

## Penulis

**Anastia Firyal Nisrina**
Teknik Informatika, Universitas Ibn Khaldun (UIKA) Bogor
Pembimbing I: Gibtha Fitri Laxmi
Pembimbing II: Dr. Foni Agus Setiawan (BRIN Bandung)

## Lisensi

Proyek ini menggunakan lisensi MIT — lihat file [LICENSE](LICENSE) untuk detail.
