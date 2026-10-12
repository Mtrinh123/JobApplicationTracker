# 📋 Job Application Tracker

Paste a job link, track it through your pipeline, and never forget to follow up.

**Next.js** · **FastAPI** · **PostgreSQL**

## ✨ Features

| | |
|---|---|
| 🔗 **Smart add** | Paste a link and the company and role fill in |
| 🗂️ **Pipeline board** | Drag jobs between saved → applied → interview → offer / rejected |
| ⏰ **Reminders** | Follow-ups are highlighted on the board and can be emailed daily |
| 📅 **Interviews** | Set the time on the card, see this week's at the top, add it to your calendar (.ics) |
| 📊 **Stats** | Response rate and average days spent in each stage |
| 📝 **Notes** | Recruiter names, salary, anything else |
| 🔍 **Search & export** | Filter by company or role, download a CSV |
| 🔐 **Accounts** | Private boards, email confirmation, hashed passwords, login lockout after 5 wrong tries |
| ⚙️ **Settings** | Turn reminder emails on or off, change your password, delete your account |

## 🧭 How it works

```mermaid
flowchart LR
    U([You]) --> FE["Next.js<br/>:3000"]
    FE -- "/api" --> BE["FastAPI<br/>:8000"]
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

## 📁 Project layout

```
backend/
  main.py         API, login, database setup
  remind.py       Daily follow-up reminders
  test_main.py    Tests (python test_main.py)
frontend/
  next.config.mjs Forwards /api to the backend
  app/page.js     Board
  app/landing.js  Login / sign up
  app/settings/   Settings page
docker-compose.yml
render.yaml       Deploy the backend + database on Render

```

## 📧 Email

The app sends two kinds of email: a **confirmation link** when someone signs up, and **daily follow-up reminders**. Reminders only go to accounts that confirmed their email and left reminders on in Settings.


```bash
cd backend
.venv\Scripts\python remind.py
```

Accounts created before email confirmation existed count as confirmed.

## 🔌 API

Every route except `/register`, `/login`, `/logout` and `/verify-email` needs you to be logged in.

| Route | Does |
|---|---|
| `POST /register` · `/login` · `/logout` | Accounts |
| `GET` · `PATCH` · `DELETE /me` | Your account. `PATCH {reminders}` saves settings; deleting needs `{password}` |
| `POST /me/password` | Change password (`{current_password, new_password}`), signs out other devices |
| `GET /verify-email?token=` | The link in the confirmation email. Redirects to the board |
| `POST /verify-email/resend` | Send a new confirmation link (once a minute) |
| `GET` · `POST /jobs` | List or add jobs |
| `PATCH` · `DELETE /jobs/{id}` | Edit or remove a job |
| `GET /stats` | Response rate and average days per stage |
| `GET /preview?url=` | Guess the company and role from a link (public addresses only) |

The frontend reaches all of these at `/api/...`.

Full interactive docs: http://localhost:8000/docs

## ⚙️ Settings

| Variable | Default |
|---|---|
| `DATABASE_URL` (backend) | `postgresql://tracker:tracker@127.0.0.1:5433/tracker` |
| `COOKIE_SECURE` (backend) | off. Set to `1` when served over HTTPS |
| `APP_URL` (backend) | `http://localhost:3000`. The frontend's address, for links in emails |
| `SMTP_*` (backend) | unset, so emails are printed. See [Email](#-email) |
| `API_URL` (frontend, read at build time) | `http://localhost:8000` |

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `password authentication failed` | Another Postgres is answering. Use port **5433** |
| Every action shows "Request failed" | The backend isn't running |
| Link doesn't fill in | Some sites (LinkedIn, Workday) block it. Type the details in |
| "Too many wrong passwords" | Wait 15 minutes, or restart the backend |
| No confirmation email arrives | Without `SMTP_*` set it's printed in the backend terminal. With it set, check spam, then use Resend in Settings |


## 🗺️ Roadmap

- [x] Pipeline board, reminders, notes, search, CSV export
- [x] Auto-fill from the link, email reminders
- [x] Accounts and account deletion
- [x] Interview dates with calendar export
- [x] Stats: response rate and time spent in each stage
- [x] Before going online: limit login attempts, HTTPS-only cookie, block private addresses in the link lookup
- [x] Deploy config (Render blueprint + Vercel)
- [ ] Actually deploy it
