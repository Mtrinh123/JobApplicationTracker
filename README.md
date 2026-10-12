# 📋 Job Application Tracker

Paste a job link, track it through your pipeline, and never forget to follow up.

**Next.js** · **FastAPI** · **PostgreSQL**

## ✨ Features

| | |
|---|---|
| 🔗 **Smart add** | Paste a link and the company and role fill in |
| 🗂️ **Pipeline board** | Drag jobs between saved → applied → interview → offer / rejected |
| ⏰ **Reminders** | Follow-ups are highlighted on the board and can be emailed daily |
| 📝 **Notes** | Recruiter names, interview dates, salary |
| 🔍 **Search & export** | Filter by company or role, download a CSV |
| 🔐 **Accounts** | Private boards, hashed passwords, delete your account anytime |
| 🌙 **Dark mode** | Works on a phone too |

## 🧭 How it works

```mermaid
flowchart LR
    U([You]) --> FE["Next.js<br/>:3000"]
    FE --> BE["FastAPI<br/>:8000"]
    BE --> DB[("PostgreSQL<br/>:5433")]
    BE -.-> WEB(["Job posting"])
    R["remind.py<br/>daily"] --> DB
    R --> M[/"Email"/]
```

## 🚀 Quick start

Needs **Docker Desktop**, **Python 3.10+** and **Node 18+**.

```bash
# 1. Database
docker compose up -d

# 2. Backend (http://localhost:8000/docs)
cd backend
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Frontend (http://localhost:3000)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and create an account.

## 📁 Project layout

```
backend/
  main.py         API, login, database setup
  remind.py       Daily follow-up reminders
  test_main.py    Tests
frontend/app/
  page.js         Board
  landing.js      Login / sign up
docker-compose.yml
```

## ⏰ Reminders

```bash
cd backend
.venv\Scripts\python remind.py
```

To get them by email, set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` and `SMTP_PASSWORD`. For Gmail, use an [app password](https://myaccount.google.com/apppasswords).
To run it every day, schedule it with Windows Task Scheduler or cron.

## 🔌 API

Every route except `/register`, `/login` and `/logout` needs you to be logged in.

| Route | Does |
|---|---|
| `POST /register` · `/login` · `/logout` | Accounts |
| `GET` · `DELETE /me` | Your account (deleting needs `{password}`) |
| `GET` · `POST /jobs` | List or add jobs |
| `PATCH` · `DELETE /jobs/{id}` | Edit or remove a job |
| `GET /preview?url=` | Guess the company and role from a link |

Full interactive docs: http://localhost:8000/docs

## ⚙️ Settings

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql://tracker:tracker@127.0.0.1:5433/tracker` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `password authentication failed` | Another Postgres is answering. Use port **5433** |
| `Failed to fetch` | The backend isn't running |
| Keeps sending you to the login page | Open `localhost:3000`, not `127.0.0.1` |
| Link doesn't fill in | Some sites (LinkedIn, Workday) block it. Type the details in |

## 🗺️ Roadmap

- [x] Pipeline board, reminders, notes, search, CSV export
- [x] Auto-fill from the link, email reminders
- [x] Accounts and account deletion
- [ ] Interview dates with calendar export
- [ ] Stats: response rate and time spent in each stage
- [ ] Before going online: limit login attempts, HTTPS-only cookie, block private addresses in the link lookup
- [ ] Deploy (Vercel + Render/Fly.io)
