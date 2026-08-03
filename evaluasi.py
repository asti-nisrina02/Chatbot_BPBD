import os
from dotenv import load_dotenv
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from ragas.llms import llm_factory
from openai import OpenAI
from datasets import Dataset
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
import pandas as pd
import numpy as np

load_dotenv(dotenv_path='.env', override=True)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ragas_llm = llm_factory(
    "gpt-4.1-nano",
    client=openai_client,
    temperature=0
)

ragas_embeddings = RagasOpenAIEmbeddings(
    model="text-embedding-3-small",
    client=openai_client
)

# Load dari CSV
df = pd.read_csv("jawaban_dataset.csv")
print(f"✅ Data loaded: {len(df)} rows")

# Fix: kolom context/answer/reference bisa kebaca NaN (float) kalau ada cell
# kosong (misal soal nomor darurat yang bypass hardcode, jadi context-nya
# memang kosong by design). NaN bikin pyarrow gagal infer tipe kolom saat
# convert ke Dataset (error "tried to convert to double"). fillna("") biar
# semua konsisten jadi string kosong, bukan NaN.
df["context"] = df["context"].fillna("")
df["answer"] = df["answer"].fillna("")
df["reference"] = df["reference"].fillna("")

data = {
    "question": df["question"].tolist(),
    "answer": df["answer"].tolist(),
    "contexts": [[ctx] for ctx in df["context"].tolist()],
    "reference": df["reference"].tolist()
}

dataset = Dataset.from_dict(data)
print("✅ Dataset siap!")

# ─── Coba jalanin metrik answer_relevancy RESMI RAGAS juga ────────────────
# Ini kemungkinan besar tetap NaN (bug dikenal di RAGAS v0.4.3 dengan
# embeddings lokal -- wrapper OpenAIEmbeddings gak punya method embed_query).
# Tetap dicoba di sini (gak mahal, gak bikin crash, cuma NaN kalau gagal),
# dan tetap dihitung MANUAL sesuai formula AR = (1/N) Σ cos(q, Qi) di bawah
# sebagai metode utama yang dilaporkan (sesuai catatan metodologi jurnal).
print("\n📊 Mengevaluasi dengan RAGAS (Faithfulness, Answer Relevancy, Context Precision)...")
hasil = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, context_precision],
    llm=ragas_llm,
    embeddings=ragas_embeddings
)

print("\n✅ Hasil Evaluasi RAGAS (native):")
df_hasil = hasil.to_pandas()
print(f"  Faithfulness      : {df_hasil['faithfulness'].mean():.4f}")
ar_native_mean = df_hasil['answer_relevancy'].mean()
if pd.isna(ar_native_mean):
    print(f"  Answer Relevancy  : NaN (bug diketahui di RAGAS v0.4.3 dgn embeddings lokal -- pakai hasil manual di bawah)")
else:
    print(f"  Answer Relevancy  : {ar_native_mean:.4f}")
print(f"  Context Precision : {df_hasil['context_precision'].mean():.4f}")

print("\n📋 Detail per pertanyaan:")
print(df_hasil[['user_input', 'faithfulness', 'answer_relevancy', 'context_precision']].to_string(index=False))

df_hasil.to_csv("hasil_evaluasi.csv", index=False)
print("\n💾 Hasil disimpan ke hasil_evaluasi.csv")


# ─── Answer Relevancy MANUAL, sesuai formula: AR = (1/N) Σ cos(q, Qi) ──────
# q = pertanyaan asli, Qi = N pertanyaan yang digenerate DARI jawaban.
# Ini algoritma yang sama dengan Answer Relevancy resmi RAGAS, cuma
# dihitung manual karena bug embed_query di atas.
N_QUESTIONS = 3  # sama dengan default RAGAS


def generate_questions_from_answer(jawaban, n=N_QUESTIONS, model="gpt-4.1-nano"):
    """Generate N pertanyaan yang mungkin dijawab oleh teks jawaban ini,
    pakai LLM yang sama dengan judge RAGAS (gpt-4.1-nano)."""
    prompt = f"""Generate {n} questions (in Indonesian) that the following answer
could plausibly be responding to. Return ONLY the questions, one per line,
no numbering, no extra text.

Answer:
{jawaban}
"""
    resp = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    teks = resp.choices[0].message.content.strip()
    pertanyaan_list = [q.strip("-•0123456789. ").strip() for q in teks.split("\n") if q.strip()]
    return pertanyaan_list[:n] if pertanyaan_list else [jawaban]


def embed(teks):
    resp = openai_client.embeddings.create(model="text-embedding-3-small", input=[teks])
    return np.array(resp.data[0].embedding)


def cosine_sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def hitung_answer_relevancy_manual(pertanyaan_asli, jawaban, n=N_QUESTIONS):
    """AR = (1/N) * sum(cos(q, Qi)) -- Qi = pertanyaan hasil generate dari jawaban."""
    pertanyaan_generated = generate_questions_from_answer(jawaban, n=n)
    emb_asli = embed(pertanyaan_asli)
    similarities = [cosine_sim(emb_asli, embed(qi)) for qi in pertanyaan_generated]
    return float(np.mean(similarities)), pertanyaan_generated


print(f"\n📊 Answer Relevancy MANUAL (formula: AR = (1/N) Σ cos(q, Qi), N={N_QUESTIONS}):")
ar_scores = []
for _, row in df.iterrows():
    score, generated = hitung_answer_relevancy_manual(row['question'], row['answer'])
    ar_scores.append(score)
    print(f"  {row['question'][:55]}... : {score:.4f}")

print(f"\n  Answer Relevancy (manual, rata-rata): {np.mean(ar_scores):.4f}")

df_hasil['answer_relevancy_manual'] = ar_scores
df_hasil.to_csv("hasil_evaluasi.csv", index=False)
print("💾 CSV diupdate dengan kolom answer_relevancy_manual")

print("\n" + "=" * 60)
print("📊 RINGKASAN FINAL")
print("=" * 60)
print(f"  Faithfulness                    : {df_hasil['faithfulness'].mean():.4f}")
print(f"  Context Precision               : {df_hasil['context_precision'].mean():.4f}")
if pd.isna(ar_native_mean):
    print(f"  Answer Relevancy (RAGAS native) : NaN (gagal, lihat catatan di atas)")
else:
    print(f"  Answer Relevancy (RAGAS native) : {ar_native_mean:.4f}")
print(f"  Answer Relevancy (manual, N={N_QUESTIONS})     : {np.mean(ar_scores):.4f}")
print("=" * 60)