# photoblog

A self-hosted photo blog built with Python and FastAPI. Drop images into directories, and the site updates automatically. No upload UI, no database to manage, no user accounts.

![Dark minimal photo blog](docs/screenshot.png)

## Features

- **Filesystem-driven** — add or remove photos by copying files, no admin panel needed
- **Auto-indexing** — a file watcher detects changes and re-indexes in the background
- **Justified-row grid** — photos fill each row at a uniform height, preserving aspect ratios
- **Fullscreen viewer** — click any photo to go fullscreen; swipe or use arrow keys to navigate
- **Lazy thumbnails** — generated on first request, cached on disk
- **PWA-ready** — installable on iOS and Android, works without browser chrome
- **Configurable branding** — one YAML file controls your name, tagline, and social links

## Requirements

- Python 3.12+
- (Optional) Docker + Docker Compose for production deployment

## Quick start

```bash
git clone https://github.com/your-username/photoblog.git
cd photoblog

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example config and fill in your details:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml`:

```yaml
site_name: "Your Name"
tagline: "Photography · @yourhandle"
instagram_url: "https://instagram.com/yourhandle"
facebook_url: "https://facebook.com/yourpage"
```

Start the server:

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

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

## Directory structure

```
photoblog/
  app/
    main.py          # FastAPI app, routes
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
  requirements.txt
  docker-compose.yml
  nginx.conf.example
```

## Running tests

Make sure the virtual environment is active, then use `python -m pytest` rather than the bare `pytest` command — this ensures the tests run with the same Python interpreter that has the dependencies installed.

```bash
source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pytest
```

To run a specific file:

```bash
python -m pytest tests/test_routes.py -v
```

The test suite uses an in-memory SQLite database and a temporary photos directory — no real files or running server are needed.

## License

MIT
