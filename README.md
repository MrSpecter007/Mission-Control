# Mission Control

Internal platform operations dashboard for tracking websites, applications, infrastructure, health, and work history across your estate.

---

## What It Does

Mission Control gives you a single place to answer:

- What platforms exist and what state are they in?
- Where are they hosted and what services run on them?
- Are they healthy right now?
- What credentials are used to administer them?
- What work was done, when, and why?

---

## Features

| Area | Description |
|---|---|
| **Platforms** | Full CRUD with guided wizard onboarding. Tracks framework, lifecycle, ownership, and client. |
| **Health checks** | HTTP probes with monitored URL paths, response time tracking, og:image preview. |
| **Dependencies** | Composer, npm, PyPI, and WordPress plugin tracking via repository manifests. |
| **Updates feed** | GitHub commits/releases, framework release alerts, deployment lag warnings. |
| **Credentials vault** | Encrypted admin credentials per platform (Fernet AES-128). |
| **Activity Log** | Operational work history across the estate with auto-logging and milestone feed. |
| **Clients** | Client records with industry, contacts, and platform ownership. |
| **Infrastructure** | Host and service inventory linked to platforms. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.1, Python 3.13 |
| Database | PostgreSQL |
| Container | Docker + Docker Compose |
| Reverse proxy | nginx |
| Encryption | cryptography (Fernet) |
| Frontend | Vanilla JS, custom CSS |

---

## Getting Started

### Requirements

- Docker and Docker Compose
- Python 3.13+ (for local development without Docker)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your local values

# Run migrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Seed demo data (optional)
python manage.py seed_demo

# Start the dev server
python manage.py runserver
```

### Docker (Production)

```bash
# Build and start
docker compose -f docker-compose.prod.yml up --build -d

# Apply migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate --no-input

# Collect static files
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Create a superuser
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
SECRET_KEY=          # Django secret key (required)
DEBUG=False          # Set True for local dev
DATABASE_URL=        # postgres://user:pass@host:5432/dbname
ALLOWED_HOSTS=       # comma-separated, e.g. specter-ops.cloud
CSRF_TRUSTED_ORIGINS=https://specter-ops.cloud
CREDENTIALS_KEY=     # Fernet key for credential encryption (see below)
GITHUB_TOKEN=        # Optional — enables repo/dependency scanning
```

### Generating a Credentials Key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If `CREDENTIALS_KEY` is not set, passwords are stored as plaintext (development fallback only — always set this in production).

---

## Activity Log

A lightweight operational work history. Records what work was done, what changed, why, and which platform was affected.

### Activity Types

| Type | Use for |
|---|---|
| `development` | Code changes, features, bug fixes |
| `deployment` | Releases pushed to an environment |
| `infrastructure` | Server, hosting, network changes |
| `configuration` | Config, env var, or settings changes |
| `maintenance` | Routine upkeep, dependency bumps |
| `content` | Content migrations, CMS updates |
| `operations` | Business or operational changes |
| `decision` | Architectural or strategic decisions |
| `incident` | Outages, errors, post-mortems |
| `milestone` | Significant achievements or transitions |
| `other` | Anything else |

### Auto-Logged Events

These are logged automatically:

| Event | Type |
|---|---|
| Platform added | `operations` |
| Platform lifecycle changed | `operations` |
| Health status changed (down/recovery) | `incident` / `operations` |
| Domain added | `infrastructure` |
| Service added | `infrastructure` |

### Milestone Feed

Subscribe to significant milestones at `/activity/milestones.atom` in any feed reader.

---

## Credentials Vault

Admin credentials per platform are stored encrypted using Fernet symmetric encryption.

- Passwords are never stored in plaintext when `CREDENTIALS_KEY` is set
- The reveal endpoint (`POST /platforms/<slug>/credentials/<pk>/reveal/`) returns the decrypted value server-side only on explicit request
- Credentials are masked by default in the UI with a copy-to-clipboard button

---

## Running Tests

```bash
python manage.py test platforms
```

---

## Deployment

The production stack uses Docker Compose with a Python 3.13-slim image, gunicorn, and nginx as a reverse proxy.

**nginx** proxies `specter-ops.cloud` → `localhost:9001` → container port 8000.

To redeploy after a code change:

```bash
# On the VPS
cd /opt/mission-control

# Extract new code (if deploying via archive)
tar -xzf mc-deploy.tar.gz

# Rebuild and restart
docker compose -f docker-compose.prod.yml up --build -d

# Run any new migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate --no-input
```

---

## Project Structure

```
mission-control/
├── mission_control/        # Django project settings and URLs
├── platforms/              # Main app
│   ├── models.py           # Platform, ActivityEntry, PlatformCredential, etc.
│   ├── views.py            # All views including activity and credential endpoints
│   ├── forms.py            # ModelForms
│   ├── feeds.py            # Milestone Atom feed
│   ├── crypto.py           # Fernet encrypt/decrypt helpers
│   ├── updater/            # GitHub, framework, dependency, WordPress update logic
│   └── migrations/         # Database migrations
├── templates/
│   ├── base.html           # Global nav and layout
│   └── platforms/          # All page templates
├── static/mission-control/ # CSS and JS
├── deploy/                 # nginx config
├── Dockerfile
└── docker-compose.prod.yml
```
