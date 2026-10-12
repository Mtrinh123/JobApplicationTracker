"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import Landing from "./landing";

const STATUSES = ["saved", "applied", "interview", "offer", "rejected"];
const ACTIVE = ["saved", "applied", "interview"];

function localDate(daysFromNow = 0) {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toLocaleDateString("en-CA");
}

function downloadCsv(jobs) {
  const cols = ["company", "role", "status", "follow_up", "url", "notes", "created_at"];
  // A leading = + - @ makes Excel run the cell as a formula, so prefix those with '
  const cell = (v) => `"${String(v ?? "").replace(/^[=+\-@]/, "'$&").replaceAll('"', '""')}"`;
  const rows = jobs.map((job) => cols.map((c) => cell(job[c])).join(","));
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([[cols.join(","), ...rows].join("\n")], { type: "text/csv" }));
  link.download = `jobs-${localDate()}.csv`;
  link.click();
}

export default function Home() {
  const [user, setUser] = useState(undefined);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [lookingUp, setLookingUp] = useState(false);
  const [dropTarget, setDropTarget] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const deleteDialog = useRef(null);

  function fail(e) {
    if (e.status === 401) setUser(null);
    else setError(e.message);
  }

  const load = () => api("/jobs").then(setJobs).catch(fail);

  useEffect(() => { api("/me").then(setUser).catch(() => setUser(null)); }, []);
  useEffect(() => { if (user) load(); }, [user]);

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
    setJobs([]);
    setSearch("");
    setUser(null);
  }

  async function logout() {
    await api("/logout", { method: "POST" }).catch(() => {});
    signedOut();
  }

  async function deleteAccount(e) {
    e.preventDefault();
    setDeleteError("");
    try {
      const body = JSON.stringify(Object.fromEntries(new FormData(e.target)));
      await api("/me", { method: "DELETE", body });
      signedOut();
    } catch (err) {
      setDeleteError(err.message);
    }
  }

  function add(e) {
    e.preventDefault();
    const form = e.target;
    const body = JSON.stringify(Object.fromEntries(new FormData(form)));
    run(api("/jobs", { method: "POST", body }).then(() => form.reset()));
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
  if (!user) return <Landing onLogin={setUser} />;

  const today = localDate();
  const isDue = (job) => ACTIVE.includes(job.status) && job.follow_up && job.follow_up <= today;
  const due = jobs.filter(isDue);
  const query = search.toLowerCase();
  const shown = jobs.filter((j) => `${j.company} ${j.role}`.toLowerCase().includes(query));

  return (
    <main>
      <header className="top">
        <h1>Job Tracker</h1>
        <div className="tools">
          <input
            type="search"
            placeholder="Search company or role"
            aria-label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button onClick={() => downloadCsv(jobs)} disabled={!jobs.length}>Export CSV</button>
          <span className="who">{user.email}</span>
          <button onClick={logout}>Log out</button>
          <button className="danger" onClick={() => { setDeleteError(""); deleteDialog.current.showModal(); }}>
            Delete account
          </button>
        </div>
      </header>

      <dialog ref={deleteDialog}>
        <form className="auth" onSubmit={deleteAccount}>
          <h2>Delete your account?</h2>
          <p>
            This permanently deletes <strong>{user.email}</strong> and all {jobs.length} of your
            saved jobs. It can't be undone. Export a CSV first if you want a copy.
          </p>
          <label>
            Enter your password to confirm
            <input name="password" type="password" autoComplete="current-password" required />
          </label>
          {deleteError && <p className="error">{deleteError}</p>}
          <div className="actions">
            <button type="button" onClick={() => deleteDialog.current.close()}>Cancel</button>
            <button className="danger solid">Delete forever</button>
          </div>
        </form>
      </dialog>

      <form className="add" onSubmit={add}>
        <input name="url" type="url" placeholder="Paste the job posting link" aria-label="Posting link" required onBlur={autofill} />
        <input name="company" placeholder={lookingUp ? "Looking up..." : "Company"} aria-label="Company" required />
        <input name="role" placeholder={lookingUp ? "Looking up..." : "Role"} aria-label="Role" required />
        <button className="primary">Add job</button>
      </form>

      {error && <p className="error">{error}</p>}

      {due.length > 0 && (
        <div className="reminders">
          <strong>Follow up today:</strong>{" "}
          {due.map((j) => `${j.company} (${j.role})`).join(", ")}
        </div>
      )}

      <div className="board">
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
              <h2>{status} <span className="count">{list.length}</span></h2>
              {list.map((job) => (
                <article
                  key={job.id}
                  className={isDue(job) ? "card due" : "card"}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData("text/plain", job.id)}
                >
                  <div className="card-head">
                    <strong>{job.company}</strong>
                    <a href={job.url} target="_blank" rel="noreferrer">Posting</a>
                  </div>
                  <span className="role">{job.role}</span>

                  <select aria-label="Status" value={job.status} onChange={(e) => update(job.id, { status: e.target.value })}>
                    {STATUSES.map((s) => <option key={s}>{s}</option>)}
                  </select>
                  <label className="follow">
                    Follow up
                    <input
                      type="date"
                      key={job.follow_up}
                      defaultValue={job.follow_up || ""}
                      onBlur={(e) => e.target.value !== (job.follow_up || "") && update(job.id, { follow_up: e.target.value || null })}
                    />
                  </label>

                  <details>
                    <summary>Notes{job.notes ? " *" : ""}</summary>
                    <textarea
                      defaultValue={job.notes}
                      placeholder="Recruiter name, interview dates, salary..."
                      onBlur={(e) => e.target.value !== job.notes && update(job.id, { notes: e.target.value })}
                    />
                  </details>

                  <div className="actions">
                    {ACTIVE.includes(job.status) && (
                      <button onClick={() => update(job.id, { follow_up: localDate(7) })}>Followed up</button>
                    )}
                    <button className="danger" onClick={() => confirm(`Delete ${job.company}?`) && remove(job.id)}>
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </section>
          );
        })}
      </div>
    </main>
  );
}
