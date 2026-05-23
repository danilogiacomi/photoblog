import pytest
from pathlib import Path
from fastapi.testclient import TestClient

import app.main as main_module


@pytest.fixture
def client(tmp_photos_dir, tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    thumbnails_dir = tmp_path / "thumbnails"
    monkeypatch.setattr(main_module, "PHOTOS_DIR", tmp_photos_dir)
    monkeypatch.setattr(main_module, "THUMBNAILS_DIR", thumbnails_dir)
    monkeypatch.setattr(main_module, "DB_PATH", db_path)
    with TestClient(main_module.app) as c:
        yield c


def test_splash_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_homepage_returns_200(client):
    response = client.get("/gallery")
    assert response.status_code == 200


def test_homepage_shows_catalogue_title(client):
    response = client.get("/gallery")
    assert "Test Catalogue" in response.text


def test_catalogue_page_returns_200(client):
    response = client.get("/catalogue/test-catalogue")
    assert response.status_code == 200


def test_catalogue_page_shows_photo_filenames(client):
    response = client.get("/catalogue/test-catalogue")
    assert "photo1.jpg" in response.text


def test_catalogue_404_for_unknown_slug(client):
    response = client.get("/catalogue/nonexistent")
    assert response.status_code == 404


def test_photo_page_returns_200(client):
    response = client.get("/catalogue/test-catalogue/photo1.jpg")
    assert response.status_code == 200


def test_photo_page_shows_sidecar_title(client):
    response = client.get("/catalogue/test-catalogue/photo1.jpg")
    assert "Photo One" in response.text


def test_photo_page_has_prev_next_links(client):
    response = client.get("/catalogue/test-catalogue/photo1.jpg")
    assert "photo2.jpg" in response.text


def test_photo_404_for_unknown_filename(client):
    response = client.get("/catalogue/test-catalogue/nonexistent.jpg")
    assert response.status_code == 404


def test_serve_photo_redirects_when_unauthenticated(client):
    response = client.get("/photos/test-catalogue/photo1.jpg", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_serve_photo_returns_image_bytes(admin_client):
    response = admin_client.get("/photos/test-catalogue/photo1.jpg")
    assert response.status_code == 200
    assert "image" in response.headers["content-type"]


def test_serve_photo_404_for_missing_file(admin_client):
    response = admin_client.get("/photos/test-catalogue/missing.jpg")
    assert response.status_code == 404


def test_thumbnail_generated_lazily(client):
    response = client.get("/thumbnails/test-catalogue/photo1.jpg")
    assert response.status_code == 200
    assert "image" in response.headers["content-type"]


def test_thumbnail_404_for_missing_source(client):
    response = client.get("/thumbnails/test-catalogue/missing.jpg")
    assert response.status_code == 404
