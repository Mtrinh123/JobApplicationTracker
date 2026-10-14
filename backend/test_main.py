"""Run with: python test_main.py"""
from fastapi import HTTPException

from main import (
    FAIL_WINDOW,
    MAX_FAILS,
    check_password,
    check_public,
    failed_logins,
    hash_password,
    parse_posting,
    summarize,
    too_many_fails,
    verified_user,
)


def page(title="", **meta):
    tags = "".join(f'<meta property="{k.replace("_", ":", 1)}" content="{v}">' for k, v in meta.items())
    return f"<html><head><title>{title}</title>{tags}</head></html>"


cases = [
    (page("Software Engineer at Acme | LinkedIn"), "Acme", "Software Engineer"),
    (page("Acme hiring Data Analyst in Raleigh, NC | LinkedIn"), "Acme", "Data Analyst in Raleigh, NC"),
    (page(og_title="Job Application for Backend Intern at Globex"), "Globex", "Backend Intern"),
    (page("Product Designer - Initech"), "Initech", "Product Designer"),
    (page("Frontend Developer – Hooli"), "Hooli", "Frontend Developer"),
    (page("Careers", og_site_name="Umbrella"), "Umbrella", "Careers"),
    (page(""), "", ""),
]

for html, company, role in cases:
    got = parse_posting(html)
    assert got == {"company": company, "role": role}, (html, got)

stored = hash_password("correct horse")
assert check_password("correct horse", stored)
assert not check_password("wrong horse", stored)
assert hash_password("correct horse") != stored, "salt should differ each time"

# Login limit: blocked after MAX_FAILS, free again once they age out
failed_logins["a@b.co"].extend([100.0] * MAX_FAILS)
assert too_many_fails("a@b.co", now=101.0)
assert not too_many_fails("a@b.co", now=100.0 + FAIL_WINDOW + 1)
assert "a@b.co" not in failed_logins

# Link lookup refuses the server's own network. IP literals, so no internet needed
for url in ["http://127.0.0.1/", "http://localhost:8000/docs", "http://169.254.169.254/", "http://10.0.0.1/",
            "http://[::1]/", "http://[::ffff:127.0.0.1]/", "file:///etc/passwd"]:
    try:
        check_public(url)
        raise AssertionError(f"{url} should be refused")
    except HTTPException:
        pass
check_public("http://8.8.8.8/")

history = [
    {"job_id": 1, "status": "applied", "days": 10},
    {"job_id": 1, "status": "interview", "days": 4},
    {"job_id": 2, "status": "saved", "days": 2},
    {"job_id": 2, "status": "applied", "days": 20},
    {"job_id": 3, "status": "saved", "days": 1},
]
assert summarize(history) == {
    "applied": 2, "responded": 1, "response_rate": 0.5,
    "avg_days": {"saved": 1.5, "applied": 15.0, "interview": 4.0},
}, summarize(history)
assert summarize([])["response_rate"] is None

confirmed = {"id": 1, "email_verified": True}
assert verified_user(confirmed) is confirmed
try:
    verified_user({"id": 2, "email_verified": False})
    raise AssertionError("an unconfirmed account should be kept off the board")
except HTTPException as e:
    assert e.status_code == 403

from datetime import date, timedelta

from remind import reminder

sneaky = {"company": "<b>Evil</b>\nCorp", "role": "Dev & Ops", "url": 'https://x.co/"><script>', "status": "applied",
          "follow_up": date.today() - timedelta(days=2)}
subject, text, page = reminder([sneaky])
assert "\n" not in subject and "Evil" in subject, subject
assert "<b>Evil" not in page and "&lt;b&gt;Evil" in page, "typed text must be escaped in the HTML email"
assert "<script>" not in page and "Dev &amp; Ops" in page
assert "2 days overdue" in page and "2 days overdue" in text

print(f"{len(cases)} parse cases, password, login limit, link lookup, stats, email confirmation and email escaping checks passed")
