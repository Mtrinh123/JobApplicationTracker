"""Print applications that need a follow-up. Run it daily with cron or Task Scheduler."""
from main import reminders

due = reminders()
if not due:
    print("No follow-ups due.")
for job in due:
    print(f"[{job['follow_up']}] {job['company']} - {job['role']} ({job['status']}) {job['url']}")
