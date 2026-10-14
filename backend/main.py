import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import smtplib
import socket
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import Literal

import psycopg
from fastapi import BackgroundTasks, Body, Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tracker:tracker@127.0.0.1:5433/tracker")
SESSION_DAYS = 30
# Cookies are shared across ports, so a generic name like "session" would clash with other localhost apps
COOKIE = "jobtracker_session"
# Set COOKIE_SECURE=1 when served over HTTPS so the browser never sends the session over plain http
COOKIE_SECURE = os.getenv("COOKIE_SECURE") == "1"
# Where the frontend lives, for links in emails
APP_URL = os.getenv("APP_URL", "http://localhost:3000").rstrip("/")
VERIFY_HOURS = 24
# What the frontend needs to know about the logged-in user
USER_FIELDS = "id, email, email_verified, reminders"

Status = Literal["saved", "applied", "interview", "offer", "rejected"]

SCHEMA = """
create table if not exists users (
    id serial primary key,
    email text not null unique,
    password_hash text not null,
    created_at timestamptz not null default now()
);
create table if not exists sessions (
    token_hash text primary key,
    user_id int not null references users(id) on delete cascade,
    created_at timestamptz not null default now()
);
create table if not exists jobs (
    id serial primary key,
    url text not null,
    company text not null,
    role text not null,
    status text not null default 'applied'
        check (status in ('saved', 'applied', 'interview', 'offer', 'rejected')),
    follow_up date,
    notes text not null default '',
    user_id int not null references users(id) on delete cascade,
    created_at timestamptz not null default now()
);
-- Local wall-clock time as typed, so calendar exports show the time the user entered
alter table jobs add column if not exists interview_at timestamp;
create table if not exists status_changes (
    job_id int not null references jobs(id) on delete cascade,
    status text not null,
    changed_at timestamptz not null default now()
);
-- Jobs from before status history existed start their history when they were added
insert into status_changes (job_id, status, changed_at)
    select id, status, created_at from jobs j
    where not exists (select 1 from status_changes s where s.job_id = j.id);
-- Accounts from before email confirmation existed count as confirmed; new ones start unconfirmed
alter table users add column if not exists email_verified boolean not null default true;
alter table users alter column email_verified set default false;
alter table users add column if not exists reminders boolean not null default true;
create table if not exists email_verifications (
    token_hash text primary key,
    user_id int not null references users(id) on delete cascade,
    created_at timestamptz not null default now()
);
"""


def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)


@asynccontextmanager
async def lifespan(app):
    with db() as conn:
        conn.execute(SCHEMA)
    yield


# The frontend proxies /api to this app (next.config.mjs), so the browser sees one origin and needs no CORS
app = FastAPI(lifespan=lifespan)


# --- Accounts ---

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${key.hex()}"


def check_password(password, stored):
    salt = bytes.fromhex(stored.split("$")[0])
    return hmac.compare_digest(hash_password(password, salt), stored)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def send_email(to, subject, body):
    """Send a plain-text email. Without SMTP settings (local dev) it's printed to the console instead."""
    if not os.getenv("SMTP_HOST"):
        print(f"\n--- Email to {to}: {subject}\n{body}\n---", flush=True)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_FROM") or os.environ["SMTP_USER"]
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)


def send_verification(conn, user, background):
    """Replace any earlier link with a fresh one, and email it after the response has gone out."""
    token = secrets.token_urlsafe(32)
    conn.execute("delete from email_verifications where user_id = %s", (user["id"],))
    conn.execute(
        "insert into email_verifications (token_hash, user_id) values (%s, %s)", (token_hash(token), user["id"])
    )
    body = (
        "Confirm your email so Job Tracker can send your follow-up reminders:\n\n"
        f"{APP_URL}/api/verify-email?token={token}\n\n"
        f"The link works for {VERIFY_HOURS} hours. If you didn't create an account, you can ignore this email."
    )
    background.add_task(send_email, user["email"], "Confirm your email for Job Tracker", body)


