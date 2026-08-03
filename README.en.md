# BOGORSiaga — Knowledge Graph-Based Disaster Mitigation Chatbot

![Python](https://img.shields.io/badge/Python-3.x-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-final%20year%20project-orange)

🇮🇩 [Baca dalam Bahasa Indonesia](README.md)

Final year project (undergraduate thesis) for a Bachelor's degree in Informatics Engineering, Universitas Ibn Khaldun (UIKA) Bogor.

This chatbot was built to help the community of Kabupaten Bogor access disaster preparedness and mitigation information interactively, with a knowledge base extracted from BPBD Kabupaten Bogor's Disaster Preparedness Handbook (2nd edition, 2024) into a Knowledge Graph.

## Key Features

- Flask-based chatbot answering questions on 8 disaster types: floods, earthquakes, strong winds, volcanic eruptions, forest/land fires, drought, land shifts, and landslides
- Knowledge base in the form of a Neo4j Knowledge Graph, built from automated entity & relation extraction using an LLM
- Question classification into 5 categories: definition, location, impact, prohibition, and procedural
- Answer quality evaluation using the RAGAS framework

## Tech Stack

- **Local LLM:** Ollama + Gemma3:4b
- **Graph database:** Neo4j Desktop
- **Framework:** LangChain, Flask
- **Document extraction:** PyMuPDF
- **Evaluation:** RAGAS v0.4.3

## Knowledge Graph

- **483 nodes** (472 `:Entitas` with nama/deskripsi/fase properties + 11 `:Dokumen`)
- **754 relations**, 79 unique relation types
- Data source: 11 PDF documents split from BPBD Kabupaten Bogor's 2024 Disaster Preparedness Handbook

## Evaluation Results (RAGAS, 3-trial average)

| Metric | Score |
|---|---|
| Faithfulness | 0.8707 |
| Context Precision | 0.8249 |
| Answer Relevancy* | 0.6732 |

*Answer Relevancy was computed using a manual cosine similarity proxy (not the official RAGAS metric) due to a known bug in RAGAS v0.4.3's `embed_query` when using local embeddings.

## Project Structure

```
├── data/                   # 11 source documents (PDF) per disaster type
├── templates/              # HTML templates for the chatbot interface
├── app.py                  # Flask application entry point
├── ingest_data.py          # Data extraction & ingestion script into Neo4j
├── init_database.py        # Database schema initialization
├── evaluasi.py              # RAGAS evaluation script
└── jawaban_dataset.csv     # Q&A dataset for evaluation
```

## How to Run

1. Install dependencies: `pip install -r requirements.txt`
2. Set up a local Neo4j instance and configure credentials in a `.env` file
3. Run Ollama with the `gemma3:4b` model
4. Ingest data: `python ingest_data.py`
5. Run the application: `python app.py`

> ⚠️ **Known issues:** The current version still has some unresolved bugs (particularly in certain cache flows and edge-case questions). This repo is published as source code documentation for academic/portfolio purposes, not as a deployment-ready application.

## Notes & Limitations

- Average chatbot response time is currently ~279 seconds/question, noted as an area for further development
- ~3.5% of nodes in the Knowledge Graph have no relations to other entities (only connected to their source document) — a natural characteristic of LLM-based KG extraction, with no impact on retrieval quality since retrieval is document-based
- 14 out of 99 evaluation questions cover topics not present in the source documents; the chatbot honestly responds that the information is unavailable

## Author

**Anastia Firyal Nisrina**
Informatics Engineering, Universitas Ibn Khaldun (UIKA) Bogor
Supervisor I: Gibtha Fitri Laxmi
Supervisor II: Dr. Foni Agus Setiawan (BRIN Bandung)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
