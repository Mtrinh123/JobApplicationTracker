"""Email every user with confirmed email and reminders on their due follow-ups.

Without SMTP settings the emails are printed instead. Run it daily with cron or Task Scheduler.
"""
from itertools import groupby

from main import due_jobs, send_email

due = due_jobs()
if not due:
    print("No follow-ups due.")

for email, jobs in groupby(due, key=lambda job: job["email"]):
    lines = [
        f"[{job['follow_up']}] {job['company']} - {job['role']} ({job['status']}) {job['url']}"
        for job in jobs
    ]
    send_email(email, f"{len(lines)} job follow-up(s) due", "Time to follow up on:\n\n" + "\n".join(lines))
    print(f"Sent {len(lines)} reminder(s) to {email}")
