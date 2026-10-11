"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STATUSES = ["saved", "applied", "interview", "offer", "rejected"];
const ACTIVE = ["saved", "applied", "interview"];

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.status === 204 ? null : res.json();
}

export default function Home() {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");

  const load = () => api("/jobs").then(setJobs).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function run(promise) {
    try {
      setError("");
      await promise;
      await load();
    } catch (e) {
      setError(e.message);
    }
  }

  function add(e) {
    e.preventDefault();
    const form = e.target;
    const body = JSON.stringify(Object.fromEntries(new FormData(form)));
    run(api("/jobs", { method: "POST", body }).then(() => form.reset()));
  }

  const update = (id, data) =>
    run(api(`/jobs/${id}`, { method: "PATCH", body: JSON.stringify(data) }));
  const remove = (id) => run(api(`/jobs/${id}`, { method: "DELETE" }));

  const today = new Date().toLocaleDateString("en-CA");
  const isDue = (job) => ACTIVE.includes(job.status) && job.follow_up && job.follow_up <= today;
  const due = jobs.filter(isDue);

  return (
    <main>
      <h1>Job Tracker</h1>

      <form onSubmit={add}>
        <input name="url" type="url" placeholder="Job posting link" required />
        <input name="company" placeholder="Company" required />
        <input name="role" placeholder="Role" required />
        <button>Add</button>
      </form>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {due.length > 0 && (
        <div className="reminders">
          <strong>Follow up today:</strong>{" "}
          {due.map((j) => `${j.company} (${j.role})`).join(", ")}
        </div>
      )}

      <div className="board">
        {STATUSES.map((status) => (
          <section className="column" key={status}>
            <h2>{status}</h2>
            {jobs.filter((j) => j.status === status).map((job) => (
              <div className={isDue(job) ? "card due" : "card"} key={job.id}>
                <strong>{job.company}</strong>
                <span>{job.role}</span>
                <a href={job.url} target="_blank" rel="noreferrer">posting</a>
                <select value={job.status} onChange={(e) => update(job.id, { status: e.target.value })}>
                  {STATUSES.map((s) => <option key={s}>{s}</option>)}
                </select>
                <label>
                  Follow up{" "}
                  <input
                    type="date"
                    value={job.follow_up || ""}
                    onChange={(e) => update(job.id, { follow_up: e.target.value || null })}
                  />
                </label>
                <button onClick={() => confirm("Delete?") && remove(job.id)}>Delete</button>
              </div>
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}