def start_session(conn, user_id, response):
    token = secrets.token_urlsafe(32)
    conn.execute("delete from sessions where created_at < now() - make_interval(days => %s)", (SESSION_DAYS,))
    conn.execute("insert into sessions (token_hash, user_id) values (%s, %s)", (token_hash(token), user_id))
    response.set_cookie(
        COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=COOKIE_SECURE
    )


def current_user(session: str | None = Cookie(default=None, alias=COOKIE)):
    if session:
        with db() as conn:
            user = conn.execute(
                "select u.id, u.email, u.email_verified, u.reminders from sessions s join users u on u.id = s.user_id"
                " where s.token_hash = %s and s.created_at > now() - make_interval(days => %s)",
                (token_hash(session), SESSION_DAYS),
            ).fetchone()
        if user:
            return user
    raise HTTPException(401, "Please log in")


def verified_user(user=Depends(current_user)):
    """For the board: a confirmed email shows a real person signed up, not a bot with a made-up address."""
    if not user["email_verified"]:
        raise HTTPException(403, "Confirm your email first. The link is in your inbox")
    return user


class Credentials(BaseModel):
    email: str = Field(pattern=r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$", max_length=254)
    password: str = Field(min_length=8, max_length=200)


@app.post("/register", status_code=201)
def register(creds: Credentials, response: Response, background: BackgroundTasks):
    with db() as conn:
        try:
            user = conn.execute(
                f"insert into users (email, password_hash) values (%s, %s) returning {USER_FIELDS}",
                (creds.email.strip().lower(), hash_password(creds.password)),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "That email already has an account")
        start_session(conn, user["id"], response)
        send_verification(conn, user, background)
    return user


MAX_FAILS = 5
FAIL_WINDOW = 15 * 60
# ponytail: in memory and per process, so it resets on restart. Move it to the database if you run several workers
failed_logins = defaultdict(deque)


def too_many_fails(email, now=None):
    now = now or time.monotonic()
    fails = failed_logins[email]
    while fails and fails[0] < now - FAIL_WINDOW:
        fails.popleft()
    if not fails:
        del failed_logins[email]
    return len(fails) >= MAX_FAILS


@app.post("/login")
def login(creds: Credentials, response: Response):
    email = creds.email.strip().lower()
    # Keyed by account, not IP: behind the frontend proxy every request comes from the same address
    if too_many_fails(email):
        raise HTTPException(429, "Too many wrong passwords. Try again in 15 minutes")
    with db() as conn:
        user = conn.execute(f"select {USER_FIELDS}, password_hash from users where email = %s", (email,)).fetchone()
        if not user or not check_password(creds.password, user["password_hash"]):
            failed_logins[email].append(time.monotonic())
            raise HTTPException(401, "Wrong email or password")
        failed_logins.pop(email, None)
        start_session(conn, user["id"], response)
    del user["password_hash"]
    return user


@app.post("/logout", status_code=204)
def logout(response: Response, session: str | None = Cookie(default=None, alias=COOKIE)):
    if session:
        with db() as conn:
            conn.execute("delete from sessions where token_hash = %s", (token_hash(session),))
    response.delete_cookie(COOKIE)


@app.get("/me")
def me(user=Depends(current_user)):
    return user


class Settings(BaseModel):
    reminders: bool


@app.patch("/me")
def update_settings(settings: Settings, user=Depends(current_user)):
    with db() as conn:
        return conn.execute(
            f"update users set reminders = %s where id = %s returning {USER_FIELDS}", (settings.reminders, user["id"])
        ).fetchone()


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


@app.post("/me/password", status_code=204)
def change_password(change: PasswordChange, user=Depends(current_user), session: str = Cookie(alias=COOKIE)):
    with db() as conn:
        stored = conn.execute("select password_hash from users where id = %s", (user["id"],)).fetchone()
        # 403, not 401: a typo shouldn't log you out
        if not check_password(change.current_password, stored["password_hash"]):
            raise HTTPException(403, "Current password is wrong")
        conn.execute(
            "update users set password_hash = %s where id = %s", (hash_password(change.new_password), user["id"])
        )
        # Sign out every other device, in case a leaked password is why it's being changed
        conn.execute("delete from sessions where user_id = %s and token_hash <> %s", (user["id"], token_hash(session)))


@app.get("/verify-email")
def verify_email(token: str = ""):
    # Relative redirects, so they land on the frontend through the /api proxy; the board shows the result
    with db() as conn:
        found = conn.execute(
            "delete from email_verifications where token_hash = %s"
            " returning user_id, created_at > now() - make_interval(hours => %s) as fresh",
            (token_hash(token), VERIFY_HOURS),
        ).fetchone()
        if found and found["fresh"]:
            conn.execute("update users set email_verified = true where id = %s", (found["user_id"],))
            return RedirectResponse("/?verified=1", status_code=303)
    return RedirectResponse("/?verified=0", status_code=303)


@app.post("/verify-email/resend", status_code=204)
def resend_verification(background: BackgroundTasks, user=Depends(current_user)):
    if user["email_verified"]:
        raise HTTPException(409, "Your email is already confirmed")
    with db() as conn:
        recent = conn.execute(
            "select 1 from email_verifications where user_id = %s and created_at > now() - interval '1 minute'",
            (user["id"],),
        ).fetchone()
        if recent:
            raise HTTPException(429, "We just sent one. Check your inbox and spam folder, or try again in a minute")
        send_verification(conn, user, background)


@app.delete("/me", status_code=204)
def delete_account(response: Response, password: str = Body(embed=True), user=Depends(current_user)):
    with db() as conn:
        stored = conn.execute("select password_hash from users where id = %s", (user["id"],)).fetchone()
        # 403, not 401: a typo shouldn't log you out
        if not check_password(password, stored["password_hash"]):
            raise HTTPException(403, "Wrong password")
        # Jobs and sessions go with it (on delete cascade)
        conn.execute("delete from users where id = %s", (user["id"],))
    response.delete_cookie(COOKIE)


# --- Jobs ---

class JobIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: HttpUrl
    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    status: Status = "applied"
    follow_up: date | None = None
    interview_at: datetime | None = None
    notes: str = ""


class JobUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str | None = Field(default=None, min_length=1)
    role: str | None = Field(default=None, min_length=1)
    status: Status | None = None
    follow_up: date | None = None
    interview_at: datetime | None = None
    notes: str | None = None


CLEARABLE = {"follow_up", "interview_at"}


@app.get("/jobs")
def list_jobs(user=Depends(verified_user)):
    with db() as conn:
        return conn.execute(
            "select * from jobs where user_id = %s order by created_at desc", (user["id"],)
        ).fetchall()


@app.post("/jobs", status_code=201)
def create_job(job: JobIn, user=Depends(verified_user)):
    follow_up = job.follow_up or date.today() + timedelta(days=7)
    with db() as conn:
        row = conn.execute(
            "insert into jobs (url, company, role, status, follow_up, interview_at, notes, user_id)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s) returning *",
            (str(job.url), job.company, job.role, job.status, follow_up, job.interview_at, job.notes, user["id"]),
        ).fetchone()
        conn.execute("insert into status_changes (job_id, status) values (%s, %s)", (row["id"], row["status"]))
    return row


@app.patch("/jobs/{job_id}")
def update_job(job_id: int, job: JobUpdate, user=Depends(verified_user)):
    # Only the dates can be cleared, so null means "leave it" for the rest
    fields = {k: v for k, v in job.model_dump(exclude_unset=True).items() if v is not None or k in CLEARABLE}
    if not fields:
        raise HTTPException(400, "Nothing to update")
    query = sql.SQL("update jobs set {} where id = %s and user_id = %s returning *").format(
        sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)
    )
    with db() as conn, conn.transaction():
        old = conn.execute(
            "select status from jobs where id = %s and user_id = %s for update", (job_id, user["id"])
        ).fetchone()
        if not old:
            raise HTTPException(404, "Job not found")
        row = conn.execute(query, (*fields.values(), job_id, user["id"])).fetchone()
        if row["status"] != old["status"]:
            conn.execute("insert into status_changes (job_id, status) values (%s, %s)", (job_id, row["status"]))
    return row


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, user=Depends(verified_user)):
    with db() as conn:
        deleted = conn.execute("delete from jobs where id = %s and user_id = %s", (job_id, user["id"]))
        if deleted.rowcount == 0:
            raise HTTPException(404, "Job not found")


