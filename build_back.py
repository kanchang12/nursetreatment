import os
import sqlite3
import pandas as pd

print("[SYSTEM] Building lightweight production database from your downloaded files...")

DB_PATH = "decagon_index.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Index Decagon DDI Graph Interactions
decagon_gz = "PP-Decagon_ppi.csv.gz"
if os.path.exists(decagon_gz):
    print(f"[-] Processing {decagon_gz} into SQLite index...")
    # Read in chunks to avoid memory spikes
    chunk_size = 50000
    for chunk in pd.read_csv(decagon_gz, chunksize=chunk_size):
        # Normalize column names if needed
        chunk.columns = [c.strip().lower() for c in chunk.columns]
        chunk.to_sql("decagon_interactions", conn, if_exists="append", index=False)
    
    # Create fast lookup indexes on drug/node columns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_drug1 ON decagon_interactions (synth_1);") # adjust based on your columns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_drug2 ON decagon_interactions (synth_2);")
    conn.commit()
    print("[SUCCESS] Decagon interactions indexed into SQLite.")

# 2. Index Synthea Files
SYNTHEA_DIR = "data/synthea_csv"
if os.path.exists(SYNTHEA_DIR):
    for filename in os.listdir(SYNTHEA_DIR):
        if filename.endswith(".csv"):
            table_name = filename.replace(".csv", "")
            file_path = os.path.join(SYNTHEA_DIR, filename)
            print(f"[-] Importing Synthea table: {table_name}...")
            df = pd.read_csv(file_path)
            df.columns = [c.strip().lower() for c in df.columns]
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"[SUCCESS] Table '{table_name}' stored.")

conn.close()
print("[DONE] Build complete. 'decagon_index.db' is ready for deployment.")