import pandas as pd

df = pd.read_csv("relationships.csv")
df["relationship"] = df["relationship"].replace("MEMILIKI_ENTITAS", "MEMBAHAS")
df.to_csv("relationships.csv", index=False)
print("Selesai! MEMILIKI_ENTITAS sudah diganti jadi MEMBAHAS")