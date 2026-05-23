from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from app.auth import hash_password, new_token, session_expires_at, verify_password
from app.db import (
    create_schema,
    create_session,
    create_user,
    delete_session,
    get_adjacent_photos,
    get_all_catalogues,
    get_catalogue_by_slug,
    get_connection,
    get_photo,
    get_photos_by_catalogue,
    get_session_user,
    get_user_by_username,
)
from app.indexer import index_all
from app.watcher import start_watcher

BASE_DIR = Path(__file__).parent.parent
PHOTOS_DIR = BASE_DIR / "photos"
THUMBNAILS_DIR = BASE_DIR / "thumbnails"
DISPLAY_DIR = BASE_DIR / "display"
DB_PATH = BASE_DIR / "photoblog.db"

def _load_config() -> dict:
    path = BASE_DIR / "config.yaml"
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["config"] = _load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection(DB_PATH)
    try:
        create_schema(conn)
        index_all(PHOTOS_DIR, conn)
    finally:
        conn.close()
    observer = start_watcher(PHOTOS_DIR, lambda: get_connection(DB_PATH))
    yield
    observer.stop()
    observer.join()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


def _conn():
    return get_connection(DB_PATH)


def _get_auth_user(token: str) -> dict | None:
    conn = _conn()
    try:
        return get_session_user(conn, token)
    finally:
        conn.close()


@app.get("/manifest.json")
async def manifest():
    cfg = _load_config()
    name = cfg.get("site_name", "Photoblog")
    return JSONResponse({
        "name": name,
        "short_name": name,
        "description": cfg.get("tagline", ""),
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0d0d0d",
        "theme_color": "#0d0d0d",
        "orientation": "any",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    })


@app.get("/", response_class=HTMLResponse)
async def splash(request: Request):
    return templates.TemplateResponse(request, "splash.html", {})


@app.get("/gallery", response_class=HTMLResponse)
async def homepage(request: Request):
    conn = _conn()
    try:
        catalogues = get_all_catalogues(conn)
        for cat in catalogues:
            if not cat.get("cover_image"):
                photos = get_photos_by_catalogue(conn, cat["id"])
                cat["cover_image"] = photos[0]["filename"] if photos else None
    finally:
        conn.close()
    return templates.TemplateResponse(request, "home.html", {"catalogues": catalogues})


@app.get("/catalogue/{slug}", response_class=HTMLResponse)
async def catalogue_page(request: Request, slug: str):
    conn = _conn()
    try:
        catalogue = get_catalogue_by_slug(conn, slug)
        if not catalogue:
            raise HTTPException(status_code=404)
        photos = get_photos_by_catalogue(conn, catalogue["id"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "catalogue.html",
        {"catalogue": catalogue, "photos": photos},
    )


@app.get("/catalogue/{slug}/{filename}", response_class=HTMLResponse)
async def photo_page(request: Request, slug: str, filename: str):
    conn = _conn()
    try:
        catalogue = get_catalogue_by_slug(conn, slug)
        if not catalogue:
            raise HTTPException(status_code=404)
        photo = get_photo(conn, catalogue["id"], filename)
        if not photo:
            raise HTTPException(status_code=404)
        prev_photo, next_photo = get_adjacent_photos(conn, catalogue["id"], filename)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "photo.html",
        {
            "catalogue": catalogue,
            "photo": photo,
            "prev_photo": prev_photo,
            "next_photo": next_photo,
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    conn = _conn()
    try:
        user = get_user_by_username(conn, username)
        if not user or not verify_password(password, user["password_hash"]):
            return templates.TemplateResponse(
                request, "login.html", {"error": "Invalid username or password"}, status_code=401
            )
        token = new_token()
        create_session(conn, token=token, user_id=user["id"], expires_at=session_expires_at())
    finally:
        conn.close()
    next_url = request.query_params.get("next", "/gallery")
    response = RedirectResponse(url=next_url, status_code=303)
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=30 * 24 * 3600)
    return response


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    if token:
        conn = _conn()
        try:
            delete_session(conn, token)
        finally:
            conn.close()
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session")
    return response


@app.get("/hero-image")
async def serve_hero():
    path = (PHOTOS_DIR / "hero.jpg").resolve()
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.get("/display/{catalogue}/{filename}")
async def serve_display(catalogue: str, filename: str):
    display_path = (DISPLAY_DIR / catalogue / filename).resolve()
    src_path = (PHOTOS_DIR / catalogue / filename).resolve()
    if not src_path.is_relative_to(PHOTOS_DIR.resolve()):
        raise HTTPException(status_code=404)
    if not display_path.exists():
        if not src_path.exists():
            raise HTTPException(status_code=404)
        display_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src_path) as img:
            img.thumbnail((2048, 2048))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(display_path, "JPEG", quality=90)
    return FileResponse(display_path)


@app.get("/photos/{catalogue}/{filename}")
async def serve_photo(request: Request, catalogue: str, filename: str):
    token = request.cookies.get("session")
    if not token or not _get_auth_user(token):
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=302)
    path = (PHOTOS_DIR / catalogue / filename).resolve()
    if not path.is_relative_to(PHOTOS_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.get("/thumbnails/{catalogue}/{filename}")
async def serve_thumbnail(catalogue: str, filename: str):
    thumb_path = (THUMBNAILS_DIR / catalogue / filename).resolve()
    src_path = (PHOTOS_DIR / catalogue / filename).resolve()
    if not src_path.is_relative_to(PHOTOS_DIR.resolve()):
        raise HTTPException(status_code=404)
    if not thumb_path.exists():
        if not src_path.exists():
            raise HTTPException(status_code=404)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src_path) as img:
            img.thumbnail((600, 600))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(thumb_path, "JPEG", quality=85)
    return FileResponse(thumb_path)
