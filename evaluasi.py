import os
from dotenv import load_dotenv
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from ragas.llms import llm_factory
from openai import OpenAI
from datasets import Dataset
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
import pandas as pd

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

data = {
    "question": df["question"].tolist(),
    "answer": df["answer"].tolist(),
    "contexts": [[ctx] for ctx in df["context"].tolist()],
    "reference": df["reference"].tolist()
}

dataset = Dataset.from_dict(data)
print("✅ Dataset siap!")

print("\n📊 Mengevaluasi dengan RAGAS...")
hasil = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, context_precision],
    llm=ragas_llm,
    embeddings=ragas_embeddings
)

print("\n✅ Hasil Evaluasi RAGAS:")
df_hasil = hasil.to_pandas()
print(f"  Faithfulness      : {df_hasil['faithfulness'].mean():.4f}")
print(f"  Answer Relevancy  : {df_hasil['answer_relevancy'].mean():.4f}")
print(f"  Context Precision : {df_hasil['context_precision'].mean():.4f}")

print("\n📋 Detail per pertanyaan:")
print(df_hasil[['user_input', 'faithfulness', 'answer_relevancy', 'context_precision']].to_string(index=False))

df_hasil.to_csv("hasil_evaluasi.csv", index=False)
print("\n💾 Hasil disimpan ke hasil_evaluasi.csv")

import numpy as np

def hitung_answer_relevancy(pertanyaan, jawaban):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[pertanyaan, jawaban]
    )
    emb_pertanyaan = np.array(response.data[0].embedding)
    emb_jawaban = np.array(response.data[1].embedding)
    
    similarity = np.dot(emb_pertanyaan, emb_jawaban) / (
        np.linalg.norm(emb_pertanyaan) * np.linalg.norm(emb_jawaban)
    )
    return float(similarity)

print("\n📊 Answer Relevancy (Manual Cosine Similarity):")
ar_scores = []
for _, row in df.iterrows():
    score = hitung_answer_relevancy(row['question'], row['answer'])
    ar_scores.append(score)
    print(f"  {row['question'][:55]}... : {score:.4f}")

print(f"\n  Answer Relevancy (rata-rata): {np.mean(ar_scores):.4f}")

# Update CSV dengan answer relevancy
df_hasil['answer_relevancy_manual'] = ar_scores
df_hasil.to_csv("hasil_evaluasi.csv", index=False)
print("💾 CSV diupdate dengan answer relevancy manual")