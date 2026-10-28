"""Email every user with confirmed email and reminders on their due follow-ups.

Without SMTP settings the emails are printed instead. Runs every morning from GitHub Actions
(.github/workflows/reminders.yml), or by hand: python remind.py
"""
import html
import os
import sys
from datetime import date
from itertools import groupby

from main import APP_URL, due_jobs, email_html, send_email


def when(day):
    days = (date.today() - day).days
    return "today" if days == 0 else f"{days} day{'s' * (days != 1)} overdue"


def job_row(job):
    # Everything here was typed by the user, so it's escaped
    company, role, url = (html.escape(job[k]) for k in ("company", "role", "url"))
    return f"""<tr><td style="padding:14px 0;border-top:1px solid #e3e5ea">
  <div style="font-size:15px;font-weight:600;color:#1b1c1f">{company}</div>
  <div style="font-size:14px;color:#3c4149;margin:2px 0 6px">{role}</div>
  <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#fff4e8;color:#b8621b;font-size:12px">Follow-up {when(job['follow_up'])}</span>
  <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#eef0fb;color:#4a55b8;font-size:12px">{job['status'].title()}</span>
  <a href="{url}" style="font-size:13px;color:#5e6ad2;margin-left:6px">View posting</a>
</td></tr>"""


def reminder(jobs):
    count = f"{len(jobs)} follow-up{'s' * (len(jobs) != 1)}"
    # Collapse whitespace: a line break typed into a company name would be an invalid email header
    names = ", ".join(" ".join(j["company"].split()) for j in jobs[:3])
    subject = f"{count} due: {names}{'...' if len(jobs) > 3 else ''}"
    body = (
        f"Time to follow up on {count}:\n\n"
        + "\n".join(f"- {j['company']}, {j['role']} ({j['status']}, follow-up {when(j['follow_up'])})\n  {j['url']}" for j in jobs)
        + "\n\nA short, friendly note to the recruiter or hiring manager keeps you on their radar. "
        f"Once you've sent it, set a new follow-up date on the card.\n\nOpen your board: {APP_URL}\n\n"
        f"Don't want these? Turn reminders off in Settings: {APP_URL}/settings"
    )
    html_body = email_html(
        "Time to follow up",
        [
            f"You have <strong>{count}</strong> due. A short, friendly note to the recruiter or hiring manager "
            "keeps you on their radar.",
        ],
        "Open your board",
        APP_URL,
        extra=(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px">'
            + "".join(job_row(j) for j in jobs)
            + "</table>"
            '<p style="margin:8px 0 24px;font-size:14px;line-height:1.6;color:#3c4149"><strong>Tip:</strong> '
            "after you follow up, set a new date on the card so you get reminded again if you don't hear back.</p>"
        ),
        footer=(
            "You're getting this because follow-up reminders are on. "
            f'<a href="{html.escape(APP_URL)}/settings" style="color:#5e6ad2">Turn them off in Settings</a>.'
        ),
    )
    return subject, body, html_body


if __name__ == "__main__":
    # Logs of a public repo's Actions runs are public: never print an email there
    if os.getenv("GITHUB_ACTIONS") and not os.getenv("SMTP_HOST"):
        sys.exit("SMTP_HOST is not set, so emails would be printed to the public log. Add the SMTP secrets first.")

    due = due_jobs()
    sent = failed = 0
    for email, jobs in groupby(due, key=lambda job: job["email"]):
        try:
            send_email(email, *reminder(list(jobs)))
            sent += 1
        except Exception as e:  # one bad address shouldn't stop everyone else's reminders
            failed += 1
            print(f"A reminder failed: {type(e).__name__}")
    # Counts only, no addresses or job details
    print(f"{len(due)} follow-up(s) due, emailed {sent} user(s), {failed} failed.")
    if failed:
        sys.exit(1)
