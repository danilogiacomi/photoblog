import sqlite3
from datetime import datetime
from pathlib import Path

import yaml
from PIL import Image

from app.db import (
    delete_missing_catalogues,
    delete_missing_photos,
    upsert_catalogue,
    upsert_photo,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

_EXIF_DATETIME_ORIGINAL = 36867
_EXIF_IMAGE_DESCRIPTION = 270


def parse_catalogue_yaml(catalogue_dir: Path) -> dict:
    yaml_path = catalogue_dir / "catalogue.yaml"
    if not yaml_path.exists():
        return {"title": catalogue_dir.name}
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("title", catalogue_dir.name)
    if data.get("date") is not None:
        data["date"] = str(data["date"])
    return data


def parse_sidecar_yaml(sidecar_path: Path) -> dict:
    if not sidecar_path.exists():
        return {}
    with open(sidecar_path) as f:
        data = yaml.safe_load(f) or {}
    if data.get("date") is not None:
        data["date"] = str(data["date"])
    return data


def extract_exif(image_path: Path) -> dict:
    try:
        img = Image.open(image_path)
        exif_data = img.getexif()
        if not exif_data:
            return {}
        result = {}
        date_str = exif_data.get(_EXIF_DATETIME_ORIGINAL)
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                result["date"] = dt.date().isoformat()
            except ValueError:
                pass
        desc = exif_data.get(_EXIF_IMAGE_DESCRIPTION)
        if desc:
            result["title"] = (
                desc.decode("utf-8", errors="ignore") if isinstance(desc, bytes) else str(desc)
            )
        return result
    except Exception:
        return {}


def merge_photo_metadata(filename: str, sidecar: dict, exif: dict) -> dict:
    stem = Path(filename).stem
    return {
        "title": sidecar.get("title") or exif.get("title") or stem,
        "caption": sidecar.get("caption"),
        "date": sidecar.get("date") or exif.get("date"),
        "location": sidecar.get("location"),
        "tags": sidecar.get("tags") or [],
    }


def index_catalogue(catalogue_dir: Path, conn: sqlite3.Connection) -> None:
    if not catalogue_dir.is_dir():
        return
    slug = catalogue_dir.name
    cat_meta = parse_catalogue_yaml(catalogue_dir)

    image_files = sorted(
        f for f in catalogue_dir.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS
    )

    cat_id = upsert_catalogue(
        conn,
        slug=slug,
        title=cat_meta.get("title", slug),
        description=cat_meta.get("description"),
        date=cat_meta.get("date"),
        location=cat_meta.get("location"),
        cover_image=cat_meta.get("cover_image"),
        tags=cat_meta.get("tags", []),
        photo_count=len(image_files),
    )

    existing_filenames = []
    for image_path in image_files:
        sidecar = parse_sidecar_yaml(image_path.with_suffix(".yaml"))
        exif = extract_exif(image_path)
        meta = merge_photo_metadata(image_path.name, sidecar, exif)

        try:
            with Image.open(image_path) as img:
                aspect_ratio = img.width / img.height if img.height else 1.0
        except Exception:
            aspect_ratio = 1.0

        upsert_photo(
            conn,
            catalogue_id=cat_id,
            filename=image_path.name,
            title=meta["title"],
            caption=meta["caption"],
            date=meta["date"],
            location=meta["location"],
            tags=meta["tags"],
            exif_raw=exif,
            aspect_ratio=aspect_ratio,
        )
        existing_filenames.append(image_path.name)

    delete_missing_photos(conn, cat_id, existing_filenames)


def index_all(photos_dir: Path, conn: sqlite3.Connection) -> None:
    photos_dir.mkdir(parents=True, exist_ok=True)
    catalogue_dirs = [d for d in photos_dir.iterdir() if d.is_dir()]
    existing_slugs = []
    for cat_dir in catalogue_dirs:
        index_catalogue(cat_dir, conn)
        existing_slugs.append(cat_dir.name)
    delete_missing_catalogues(conn, existing_slugs)
