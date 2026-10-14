"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import Brand from "./brand";
import Landing from "./landing";

const STATUSES = ["saved", "applied", "interview", "offer", "rejected"];
const ACTIVE = ["saved", "applied", "interview"];

function localDate(daysFromNow = 0) {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toLocaleDateString("en-CA");
}

function download(text, type, filename) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type }));
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href));
}

function downloadCsv(jobs) {
  const cols = ["company", "role", "status", "follow_up", "interview_at", "url", "notes", "created_at"];
  // A leading = + - @ makes Excel run the cell as a formula, so prefix those with '
  const cell = (v) => `"${String(v ?? "").replace(/^[=+\-@]/, "'$&").replaceAll('"', '""')}"`;
  const rows = jobs.map((job) => cols.map((c) => cell(job[c])).join(","));
  download([cols.join(","), ...rows].join("\n"), "text/csv", `jobs-${localDate()}.csv`);
}

// "2026-10-20T14:00:00" style times have no timezone, so they're the user's local time. The .ics keeps
// them "floating" (no Z) so every calendar shows the time exactly as it was typed.
function downloadIcs(job) {
  const icsTime = (d) => d.toLocaleString("sv-SE").replace(" ", "T").replace(/[-:]/g, "");
  const text = (s) => s.replace(/[\\;,]/g, "\\$&").replace(/\r?\n/g, "\\n");
  const start = new Date(job.interview_at);
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Job Tracker//EN",
    "BEGIN:VEVENT",
    `UID:job-${job.id}-${icsTime(start)}@jobtracker`,
    `DTSTAMP:${new Date().toISOString().replace(/[-:]|\.\d+/g, "")}`,
    `DTSTART:${icsTime(start)}`,
    `DTEND:${icsTime(end)}`,
    `SUMMARY:${text(`Interview: ${job.company} (${job.role})`)}`,
    `DESCRIPTION:${text(`${job.url}\n\n${job.notes}`)}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");
  download(ics, "text/calendar", `interview-${job.company.replace(/\W+/g, "-")}.ics`);
}

export default function Home() {
  const [user, setUser] = useState(undefined);
  // null until the first load, so "No jobs yet" never flashes for someone who has jobs
  const [jobs, setJobs] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [lookingUp, setLookingUp] = useState(false);
  const [adding, setAdding] = useState(false);
  const [dropTarget, setDropTarget] = useState(null);
  const [notice, setNotice] = useState("");
  // Set when a demo visitor chooses "Create your own account", so the landing opens on the sign-up form
  const [wantsSignup, setWantsSignup] = useState(false);
  const [resendStatus, setResendStatus] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const deleteDialog = useRef(null);

  function fail(e) {
    if (e.status === 401) setUser(null);
    else setError(e.message);
  }

  const load = () => Promise.all([api("/jobs").then(setJobs), api("/stats").then(setStats)]).catch(fail);

  useEffect(() => { api("/me").then(setUser).catch(() => setUser(null)); }, []);

  // The confirmation link in the email lands here with ?verified=1 (or 0 if the link was bad or expired)
  useEffect(() => {
    const verified = new URLSearchParams(location.search).get("verified");
    if (verified === null) return;
    setNotice(
      verified === "1"
        ? "Email confirmed. Welcome to your board."
        : "That confirmation link is invalid or has expired. Log in and choose Resend email to get a new one."
    );
    history.replaceState(null, "", "/");
  }, []);
  useEffect(() => { if (user?.email_verified) load(); }, [user]);

  // The link is often opened in another tab. When the person comes back to this one, check again so the
  // board opens on its own instead of still asking them to confirm
  const waiting = user && !user.email_verified;
  useEffect(() => {
    if (!waiting) return;
    const recheck = () => {
      if (document.visibilityState !== "visible") return;
      api("/me").then((me) => me.email_verified && setUser(me)).catch(() => {});
    };
    window.addEventListener("focus", recheck);
    document.addEventListener("visibilitychange", recheck);
    return () => {
      window.removeEventListener("focus", recheck);
      document.removeEventListener("visibilitychange", recheck);
    };
  }, [waiting]);

  async function run(promise) {
    try {
      setError("");
      await promise;
      await load();
    } catch (e) {
      fail(e);
    }
  }

  function signedOut() {
    setJobs(null);
    setStats(null);
    setSearch("");
    setUser(null);
  }

  async function logout() {
    await api("/logout", { method: "POST" }).catch(() => {});
    signedOut();
  }

  async function leaveDemoToSignUp() {
    setWantsSignup(true);
    await logout();
  }

  async function resendEmail() {
    setResendStatus("Sending...");
    try {
      await api("/verify-email/resend", { method: "POST" });
      setResendStatus(`Sent. Check ${user.email}, including the spam folder.`);
    } catch (e) {
      setResendStatus(e.message);
    }
  }

  // For when the link was opened in another browser or tab: this one still thinks the email is unconfirmed
  async function checkAgain() {
    const me = await api("/me").catch(() => null);
    if (me?.email_verified) setUser(me);
    else setResendStatus("Not confirmed yet. Click the link in the email, then try again.");
  }

  // Same as in Settings: a wrong address can't be confirmed, so let them remove it and sign up again
  async function deleteAccount(e) {
    e.preventDefault();
    setDeleting(true);
    setDeleteError("");
    try {
      await api("/me", { method: "DELETE", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
      deleteDialog.current.close();
      signedOut();
    } catch (err) {
      if (err.status === 401) signedOut();
      else setDeleteError(err.message);
    }
    setDeleting(false);
  }

  function add(e) {
    e.preventDefault();
    const form = e.target;
    const body = JSON.stringify(Object.fromEntries(new FormData(form)));
    setAdding(true);
    run(api("/jobs", { method: "POST", body }).then(() => form.reset())).finally(() => setAdding(false));
  }

  async function autofill(e) {
    const input = e.target;
    const { company, role } = input.form.elements;
    if (!input.value || !input.checkValidity() || (company.value && role.value)) return;
    setLookingUp(true);
    try {
      const info = await api(`/preview?url=${encodeURIComponent(input.value)}`);
      company.value ||= info.company;
      role.value ||= info.role;
    } catch {
      // Lots of job boards block scrapers. Typing it in still works.
    }
    setLookingUp(false);
  }

  const update = (id, data) =>
    run(api(`/jobs/${id}`, { method: "PATCH", body: JSON.stringify(data) }));
  const remove = (id) => run(api(`/jobs/${id}`, { method: "DELETE" }));

  function drop(e, status) {
    e.preventDefault();
    setDropTarget(null);
    const job = jobs.find((j) => String(j.id) === e.dataTransfer.getData("text/plain"));
    if (job && job.status !== status) update(job.id, { status });
  }

  if (user === undefined) return null;
  if (!user) return <Landing onLogin={(u) => { setWantsSignup(false); setUser(u); }} notice={notice} startSignup={wantsSignup} />;

  if (!user.email_verified) {
    return (
      <>
        <header className="nav">
          <Brand as="h1" />
          <div className="tools">
            <span className="who">{user.email}</span>
            <button onClick={logout}>Log out</button>
          </div>
        </header>
        <main className="app">
          {notice && <p className="notice" role="status">{notice}</p>}
          <div className="verify">
            <p>
              <strong>Confirm your email to start.</strong> We sent a link to {user.email}. Your board opens once
              you click it.
            </p>
            <button type="button" className="primary" onClick={checkAgain}>I've confirmed it</button>
            <button type="button" onClick={resendEmail}>Resend email</button>
            <p className="verify-status" role="status">{resendStatus}</p>
          </div>

          <p className="verify-help">
            Wrong email, or it never arrived?{" "}
            <button type="button" className="link" onClick={() => { setDeleteError(""); deleteDialog.current.showModal(); }}>
              Delete this account
            </button>{" "}
            and sign up again.
          </p>

          <dialog ref={deleteDialog} aria-labelledby="delete-title">
            <form className="auth" onSubmit={deleteAccount}>
              <h2 id="delete-title">Delete your account?</h2>
              <p>
                This permanently deletes <strong>{user.email}</strong>. It can't be undone.
              </p>
              <label>
                Enter your password to confirm
                <input name="password" type="password" autoComplete="current-password" required />
              </label>
              {deleteError && <p className="error" role="alert">{deleteError}</p>}
              <div className="actions">
                <button type="button" onClick={() => deleteDialog.current.close()}>Cancel</button>
                <button className="danger solid" disabled={deleting}>
                  {deleting ? "Deleting..." : "Delete forever"}
                </button>
              </div>
            </form>
          </dialog>
        </main>
      </>
    );
  }

  const loaded = jobs !== null;
  const all = jobs ?? [];
  const today = localDate();
  const isDue = (job) => ACTIVE.includes(job.status) && job.follow_up && job.follow_up <= today;
  const due = all.filter(isDue);
  const weekAhead = localDate(7);
  const interviews = all
    .filter((j) => j.interview_at && j.interview_at.slice(0, 10) >= today && j.interview_at.slice(0, 10) <= weekAhead)
    .sort((a, b) => a.interview_at.localeCompare(b.interview_at));
  const when = (t) => new Date(t).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
  const query = search.toLowerCase();
  const shown = all.filter((j) => `${j.company} ${j.role}`.toLowerCase().includes(query));

  return (
    <>
      <header className="nav">
        <Brand as="h1" />
        <div className="tools">
          <input
            type="search"
            placeholder="Search company or role"
            aria-label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button onClick={() => downloadCsv(jobs)} disabled={!all.length}>Export CSV</button>
          <span className="who">{user.is_demo ? "Demo account" : user.email}</span>
          <Link href="/settings" className="button">Settings</Link>
          <button onClick={logout}>Log out</button>
        </div>
      </header>

      <main className="app">
        {notice && <p className="notice" role="status">{notice}</p>}

        {user.is_demo && (
          <div className="demo-banner">
            <p>
              <strong>You're trying the demo.</strong> These are sample jobs, so drag cards, add jobs and edit notes
              freely. Everything is deleted when you log out, or after a couple of hours.
            </p>
            <button type="button" className="primary" onClick={leaveDemoToSignUp}>Create your own account</button>
          </div>
        )}

        <form className="add" onSubmit={add}>
          <label className="url">
            Posting link
            <input name="url" type="url" placeholder="https://..." required onBlur={autofill} />
          </label>
          <label>
            Company
            <input name="company" required />
          </label>
          <label>
            Role
            <input name="role" required />
          </label>
          <button className="primary" disabled={adding}>{adding ? "Adding..." : "Add job"}</button>
        </form>
        <p className="hint" role="status">
          {lookingUp ? "Looking up the company and role..." : "Paste a link and we'll try to fill in the company and role."}
        </p>

        {error && <p className="error" role="alert">{error}</p>}

        {loaded && all.length === 0 && (
          <div className="empty">
            <p><strong>No jobs yet.</strong></p>
            <p>Paste a posting link above to add your first one. You can drag it between columns as things move along.</p>
          </div>
        )}
        {all.length > 0 && shown.length === 0 && (
          <div className="empty">
            <p><strong>No jobs match "{search}".</strong></p>
            <p>
              Search looks at company and role.{" "}
              <button type="button" className="link" onClick={() => setSearch("")}>Clear search</button>
            </p>
          </div>
        )}

        {due.length > 0 && (
          <div className="reminders due">
            <strong>Follow up today:</strong>{" "}
            {due.map((j) => `${j.company} (${j.role})`).join(", ")}
          </div>
        )}

        {interviews.length > 0 && (
          <div className="reminders">
            <strong>Interviews this week:</strong>{" "}
            {interviews.map((j) => `${j.company} ${when(j.interview_at)}`).join(", ")}
          </div>
        )}

        {stats && stats.applied > 0 && (
          <dl className="stats">
            <div><dt>Applied</dt><dd>{stats.applied}</dd></div>
            <div>
              <dt>Heard back</dt>
              <dd>{stats.responded} ({Math.round(stats.response_rate * 100)}%)</dd>
            </div>
            {Object.entries(stats.avg_days).map(([status, days]) => (
              <div key={status}><dt>Avg days in {status}</dt><dd>{days < 1 ? "<1" : days}</dd></div>
            ))}
          </dl>
        )}

        <div className="board" aria-busy={!loaded}>
          {STATUSES.map((status) => {
            const list = shown.filter((j) => j.status === status);
            return (
              <section
                key={status}
                className={dropTarget === status ? "column over" : "column"}
                onDragOver={(e) => { e.preventDefault(); setDropTarget(status); }}
                onDragLeave={(e) => !e.currentTarget.contains(e.relatedTarget) && setDropTarget(null)}
                onDrop={(e) => drop(e, status)}
              >
                <h2 className="column-head">{status} <span className="count">{list.length}</span></h2>
                {list.map((job) => (
                  <article
                    key={job.id}
                    className={isDue(job) ? "card due" : "card"}
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData("text/plain", job.id)}
                  >
                    <div className="card-head">
                      <h3>{job.company}</h3>
                      <a href={job.url} target="_blank" rel="noreferrer">
                        Posting<span className="sr-only"> for {job.company} (opens in a new tab)</span>
                      </a>
                    </div>
                    <span className="role">{job.role}</span>
                    {isDue(job) && <span className="tag due">Follow-up due</span>}

                    <select
                      aria-label={`Status for ${job.company}`}
                      value={job.status}
                      onChange={(e) => update(job.id, { status: e.target.value })}
                    >
                      {STATUSES.map((s) => <option key={s}>{s}</option>)}
                    </select>
                    <label className="follow">
                      Follow up
                      <input
                        type="date"
                        aria-label={`Follow up date for ${job.company}`}
                        key={job.follow_up}
                        defaultValue={job.follow_up || ""}
                        onBlur={(e) => e.target.value !== (job.follow_up || "") && update(job.id, { follow_up: e.target.value || null })}
                      />
                    </label>
                    {(job.status === "interview" || job.interview_at) && (
                      <label className="follow">
                        Interview
                        <input
                          type="datetime-local"
                          aria-label={`Interview time for ${job.company}`}
                          key={job.interview_at}
                          defaultValue={job.interview_at?.slice(0, 16) || ""}
                          onBlur={(e) =>
                            e.target.value !== (job.interview_at?.slice(0, 16) || "") &&
                            update(job.id, { interview_at: e.target.value || null })
                          }
                        />
                      </label>
                    )}
                    {job.interview_at && (
                      <button onClick={() => downloadIcs(job)}>
                        Add to calendar<span className="sr-only"> for the {job.company} interview</span>
                      </button>
                    )}

                    <details>
                      <summary>{job.notes ? "Notes" : "Add notes"}</summary>
                      <textarea
                        aria-label={`Notes for ${job.company}`}
                        defaultValue={job.notes}
                        placeholder="Recruiter name, interview dates, salary..."
                        onBlur={(e) => e.target.value !== job.notes && update(job.id, { notes: e.target.value })}
                      />
                    </details>

                    <div className="actions">
                      {ACTIVE.includes(job.status) && (
                        <button onClick={() => update(job.id, { follow_up: localDate(7) })}>
                          Followed up<span className="sr-only"> with {job.company}</span>
                        </button>
                      )}
                      <button className="danger" onClick={() => confirm(`Delete ${job.company}?`) && remove(job.id)}>
                        Delete<span className="sr-only"> {job.company}</span>
                      </button>
                    </div>
                  </article>
                ))}
              </section>
            );
          })}
        </div>
      </main>
    </>
  );
}
