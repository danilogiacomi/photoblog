import pytest
from pathlib import Path
from PIL import Image

from app.indexer import (
    parse_catalogue_yaml,
    parse_sidecar_yaml,
    extract_exif,
    merge_photo_metadata,
    index_catalogue,
    index_all,
)
from app.db import (
    get_all_catalogues,
    get_catalogue_by_slug,
    get_photos_by_catalogue,
)


def test_parse_catalogue_yaml_full(tmp_path):
    (tmp_path / "catalogue.yaml").write_text(
        "title: My Catalogue\n"
        "description: A description\n"
        "date: 2024-01-15\n"
        "location: Italy\n"
        "cover_image: photo.jpg\n"
        "tags:\n  - travel\n"
    )
    result = parse_catalogue_yaml(tmp_path)
    assert result["title"] == "My Catalogue"
    assert result["location"] == "Italy"
    assert result["tags"] == ["travel"]
    assert result["date"] == "2024-01-15"


def test_parse_catalogue_yaml_missing_uses_dirname(tmp_path):
    cat_dir = tmp_path / "my-catalogue"
    cat_dir.mkdir()
    result = parse_catalogue_yaml(cat_dir)
    assert result["title"] == "my-catalogue"


def test_parse_sidecar_yaml_reads_fields(tmp_path):
    (tmp_path / "photo.yaml").write_text("title: My Photo\ncaption: A caption\n")
    result = parse_sidecar_yaml(tmp_path / "photo.yaml")
    assert result["title"] == "My Photo"
    assert result["caption"] == "A caption"


def test_parse_sidecar_yaml_missing_returns_empty(tmp_path):
    result = parse_sidecar_yaml(tmp_path / "nonexistent.yaml")
    assert result == {}


def test_merge_photo_metadata_sidecar_takes_priority():
    sidecar = {"title": "Sidecar Title", "date": "2024-03-01", "location": "Rome"}
    exif = {"title": "EXIF Title", "date": "2024-01-01"}
    result = merge_photo_metadata("photo.jpg", sidecar, exif)
    assert result["title"] == "Sidecar Title"
    assert result["date"] == "2024-03-01"
    assert result["location"] == "Rome"


def test_merge_photo_metadata_falls_back_to_exif_date():
    sidecar = {"title": "Photo"}
    exif = {"date": "2024-02-15"}
    result = merge_photo_metadata("photo.jpg", sidecar, exif)
    assert result["date"] == "2024-02-15"


def test_merge_photo_metadata_falls_back_to_stem_for_title():
    result = merge_photo_metadata("sunset-over-sea.jpg", {}, {})
    assert result["title"] == "sunset-over-sea"


def test_index_catalogue_populates_db(tmp_photos_dir, db_conn):
    cat_dir = tmp_photos_dir / "test-catalogue"
    index_catalogue(cat_dir, db_conn)
    cat = get_catalogue_by_slug(db_conn, "test-catalogue")
    assert cat is not None
    assert cat["title"] == "Test Catalogue"
    photos = get_photos_by_catalogue(db_conn, cat["id"])
    assert len(photos) == 2


def test_index_catalogue_stores_aspect_ratio(tmp_photos_dir, db_conn):
    cat_dir = tmp_photos_dir / "test-catalogue"
    index_catalogue(cat_dir, db_conn)
    cat = get_catalogue_by_slug(db_conn, "test-catalogue")
    photos = get_photos_by_catalogue(db_conn, cat["id"])
    photo1 = next(p for p in photos if p["filename"] == "photo1.jpg")
    assert photo1["aspect_ratio"] == pytest.approx(2.0)  # 200x100 image


def test_index_catalogue_applies_sidecar_metadata(tmp_photos_dir, db_conn):
    cat_dir = tmp_photos_dir / "test-catalogue"
    index_catalogue(cat_dir, db_conn)
    cat = get_catalogue_by_slug(db_conn, "test-catalogue")
    photos = get_photos_by_catalogue(db_conn, cat["id"])
    photo1 = next(p for p in photos if p["filename"] == "photo1.jpg")
    assert photo1["title"] == "Photo One"
    assert photo1["caption"] == "First photo caption"


def test_index_all_indexes_multiple_catalogues(tmp_photos_dir, db_conn):
    cat2 = tmp_photos_dir / "second-catalogue"
    cat2.mkdir()
    (cat2 / "catalogue.yaml").write_text("title: Second\n")
    img = Image.new("RGB", (100, 100), color=(50, 50, 50))
    img.save(cat2 / "img.jpg", "JPEG")

    index_all(tmp_photos_dir, db_conn)
    cats = get_all_catalogues(db_conn)
    assert len(cats) == 2


def test_index_all_removes_deleted_catalogue(tmp_photos_dir, db_conn):
    index_all(tmp_photos_dir, db_conn)
    assert len(get_all_catalogues(db_conn)) == 1

    import shutil
    shutil.rmtree(tmp_photos_dir / "test-catalogue")
    index_all(tmp_photos_dir, db_conn)
    assert len(get_all_catalogues(db_conn)) == 0
