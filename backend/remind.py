"""Print every user's due follow-ups, and email each user their list if SMTP is set up.

Run it daily with cron or Task Scheduler.
"""
import os
import smtplib
from email.message import EmailMessage
from itertools import groupby

from main import due_jobs

due = due_jobs()
if not due:
    print("No follow-ups due.")

for email, jobs in groupby(due, key=lambda job: job["email"]):
    lines = [
        f"[{job['follow_up']}] {job['company']} - {job['role']} ({job['status']}) {job['url']}"
        for job in jobs
    ]
    print(f"{email}:\n" + "\n".join(lines))

    if os.getenv("SMTP_HOST"):
        msg = EmailMessage()
        msg["Subject"] = f"{len(lines)} job follow-up(s) due"
        msg["From"] = os.environ["SMTP_USER"]
        msg["To"] = email
        msg.set_content("Time to follow up on:\n\n" + "\n".join(lines))
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))) as smtp:
            smtp.starttls()
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(msg)
        print(f"Emailed {email}")
