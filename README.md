# JobApplicationTracker

A small app for keeping track of job applications while job hunting.

- Save a job posting with its link, company and role
- Move it through a pipeline: **saved → applied → interview → offer / rejected**
- Get reminded when it's time to follow up

**Stack:** Next.js (frontend) · FastAPI (backend) · PostgreSQL (database)

## How it works

```mermaid
flowchart LR
    U([You]) --> FE["Next.js board<br/>localhost:3000"]
    FE -- "REST / JSON" --> BE["FastAPI<br/>localhost:8000"]
    BE --> DB[("PostgreSQL in Docker<br/>localhost:5433")]
    R["remind.py<br/>(runs daily)"] --> DB
    R --> OUT[/"List of follow-ups due"/]
```

1. You add a job on the board. The frontend sends it to the backend.
2. The backend saves it in PostgreSQL with a follow-up date (7 days out by default).
3. The board shows every job in a column for its status. Jobs whose follow-up date has passed are highlighted and listed at the top.
4. `remind.py` runs on a schedule and prints the follow-ups that are due.

A job only needs a follow-up while it's still in play, so reminders cover **saved**, **applied** and **interview** and skip **offer** and **rejected**.

## Project layout

```
JobApplicationTracker/
├── docker-compose.yml     PostgreSQL database
├── backend/
│   ├── main.py            API and table setup
│   ├── remind.py          Prints due follow-ups
│   └── requirements.txt
└── frontend/
    └── app/
        ├── page.js        Pipeline board
        ├── layout.js
        └── globals.css
```

## Getting started

**You need:** Docker Desktop, Python 3.10+ and Node.js 18+.

### 1. Start the database

```
docker compose up -d
```

This runs PostgreSQL in Docker on port **5433**. It doesn't use 5432, so it won't clash with a Postgres already installed on your machine.

### 2. Start the backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

- API: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs

The `jobs` table is created automatically the first time the backend starts.

### 3. Start the frontend

In a second terminal:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

### Next time

Docker Desktop restarts the database on its own. You only need two terminals:

```
cd backend
.venv\Scripts\activate
uvicorn main:app --reload
```

```
cd frontend
npm run dev
```

## Settings

Both settings have defaults that work out of the box. Set them as environment variables if you need to change them.

| Variable | Default | Used by |
|---|---|---|
| `DATABASE_URL` | `postgresql://tracker:tracker@localhost:5433/tracker` | backend |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | frontend |

## API

| Method | Path | What it does |
|---|---|---|
| `GET` | `/jobs` | List all jobs, newest first |
| `POST` | `/jobs` | Add a job |
| `PATCH` | `/jobs/{id}` | Change a job's company, role, status or follow-up date |
| `DELETE` | `/jobs/{id}` | Remove a job |
| `GET` | `/reminders` | Jobs that need a follow-up today or earlier |

Example: add a job

```
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/jobs/123", "company": "Acme", "role": "Software Engineer"}'
```

`status` (default `applied`) and `follow_up` (default 7 days from today, as `YYYY-MM-DD`) are optional.

## Daily reminders

Run this from the `backend` folder to see which follow-ups are due:

```
.venv\Scripts\python remind.py
```

```
[2026-10-01] Globex - Intern (applied) https://example.com/jobs/456
```

To run it every day automatically:

- **Windows (Task Scheduler):** create a daily task.
  - Program: `C:\path\to\backend\.venv\Scripts\python.exe`
  - Arguments: `remind.py`
  - Start in: `C:\path\to\backend`
- **macOS/Linux (cron):** run `crontab -e` and add
  `0 9 * * * cd /path/to/backend && .venv/bin/python remind.py`

## Troubleshooting

| Problem | Fix |
|---|---|
| `password authentication failed for user "tracker"` | Another Postgres is answering. Check that `DATABASE_URL` uses port 5433 and that `docker compose up -d` is running. |
| The board shows `Failed to fetch` | The backend isn't running. Start it with `uvicorn main:app --reload`. |
| `docker compose` can't connect | Start Docker Desktop first. |

## Roadmap

- [ ] Fill in company and role from the posting link automatically
- [ ] Email or desktop notifications for reminders
- [ ] Notes for each application
- [ ] UI updates
