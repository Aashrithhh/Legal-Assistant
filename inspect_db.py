import sqlite3

db_path = r"C:\Users\AashrithReddyVootkur\Documents\legal-assistant\data\index\embeddings.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"Tables in database: {tables}\n")

for table in tables:
    print(f"=" * 60)
    print(f"TABLE: {table}")
    print("=" * 60)
    
    # Get schema
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    print("\nSchema:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"\nTotal rows: {count}")
    
    # Show first 5 rows (without embedding vectors if too large)
    cursor.execute(f"SELECT * FROM {table} LIMIT 5")
    rows = cursor.fetchall()
    
    if rows:
        print(f"\nFirst {len(rows)} rows:")
        col_names = [col[1] for col in columns]
        
        for i, row in enumerate(rows, 1):
            print(f"\n  Row {i}:")
            for col_name, value in zip(col_names, row):
                # Truncate large values (like embeddings)
                if col_name == 'embedding' and value:
                    print(f"    {col_name}: [vector with {len(value)} bytes]")
                elif isinstance(value, str) and len(value) > 200:
                    print(f"    {col_name}: {value[:200]}...")
                else:
                    print(f"    {col_name}: {value}")
    print("\n")

conn.close()
print("Done!")
