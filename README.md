# 📋 Job Application Tracker

[![CI](https://github.com/Mtrinh123/JobApplicationTracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Mtrinh123/JobApplicationTracker/actions/workflows/ci.yml)

Paste a job link, track it through your pipeline, and never forget to follow up.

**Next.js** · **FastAPI** · **PostgreSQL** · deployed on **Vercel**, **Render** and **Neon**

### 🌐 [Open the live app](https://job-application-tracker-tau-orcin.vercel.app) and click **Try the demo**, no sign-up needed

> The API runs on Render's free plan and sleeps when idle, so the first load can take up to a minute.

![The board with sample jobs, follow-ups due, this week's interview and stats](docs/screenshots/board.png)

<details>
<summary>Landing page</summary>

![Landing page with login and the Try the demo button](docs/screenshots/landing.png)

</details>

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
| 🎮 **Demo** | One click opens a private sample board. Deleted on log out or after 2 hours |
| 🔐 **Accounts** | Private boards, password typed twice at signup, email must be confirmed before the board opens, hashed passwords, login lockout after 5 wrong tries |
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

**Live:** the browser only talks to Vercel, which forwards `/api` to the FastAPI service on Render. Render stores data in Postgres on Neon and sends email through Brevo.

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
docs/screenshots/ Images for this README
docker-compose.yml
render.yaml       Deploy the backend on Render, Database on Neon
.github/workflows/ci.yml  Tests + build on every push (see CI)
```

## ☁️ Deployment

Every push to `main` runs CI and redeploys the frontend and the API on their own.

| Part | Service (free plan) | Settings to set there |
|---|---|---|
| Frontend | **Vercel**, root directory `frontend` | `API_URL` = the Render address, e.g. `https://jobtracker-api-erta.onrender.com` |
| API | **Render**, from `render.yaml` (Blueprint) | `DATABASE_URL`, `APP_URL` (the Vercel address), `SMTP_*` |
| Database | **Neon** Postgres | Copy its connection string into Render's `DATABASE_URL` |
| Email | **Brevo** SMTP | `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=2525`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` |

Things learned setting it up:

- Vercel reads `API_URL` only when it builds. After changing it, **redeploy**.
- Render's free plan blocks the usual email ports (25, 465, 587), so Gmail fails with `Network is unreachable`. Brevo also listens on **2525**, which works.
- Brevo rejects logins from unknown servers (`Unauthorized IP address`). Allow Render's outbound IPs in Brevo under **Security → Authorized IPs**, or turn that check off.
- Tables are created when the API starts, so a new database needs no setup.
- Connection strings and keys go in each service's dashboard, never in `render.yaml` or the repo.

## ✅ CI (GitHub Actions)

1. Push to GitHub.
2. Open the repo's **Actions** tab. Each push shows up as a run.
3. ✅ green means both jobs passed. ❌ red: click the run, then the failed job, then the red step to read the error.

The badge at the top of this README shows the latest result on `main`.

**Run the same checks locally before pushing**

```bash
cd backend && python test_main.py
cd frontend && npm ci && npm run build
```

**If a check fails**

| Problem | Fix |
|---|---|
| `backend` fails but tests pass locally | A package is missing from `requirements.txt` |
| `frontend` fails at `npm ci` | `package-lock.json` is out of date. Run `npm install` and commit the lock file |
| `frontend` fails at `npm run build` | Run `npm run build` locally, it shows the same error |

## 📧 Email

The app sends two kinds of email: a **confirmation link** when someone signs up, and **daily follow-up reminders** listing each due job with how overdue it is. Both are branded HTML emails with a plain-text copy for email apps that don't show HTML. New accounts can't use the board until they click the confirmation link, which keeps out bots signing up with made-up addresses. Reminders only go to accounts that left them on in Settings.



```bash
cd backend
.venv\Scripts\python remind.py
```

Accounts created before email confirmation existed count as confirmed.

## 🔌 API

Every route except `/register`, `/login`, `/logout`, `/demo` and `/verify-email` needs you to be logged in. `/jobs`, `/stats` and `/preview` also need a confirmed email (403 otherwise).

| Route | Does |
|---|---|
| `POST /register` · `/login` · `/logout` | Accounts. Logging out of a demo deletes it |
| `POST /demo` | Start a demo: a throwaway account with a sample board, already logged in |
| `GET` · `PATCH` · `DELETE /me` | Your account. `PATCH {reminders}` saves settings; deleting needs `{password}` |
| `POST /me/password` | Change password (`{current_password, new_password}`), signs out other devices |
| `GET /verify-email?token=` | The link in the confirmation email. Redirects to the board |
| `POST /verify-email/resend` | Send a new confirmation link (once a minute) |
| `GET` · `POST /jobs` | List or add jobs |
| `PATCH` · `DELETE /jobs/{id}` | Edit or remove a job |
| `GET /stats` | Response rate and average days per stage |
| `GET /preview?url=` | Guess the company and role from a link (public addresses only) |

The frontend reaches all of these at `/api/...`.

Full interactive docs: http://localhost:8000/docs locally, or [live](https://jobtracker-api-erta.onrender.com/docs)

## ⚙️ Settings

| Variable | Default |
|---|---|
| `DATABASE_URL` (backend) | `postgresql://tracker:tracker@127.0.0.1:5433/tracker` |
| `COOKIE_SECURE` (backend) | off. Set to `1` when served over HTTPS |
| `APP_URL` (backend) | `http://localhost:3000`. The frontend's address, for links in emails |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (backend) | unset, so emails are printed. See [Email](#-email) |
| `SMTP_FROM` (backend) | `SMTP_USER`. The sender address people see |
| `API_URL` (frontend, read at build time) | `http://localhost:8000` |

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `password authentication failed` | Another Postgres is answering. Use port **5433** |
| Every action shows "Request failed" | The backend isn't running |
| Link doesn't fill in | Some sites (LinkedIn, Workday) block it. Type the details in |
| "Too many wrong passwords" | Wait 15 minutes, or restart the backend |
| No confirmation email arrives | Without `SMTP_*` set it's printed in the backend logs. With it set, check spam, then use **Resend email** |
| `Network is unreachable` in the logs when sending email | The host blocks email ports. Use Brevo on port 2525 (see Deployment above) |
| `Unauthorized IP address` when sending email | Allow the server's IP in Brevo, under Security → Authorized IPs |
| Signing up shows `405` | Vercel's `API_URL` points at the wrong place. Fix it, then redeploy |


## 🗺️ Roadmap

- [x] Pipeline board, reminders, notes, search, CSV export
- [x] Auto-fill from the link, email reminders
- [x] Accounts and account deletion
- [x] Interview dates with calendar export
- [x] Stats: response rate and time spent in each stage
- [x] Before going online: limit login attempts, HTTPS-only cookie, block private addresses in the link lookup
- [x] Deploy config (Render blueprint + Vercel)
- [x] Actually deploy it (Vercel + Render + Neon + Brevo)
- [x] Required email confirmation, branded HTML emails
- [x] One-click demo with a sample board
- [ ] Send the daily reminders on a schedule (GitHub Actions cron)
