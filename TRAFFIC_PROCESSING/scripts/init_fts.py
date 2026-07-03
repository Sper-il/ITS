import sqlite3

conn = sqlite3.connect('c:/Users/Admin/Downloads/ITS/TRAFFIC_PROCESSING/locations.db')

# Check current schema
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Create FTS5 virtual table
conn.execute("""
CREATE VIRTUAL TABLE IF NOT EXISTS locations_fts USING fts5(
    name, address, category,
    content='locations',
    content_rowid='id'
)
""")

# Create triggers
conn.executescript("""
CREATE TRIGGER IF NOT EXISTS locations_ai AFTER INSERT ON locations BEGIN
    INSERT INTO locations_fts(rowid, name, address, category)
    VALUES (new.id, new.name, new.address, new.category);
END;

CREATE TRIGGER IF NOT EXISTS locations_ad AFTER DELETE ON locations BEGIN
    INSERT INTO locations_fts(rowid, name, address, category)
    VALUES (old.id, old.name, old.address, old.category);
END;

CREATE TRIGGER IF NOT EXISTS locations_au AFTER UPDATE ON locations BEGIN
    INSERT INTO locations_fts(rowid, name, address, category)
    VALUES (old.id, old.name, old.address, old.category);
END;
""")

# Populate FTS with existing data
conn.execute("INSERT INTO locations_fts(rowid, name, address, category) SELECT id, name, address, category FROM locations")
conn.commit()

# Verify
r = conn.execute('SELECT count(*) FROM locations_fts').fetchone()[0]
print(f'FTS5 populated: {r} rows')

# Test FTS search
r = conn.execute("SELECT name, lat, lon FROM locations JOIN locations_fts ON locations.id = locations_fts.rowid WHERE locations_fts MATCH 'Ben' LIMIT 5").fetchall()
print(f'FTS search Ben: {r}')

conn.close()