# --- Stats ---

RESPONDED = {"interview", "offer", "rejected"}


def summarize(history):
    """history: rows of {job_id, status, days}, days being how long the job sat in that status.

    A job counts as applied once it gets past "saved", and as answered once it
    reaches interview, offer or rejected.
    """
    reached = defaultdict(set)
    days = defaultdict(list)
    for row in history:
        reached[row["status"]].add(row["job_id"])
        days[row["status"]].append(row["days"])
    applied = set().union(*(reached[s] for s in ("applied", *RESPONDED)))
    responded = set().union(*(reached[s] for s in RESPONDED))
    return {
        "applied": len(applied),
        "responded": len(responded),
        "response_rate": round(len(responded) / len(applied), 2) if applied else None,
        # offer and rejected are where jobs end up, so time spent in them says nothing
        "avg_days": {s: round(sum(days[s]) / len(days[s]), 1) for s in ("saved", "applied", "interview") if days[s]},
    }


@app.get("/stats")
def stats(user=Depends(verified_user)):
    with db() as conn:
        history = conn.execute(
            "select s.job_id, s.status,"
            " extract(epoch from coalesce(lead(s.changed_at) over w, now()) - s.changed_at) / 86400 as days"
            " from status_changes s join jobs j on j.id = s.job_id where j.user_id = %s"
            " window w as (partition by s.job_id order by s.changed_at)",
            (user["id"],),
        ).fetchall()
    return summarize([{**row, "days": float(row["days"])} for row in history])


