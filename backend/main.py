import hashlib
import hmac
import os
import re
import secrets
import urllib.request
from contextlib import asynccontextmanager
from datetime import date, timedelta
from html.parser import HTMLParser
from typing import Literal

import psycopg
from fastapi import Body, Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tracker:tracker@127.0.0.1:5433/tracker")
SESSION_DAYS = 30
# Cookies are shared across ports, so a generic name like "session" would clash with other localhost apps
COOKIE = "jobtracker_session"

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
"""


def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)


@asynccontextmanager
async def lifespan(app):
    with db() as conn:
        conn.execute(SCHEMA)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def start_session(conn, user_id, response):
    token = secrets.token_urlsafe(32)
    conn.execute("delete from sessions where created_at < now() - make_interval(days => %s)", (SESSION_DAYS,))
    conn.execute("insert into sessions (token_hash, user_id) values (%s, %s)", (token_hash(token), user_id))
    # ponytail: secure=False so the cookie works on http://localhost, set secure=True once it's served over HTTPS
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax")


def current_user(session: str | None = Cookie(default=None, alias=COOKIE)):
    if session:
        with db() as conn:
            user = conn.execute(
                "select u.id, u.email from sessions s join users u on u.id = s.user_id"
                " where s.token_hash = %s and s.created_at > now() - make_interval(days => %s)",
                (token_hash(session), SESSION_DAYS),
            ).fetchone()
        if user:
            return user
    raise HTTPException(401, "Please log in")


class Credentials(BaseModel):
    email: str = Field(pattern=r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$", max_length=254)
    password: str = Field(min_length=8, max_length=200)


@app.post("/register", status_code=201)
def register(creds: Credentials, response: Response):
    with db() as conn:
        try:
            user = conn.execute(
                "insert into users (email, password_hash) values (%s, %s) returning id, email",
                (creds.email.strip().lower(), hash_password(creds.password)),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "That email already has an account")
        start_session(conn, user["id"], response)
    return user


# ponytail: no login rate limit, scrypt slows guessing but add a limiter before putting this online
@app.post("/login")
def login(creds: Credentials, response: Response):
    with db() as conn:
        user = conn.execute(
            "select id, email, password_hash from users where email = %s", (creds.email.strip().lower(),)
        ).fetchone()
        if not user or not check_password(creds.password, user["password_hash"]):
            raise HTTPException(401, "Wrong email or password")
        start_session(conn, user["id"], response)
    return {"id": user["id"], "email": user["email"]}


@app.post("/logout", status_code=204)
def logout(response: Response, session: str | None = Cookie(default=None, alias=COOKIE)):
    if session:
        with db() as conn:
            conn.execute("delete from sessions where token_hash = %s", (token_hash(session),))
    response.delete_cookie(COOKIE)


@app.get("/me")
def me(user=Depends(current_user)):
    return user


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
    notes: str = ""


class JobUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str | None = Field(default=None, min_length=1)
    role: str | None = Field(default=None, min_length=1)
    status: Status | None = None
    follow_up: date | None = None
    notes: str | None = None


@app.get("/jobs")
def list_jobs(user=Depends(current_user)):
    with db() as conn:
        return conn.execute(
            "select * from jobs where user_id = %s order by created_at desc", (user["id"],)
        ).fetchall()


@app.post("/jobs", status_code=201)
def create_job(job: JobIn, user=Depends(current_user)):
    follow_up = job.follow_up or date.today() + timedelta(days=7)
    with db() as conn:
        return conn.execute(
            "insert into jobs (url, company, role, status, follow_up, notes, user_id)"
            " values (%s, %s, %s, %s, %s, %s, %s) returning *",
            (str(job.url), job.company, job.role, job.status, follow_up, job.notes, user["id"]),
        ).fetchone()


@app.patch("/jobs/{job_id}")
def update_job(job_id: int, job: JobUpdate, user=Depends(current_user)):
    # follow_up is the only column that can be cleared, so null means "leave it" for the rest
    fields = {k: v for k, v in job.model_dump(exclude_unset=True).items() if v is not None or k == "follow_up"}
    if not fields:
        raise HTTPException(400, "Nothing to update")
    query = sql.SQL("update jobs set {} where id = %s and user_id = %s returning *").format(
        sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)
    )
    with db() as conn:
        row = conn.execute(query, (*fields.values(), job_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    return row


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, user=Depends(current_user)):
    with db() as conn:
        deleted = conn.execute("delete from jobs where id = %s and user_id = %s", (job_id, user["id"]))
        if deleted.rowcount == 0:
            raise HTTPException(404, "Job not found")


def due_jobs():
    """Active jobs whose follow-up date is today or earlier, grouped by user email. Used by remind.py."""
    with db() as conn:
        return conn.execute(
            "select j.*, u.email from jobs j join users u on u.id = j.user_id"
            " where j.follow_up <= %s and j.status in ('saved', 'applied', 'interview')"
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
def preview(url: HttpUrl = Query(), user=Depends(current_user)):
    # ponytail: fetches any http(s) URL for a logged-in user, block private IPs before putting this online
    req = urllib.request.Request(str(url), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            html = res.read(1_000_000).decode(res.headers.get_content_charset() or "utf-8", "replace")
    except Exception:
        raise HTTPException(502, "Couldn't read that page")
    return parse_posting(html)
