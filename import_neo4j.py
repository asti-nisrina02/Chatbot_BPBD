from neo4j import GraphDatabase
import pandas as pd
import re

URI = "bolt://127.0.0.1:7687"
USERNAME = "neo4j"
PASSWORD = "skripsiAsti"

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

df_nodes = pd.read_csv("nodes.csv")
df_rels = pd.read_csv("relationships.csv")

import pandas as pd

df_nodes = pd.read_csv("nodes.csv")
df_rels = pd.read_csv("relationships.csv")

print("=== DUPLICATE NODES ===")
print(df_nodes[df_nodes.duplicated(subset=["nama"], keep=False)])

print(f"\nTotal nodes di CSV: {len(df_nodes)}")
print(f"Total relationships di CSV: {len(df_rels)}")

with driver.session(database="skripsi.chatbot") as session:

    # Import nodes
    for _, row in df_nodes.iterrows():
        # Bersihkan label: ['Dokumen'] -> Dokumen
        raw_label = str(row["label"])
        label = re.findall(r"[\w]+", raw_label)[0]  # ambil kata pertama
        nama = row["nama"]
        props = row.dropna().to_dict()

        print(f"Creating node: label={label}, nama={nama}")  # debug

        query = f"MERGE (n:{label} {{nama: $nama}}) SET n += $props"
        session.run(query, nama=nama, props=props)

    print(f"Imported {len(df_nodes)} nodes")

    # Import relationships
    for _, row in df_rels.iterrows():
        source_label = row["source_label"]
        target_label = row["target_label"]
        rel_type = row["relationship"]

        query = f"""
            MATCH (a:{source_label} {{nama: $source}})
            MATCH (b:{target_label} {{nama: $target}})
            MERGE (a)-[r:{rel_type}]->(b)
        """
        session.run(query, source=row["source"], target=row["target"])

    print(f"Imported {len(df_rels)} relationships")

driver.close()