def due_jobs():
    """Active jobs whose follow-up date is today or earlier, grouped by user email. Used by remind.py."""
    with db() as conn:
        return conn.execute(
            "select j.*, u.email from jobs j join users u on u.id = j.user_id"
            " where j.follow_up <= %s and j.status in ('saved', 'applied', 'interview')"
            " and u.email_verified and u.reminders"
            " order by u.email, j.follow_up",
            (date.today(),),
        ).fetchall()


# --- Link lookup ---

class PageInfo(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta = {}
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and attrs.get("content"):
            key = attrs.get("property") or attrs.get("name")
            if key:
                self.meta[key.lower()] = attrs["content"]

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def check_public(url):
    """Refuse links that point into the server's own network (localhost, 10.x, 192.168.x, cloud metadata...)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(400, "Only web links can be looked up")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parts.hostname, None)}
    except OSError:
        raise HTTPException(502, "Couldn't read that page")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        ip = getattr(ip, "ipv4_mapped", None) or ip
        if not ip.is_global:
            raise HTTPException(400, "That address isn't allowed")


class PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


fetcher = urllib.request.build_opener(PublicRedirects)


def parse_posting(html):
    """Guess company and role from a posting's page title.

    Handles the common shapes like "Role at Company | Board" and
    "Company hiring Role". Anything else falls back to the first and second
    parts of the title.
    """
    page = PageInfo()
    page.feed(html)
    title = (page.meta.get("og:title") or page.title).strip()
    title = re.sub(r"^job application for\s+", "", title, flags=re.I)
    parts = [p.strip() for p in re.split(r"\s+[|\-–—]\s+", title) if p.strip()]
    first = parts[0] if parts else ""

    if " at " in first:
        role, company = first.split(" at ", 1)
    elif " hiring " in first:
        company, role = first.split(" hiring ", 1)
    else:
        role = first
        company = parts[1] if len(parts) > 1 else page.meta.get("og:site_name", "")
    return {"company": company.strip(), "role": role.strip()}


@app.get("/preview")
def preview(url: HttpUrl = Query(), user=Depends(verified_user)):
    # ponytail: the address is checked, then resolved again when fetched, so DNS rebinding could slip past.
    # Pin the checked IP if this ever runs next to anything sensitive
    check_public(str(url))
    req = urllib.request.Request(str(url), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with fetcher.open(req, timeout=10) as res:
            html = res.read(1_000_000).decode(res.headers.get_content_charset() or "utf-8", "replace")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Couldn't read that page")
    return parse_posting(html)
