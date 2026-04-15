import psycopg2
import os

url = "postgresql://admin:harshnaik0212@localhost:5433/coursedb"
conn = psycopg2.connect(url)
cur = conn.cursor()

# Get column details
cur.execute("""
    SELECT column_name, data_type, udt_name, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'chunks'
    ORDER BY ordinal_position
""")
cols = cur.fetchall()
print('=== LOCAL CHUNKS TABLE SCHEMA ===')
for c in cols:
    print(c)

# Check vector dimension specifically
cur.execute("""
    SELECT attname, atttypmod
    FROM pg_attribute
    WHERE attrelid = 'chunks'::regclass AND attname = 'dense_embedding'
""")
vec_info = cur.fetchone()
print(f'\n=== VECTOR DIMENSION CHECK ===')
if vec_info:
    dim = vec_info[1] - 4
    print(f'Column: {vec_info[0]}, atttypmod: {vec_info[1]}, Estimated Dim: {dim}')
    
    cur.execute('SELECT dense_embedding FROM chunks LIMIT 1')
    sample = cur.fetchone()
    if sample and sample[0]:
        val = str(sample[0]).strip('[]')
        est_dim = len(val.split(','))
        print(f'Sample embedding count: {est_dim}')
else:
    print('Vector column not found.')

conn.close()
