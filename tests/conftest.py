import pytest
from PIL import Image
from app.auth import hash_password
from app.db import create_schema, create_user, get_connection


@pytest.fixture
def db_conn():
    conn = get_connection(":memory:")
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def admin_client(tmp_photos_dir, tmp_path, monkeypatch):
    import app.main as main_module
    db_path = tmp_path / "test.db"
    thumbnails_dir = tmp_path / "thumbnails"
    monkeypatch.setattr(main_module, "PHOTOS_DIR", tmp_photos_dir)
    monkeypatch.setattr(main_module, "THUMBNAILS_DIR", thumbnails_dir)
    monkeypatch.setattr(main_module, "DB_PATH", db_path)
    from fastapi.testclient import TestClient
    with TestClient(main_module.app) as c:
        # Create admin user and log in
        conn = get_connection(db_path)
        create_schema(conn)
        create_user(conn, username="admin", password_hash=hash_password("testpass"), role="admin")
        conn.close()
        c.post("/login", data={"username": "admin", "password": "testpass"})
        yield c


@pytest.fixture
def tmp_photos_dir(tmp_path):
    photos_dir = tmp_path / "photos"
    cat_dir = photos_dir / "test-catalogue"
    cat_dir.mkdir(parents=True)

    (cat_dir / "catalogue.yaml").write_text(
        "title: Test Catalogue\n"
        "description: A test catalogue\n"
        "date: 2024-01-15\n"
        "location: Test Location\n"
        "cover_image: photo1.jpg\n"
        "tags:\n  - test\n  - sample\n"
    )

    img = Image.new("RGB", (200, 100), color=(100, 150, 200))
    img.save(cat_dir / "photo1.jpg", "JPEG")

    img2 = Image.new("RGB", (100, 200), color=(200, 150, 100))
    img2.save(cat_dir / "photo2.jpg", "JPEG")

    (cat_dir / "photo1.yaml").write_text(
        "title: Photo One\n"
        "caption: First photo caption\n"
        "location: Specific Location\n"
        "tags:\n  - tagged\n"
    )

    return photos_dir
