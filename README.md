# photoblog

A self-hosted photo blog built with Python and FastAPI. Drop images into directories, and the site updates automatically. No upload UI, no database to manage.

![Dark minimal photo blog](docs/screenshot.png)

## Features

- **Filesystem-driven** — add or remove photos by copying files, no admin panel needed
- **Auto-indexing** — a file watcher detects changes and re-indexes in the background
- **Justified-row grid** — photos fill each row at a uniform height, preserving aspect ratios
- **Fullscreen viewer** — click any photo to go fullscreen; swipe or use arrow keys to navigate
- **Fade transitions** — smooth dissolve between photos and between pages
- **Lazy thumbnails** — generated on first request, cached on disk
- **PWA-ready** — installable on iOS and Android, works without browser chrome
- **Configurable branding** — one YAML file controls your name, tagline, and social links
- **Authentication** — original photos are protected behind login; gallery and thumbnails are public

## Requirements

- Python 3.12+
- (Optional) Docker + Docker Compose for production deployment

## Quick start

```bash
git clone https://github.com/your-username/photoblog.git
cd photoblog
bash setup.sh
```

The setup script will:
1. Create a virtual environment and install dependencies
2. Ask for your site name, tagline, and social links → writes `config.yaml`
3. Ask for an admin username and password → creates the first user in the database

Then start the server:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Authentication

The `/photos/` route (original full-resolution files) requires login. Everything else — the splash page, gallery, catalogue pages, thumbnails, and display images — is public.

- **Login:** [http://localhost:8000/login](http://localhost:8000/login)
- **Logout:** [http://localhost:8000/logout](http://localhost:8000/logout)

Sessions last 30 days. To create additional admin users, re-run `setup.sh` — it will skip steps that are already done and only prompt for a new user if the username doesn't exist yet. Or add a user directly:

```python
# with venv activated, from the project root
python - <<'EOF'
from app.db import get_connection, create_schema, create_user
from app.auth import hash_password
conn = get_connection("photoblog.db")
create_schema(conn)
create_user(conn, username="newuser", password_hash=hash_password("yourpassword"))
conn.close()
EOF
```

## Adding photos

Create a subdirectory inside `photos/` for each catalogue. Each catalogue needs a `catalogue.yaml` file with at minimum a `title` field.

```
photos/
  tuscany-2024/
    catalogue.yaml
    DSC_001.jpg
    DSC_002.jpg
```

**`catalogue.yaml`** — all fields except `title` are optional:

```yaml
title: "Tuscany 2024"
date: 2024-08-15
location: "Tuscany, Italy"
description: "A week along the Tyrrhenian coast"
cover_image: DSC_001.jpg     # shown as card thumbnail on the homepage
tags:
  - travel
  - italy
```

The server picks up new photos automatically while running (1-second debounce). If the server is stopped, it re-indexes everything on startup.

### Per-photo metadata (optional)

Create a YAML sidecar with the same name as the image:

```yaml
# DSC_001.yaml
title: "Sunset over the sea"
caption: "From the cliffs above Cinque Terre"
date: 2024-08-16
location: "Cinque Terre"
tags:
  - sunset
```

Metadata priority: **sidecar YAML → EXIF → filename**.

### Splash screen background

Place a `hero.jpg` file directly inside `photos/`:

```
photos/
  hero.jpg          ← splash screen background
  tuscany-2024/
    ...
```

## Production deployment

A `docker-compose.yml` and an example nginx config are included.

```bash
docker compose up -d --build
```

The app binds to `127.0.0.1:8000`. Put nginx in front of it using the provided `nginx.conf.example` as a reference.

Photos, thumbnails, display images, and the database are bind-mounted as volumes — they persist across image rebuilds and you can drop photos in from the host without touching the container.

Run `bash setup.sh` once after the first deploy to configure branding and create the admin user.

## Directory structure

```
photoblog/
  app/
    main.py          # FastAPI app, routes
    auth.py          # password hashing, session management
    indexer.py       # filesystem scanner
    watcher.py       # watchdog integration
    db.py            # SQLite schema and queries
    templates/       # Jinja2 HTML templates
    static/          # PWA manifest, service worker, icons
  photos/            # your catalogues (gitignored)
  thumbnails/        # auto-generated (gitignored)
  display/           # reduced-resolution copies (gitignored)
  config.yaml        # your branding (gitignored)
  config.yaml.example
  setup.sh           # interactive setup script
  requirements.txt
  docker-compose.yml
  nginx.conf.example
```

## Running tests

```bash
source .venv/bin/activate
python -m pytest
```

Use `python -m pytest` rather than bare `pytest` to ensure tests run with the venv's Python.

To run a specific file:

```bash
python -m pytest tests/test_routes.py -v
```

The test suite uses an in-memory SQLite database and a temporary photos directory — no real files or running server are needed.

## License

MIT
