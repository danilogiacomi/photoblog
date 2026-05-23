import pytest
from app.db import (
    upsert_catalogue, upsert_photo, delete_missing_catalogues,
    delete_missing_photos, get_all_catalogues, get_catalogue_by_slug,
    get_photos_by_catalogue, get_photo, get_adjacent_photos,
)


def test_upsert_catalogue_creates_row(db_conn):
    cat_id = upsert_catalogue(db_conn, slug="tuscany", title="Tuscany 2024")
    assert cat_id is not None
    cat = get_catalogue_by_slug(db_conn, "tuscany")
    assert cat["title"] == "Tuscany 2024"


def test_upsert_catalogue_updates_existing(db_conn):
    upsert_catalogue(db_conn, slug="tuscany", title="Old Title")
    upsert_catalogue(db_conn, slug="tuscany", title="New Title")
    cat = get_catalogue_by_slug(db_conn, "tuscany")
    assert cat["title"] == "New Title"


def test_upsert_photo_creates_row(db_conn):
    cat_id = upsert_catalogue(db_conn, slug="tuscany", title="Tuscany")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="photo.jpg", aspect_ratio=1.5)
    photo = get_photo(db_conn, cat_id, "photo.jpg")
    assert photo is not None
    assert photo["aspect_ratio"] == pytest.approx(1.5)


def test_tags_deserialized_as_list(db_conn):
    cat_id = upsert_catalogue(db_conn, slug="tuscany", title="Tuscany", tags=["a", "b"])
    cat = get_catalogue_by_slug(db_conn, "tuscany")
    assert cat["tags"] == ["a", "b"]


def test_get_all_catalogues_sorted_by_date_desc(db_conn):
    upsert_catalogue(db_conn, slug="old", title="Old", date="2022-01-01")
    upsert_catalogue(db_conn, slug="new", title="New", date="2024-01-01")
    cats = get_all_catalogues(db_conn)
    assert cats[0]["slug"] == "new"
    assert cats[1]["slug"] == "old"


def test_get_adjacent_photos(db_conn):
    cat_id = upsert_catalogue(db_conn, slug="test", title="Test")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="a.jpg")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="b.jpg")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="c.jpg")
    prev_p, next_p = get_adjacent_photos(db_conn, cat_id, "b.jpg")
    assert prev_p["filename"] == "a.jpg"
    assert next_p["filename"] == "c.jpg"


def test_get_adjacent_photos_first_has_no_prev(db_conn):
    cat_id = upsert_catalogue(db_conn, slug="test", title="Test")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="a.jpg")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="b.jpg")
    prev_p, next_p = get_adjacent_photos(db_conn, cat_id, "a.jpg")
    assert prev_p is None
    assert next_p["filename"] == "b.jpg"


def test_get_adjacent_photos_last_has_no_next(db_conn):
    cat_id = upsert_catalogue(db_conn, slug="test", title="Test")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="a.jpg")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="b.jpg")
    prev_p, next_p = get_adjacent_photos(db_conn, cat_id, "b.jpg")
    assert prev_p["filename"] == "a.jpg"
    assert next_p is None


def test_delete_missing_photos_removes_stale(db_conn):
    cat_id = upsert_catalogue(db_conn, slug="test", title="Test")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="a.jpg")
    upsert_photo(db_conn, catalogue_id=cat_id, filename="b.jpg")
    delete_missing_photos(db_conn, cat_id, ["a.jpg"])
    photos = get_photos_by_catalogue(db_conn, cat_id)
    assert len(photos) == 1
    assert photos[0]["filename"] == "a.jpg"


def test_delete_missing_catalogues_removes_stale(db_conn):
    upsert_catalogue(db_conn, slug="keep", title="Keep")
    upsert_catalogue(db_conn, slug="drop", title="Drop")
    delete_missing_catalogues(db_conn, ["keep"])
    cats = get_all_catalogues(db_conn)
    assert len(cats) == 1
    assert cats[0]["slug"] == "keep"


def test_get_catalogue_by_slug_returns_none_for_missing(db_conn):
    assert get_catalogue_by_slug(db_conn, "nonexistent") is None
