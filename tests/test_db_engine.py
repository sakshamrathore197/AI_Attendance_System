"""
Test SQLite & PostgreSQL engine creation, schema initialization, and basic model CRUD.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_database_sqlite():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    # Re-import to pick up memory DB
    import importlib
    import app.database
    importlib.reload(app.database)
    import app.storage
    importlib.reload(app.storage)

    from app.database import engine, SessionLocal, Base
    from app.storage import init_db
    from app.models import Employee, SystemSetting, Camera

    # Initialize tables and seed
    init_db()

    db = SessionLocal()
    try:
        # Check seeded settings
        settings = db.query(SystemSetting).all()
        assert len(settings) > 0, "Default settings should be seeded"

        # Check seeded cameras
        cameras = db.query(Camera).all()
        assert len(cameras) > 0, "Default cameras should be seeded"

        # Test creating an Employee
        emp = Employee(
            employee_id="TEST001",
            name="Jane Doe",
            department="Engineering",
            designation="AI Engineer",
            email="jane@example.com",
            status="Active"
        )
        db.add(emp)
        db.commit()

        queried = db.query(Employee).filter_by(employee_id="TEST001").first()
        assert queried is not None
        assert queried.name == "Jane Doe"
        print("✓ SQLite in-memory integration & seed test passed successfully.")
    finally:
        db.close()


def test_postgresql_url_handling():
    # Test normalization of postgres:// to postgresql://
    os.environ["DATABASE_URL"] = "postgres://user:pass@localhost:5432/mydb"
    import importlib
    import app.database
    importlib.reload(app.database)
    
    assert app.database.DATABASE_URL.startswith("postgresql://")
    print("✓ PostgreSQL URL prefix normalization (postgres:// -> postgresql://) verified.")


if __name__ == "__main__":
    test_database_sqlite()
    test_postgresql_url_handling()
    print("All database integration tests passed!")
