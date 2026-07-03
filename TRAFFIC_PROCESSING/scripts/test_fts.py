import sqlite3
conn = sqlite3.connect('c:/Users/Admin/Downloads/ITS/TRAFFIC_PROCESSING/locations.db')

# Check FTS
try:
    r = conn.execute('SELECT count(*) FROM locations_fts').fetchone()[0]
    print(f'FTS rows: {r}')
except Exception as e:
    print(f'FTS error: {e}')

# Check locations
r = conn.execute('SELECT count(*) FROM locations').fetchone()[0]
print(f'Locations rows: {r}')

# Test LIKE
r = conn.execute("SELECT count(*) FROM locations WHERE name LIKE '%Ben%'").fetchone()[0]
print(f'LIKE %Ben%: {r}')

# Test FTS MATCH
try:
    r = conn.execute("SELECT count(*) FROM locations_fts WHERE locations_fts MATCH 'Ben'").fetchone()[0]
    print(f'FTS MATCH Ben: {r}')
except Exception as e:
    print(f'FTS MATCH error: {e}')

# Check some names
r = conn.execute("SELECT name FROM locations LIMIT 5").fetchall()
print(f'Sample names: {[x[0] for x in r]}')

conn.close()
