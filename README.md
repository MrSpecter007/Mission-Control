# Mission Control

Internal platform operations dashboard for tracking websites, applications, infrastructure, deployments, and health across your estate.

## Overview

Mission Control answers:

- What platforms exist, and what state are they in?
- Where are they hosted, and what services run on them?
- Are they healthy right now?
- What work was done, when, and why?

---

## Features

| Area | Description |
|---|---|
| **Platforms** | Full CRUD with wizard onboarding. Framework, lifecycle, ownership, client. |
| **Health checks** | HTTP probes with monitored URL paths, response times, og:image preview. |
| **Dependencies** | Composer, npm, PyPI, WordPress plugin tracking via repository manifests. |
| **Updates feed** | GitHub commits/releases, framework releases, deployment lag alerts. |
| **Credentials vault** | Encrypted admin credentials per platform (Fernet AES). |
| **Activity Log** | Operational work history across the estate (see below). |
| **Clients** | Client records with industry, contacts, platform ownership. |

---

## Activity Log

### Purpose

A lightweight historical layer recording what work was done, what changed, why, and which platform was affected. It is an **operational work history**, not a task management or project tracking system.

### Model: `ActivityEntry`

| Field | Type | Description |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `platform` | FK → Platform (nullable) | Associated platform; null = estate-wide |
| `title` | CharField(300) | Short description of the activity |
| `description` | TextField | Optional longer explanation |
| `activity_type` | CharField (choices) | See activity types below |
| `occurred_at` | DateTimeField | When the activity took place |
| `is_milestone` | BooleanField | Visually highlights important events |
| `created_by` | FK → User (nullable) | Who logged the entry |
| `ref_url` | URLField | Commit URL, PR link, or external reference |
| `created_at` | DateTimeField (auto) | When the record was created |
| `updated_at` | DateTimeField (auto) | When the record was last modified |

### Activity Types

| Value | Label | Use for |
|---|---|---|
| `development` | Development | Code changes, features, bug fixes |
| `deployment` | Deployment | Releases pushed to an environment |
| `infrastructure` | Infrastructure | Server, hosting, network changes |
| `configuration` | Configuration | Config, environment variable, or settings changes |
| `maintenance` | Maintenance | Routine upkeep, updates, dependency bumps |
| `content` | Content | Content migrations, CMS updates, data changes |
| `operations` | Operations | Business or operational changes |
| `decision` | Decision | Architectural or strategic decisions |
| `incident` | Incident | Outages, errors, post-mortems |
| `milestone` | Milestone | Significant achievements or transitions |
| `other` | Other | Anything that doesn't fit above |

### Scopes

**Estate Activity** — `/activity/`  
All activity across Mission Control, newest first. Filterable by platform, type, and milestones.

**Platform Activity** — Platform detail page → Activity section  
Activity associated with one specific platform. Shows the 10 most recent entries with a "View all →" link.

**Milestones** — `/activity/?milestones=1`  
Estate-wide view filtered to `is_milestone=True` entries only.

### Manual Entries

1. From the **Activity Log** page: click **+ Log Activity** to open the add form.
2. From a **Platform detail** page: click **+ Log Activity** in the Activity section header to open the inline modal.
3. All entries support: title, type, platform (optional), date/time, description, reference URL, and milestone toggle.

### Automatic Logging

These events are logged automatically without user intervention:

| Event | Type | Trigger |
|---|---|---|
| Platform added to Mission Control | `operations` | Wizard completion |
| Platform lifecycle status changed | `operations` | Platform edit form save |
| Health status changed (e.g. DOWN, recovery) | `incident` / `operations` / `maintenance` | Health check run |
| Domain added to platform | `infrastructure` | Domain add form |
| Service added to platform | `infrastructure` | Service add form |

Automatic logging is wrapped in a silent try/except — failures never surface to the user or break the triggering action.

### Milestone Feed

An Atom feed of milestone entries is available at `/activity/milestones.atom`. Subscribe with any feed reader to track major estate milestones without logging into Mission Control.

The feed URL is also exposed as an `<link rel="alternate">` autodiscovery tag on the Activity Log page.

### Per-User Feed

The Activity Log filter bar includes a **contributor** dropdown that filters entries by the user who logged them. Clicking a username inline in any entry applies the same filter.

---

## Credentials Vault

Admin credentials per platform are stored encrypted using Fernet symmetric encryption (`cryptography` library).

Set `CREDENTIALS_KEY` in `.env` to a valid Fernet key. Generate one with:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If `CREDENTIALS_KEY` is not set, passwords are stored as plaintext (development fallback).

---

## Deployment

```bash
# Build and start
docker compose up --build -d

# Apply migrations
docker compose exec web python manage.py migrate

# Collect static files
docker compose exec web python manage.py collectstatic --noinput
```

Environment variables required in `.env`:

```
SECRET_KEY=
DEBUG=False
DATABASE_URL=
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=
CREDENTIALS_KEY=
GITHUB_TOKEN=        # optional, for repo/dependency scanning
```

---

## Running Tests

```bash
python manage.py test platforms
```
