import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, HttpUrl

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tracker:tracker@localhost:5433/tracker")

Status = Literal["saved", "applied", "interview", "offer", "rejected"]

SCHEMA = """
create table if not exists jobs (
    id serial primary key,
    url text not null,
    company text not null,
    role text not null,
    status text not null default 'applied'
        check (status in ('saved', 'applied', 'interview', 'offer', 'rejected')),
    follow_up date,
    created_at timestamptz not null default now()
)
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
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobIn(BaseModel):
    url: HttpUrl
    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    status: Status = "applied"
    follow_up: date | None = None


class JobUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1)
    role: str | None = Field(default=None, min_length=1)
    status: Status | None = None
    follow_up: date | None = None


@app.get("/jobs")
def list_jobs():
    with db() as conn:
        return conn.execute("select * from jobs order by created_at desc").fetchall()


@app.post("/jobs", status_code=201)
def create_job(job: JobIn):
    follow_up = job.follow_up or date.today() + timedelta(days=7)
    with db() as conn:
        return conn.execute(
            "insert into jobs (url, company, role, status, follow_up)"
            " values (%s, %s, %s, %s, %s) returning *",
            (str(job.url), job.company, job.role, job.status, follow_up),
        ).fetchone()


@app.patch("/jobs/{job_id}")
def update_job(job_id: int, job: JobUpdate):
    fields = job.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(400, "Nothing to update")
    query = sql.SQL("update jobs set {} where id = %s returning *").format(
        sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)
    )
    with db() as conn:
        row = conn.execute(query, (*fields.values(), job_id)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    return row


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int):
    with db() as conn:
        if conn.execute("delete from jobs where id = %s", (job_id,)).rowcount == 0:
            raise HTTPException(404, "Job not found")


@app.get("/reminders")
def reminders():
    with db() as conn:
        return conn.execute(
            "select * from jobs where follow_up <= current_date"
            " and status in ('saved', 'applied', 'interview') order by follow_up"
        ).fetchall()
