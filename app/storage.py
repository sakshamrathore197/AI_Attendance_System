from sqlalchemy import text
from app.database import Base, engine

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Auto-migration check for SQLite table column additions
    with engine.connect() as conn:
        try:
            # Check unknown_faces created_at
            result = conn.execute(text("PRAGMA table_info(unknown_faces)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "created_at" not in columns:
                conn.execute(text("ALTER TABLE unknown_faces ADD COLUMN created_at DATETIME"))
                conn.commit()
                print("[DB Migration] Added missing column 'created_at' to unknown_faces.")
        except Exception as e:
            print(f"[DB Migration] Check error: {e}")