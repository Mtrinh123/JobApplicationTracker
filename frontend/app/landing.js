"use client";

import { useState } from "react";
import { api } from "./api";
import Brand from "./brand";

// Sample jobs for the board preview. Decorative only, so it's hidden from screen readers.
const PREVIEW = [
  ["Saved", [["Initech", "Product Designer"]]],
  ["Applied", [["Acme", "Software Engineer", "Follow-up due"], ["Umbrella", "Data Analyst"]]],
  ["Interview", [["Globex", "Backend Intern", "Thu 2:00 PM"]]],
  ["Offer", [["Hooli", "Frontend Developer"]]],
];

export default function Landing({ onLogin, notice, startSignup = false }) {
  const [signup, setSignup] = useState(startSignup);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    const { confirm, ...creds } = Object.fromEntries(new FormData(e.target));
    // Only catches typos, so it stays in the browser and the API never sees it
    if (signup && confirm !== creds.password) {
      setError("The passwords don't match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = JSON.stringify(creds);
      onLogin(await api(signup ? "/register" : "/login", { method: "POST", body }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  async function tryDemo() {
    setBusy(true);
    setError("");
    try {
      onLogin(await api("/demo", { method: "POST" }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <>
      <header className="nav">
        <Brand />
      </header>

      <main className="landing">
        <section className="hero">
          <div className="pitch">
            <h1>Keep every application in one place.</h1>
            <p className="lead">Paste a job link, move it through your pipeline, and never forget to follow up.</p>
            <ul>
              <li>Paste a posting link and the company and role fill in</li>
              <li>Drag jobs from saved to applied, interview and offer</li>
              <li>Get reminded when it's time to follow up</li>
              <li>Keep notes and export everything to CSV</li>
              <li>Add interviews to your calendar and see your response rate</li>
            </ul>
            <div className="demo-cta">
              <button type="button" onClick={tryDemo} disabled={busy}>Try the demo</button>
              <span>No sign-up. Opens a sample board you can play with.</span>
            </div>
          </div>

          <form className="auth" onSubmit={submit}>
            {notice && <p className="notice" role="status">{notice}</p>}
            <h2>{signup ? "Create an account" : "Log in"}</h2>
            <label>
              Email
              <input name="email" type="email" autoComplete="email" required />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                minLength={8}
                autoComplete={signup ? "new-password" : "current-password"}
                required
              />
            </label>
            {signup && <small>At least 8 characters.</small>}
            {signup && (
              <label>
                Confirm password
                <input name="confirm" type="password" minLength={8} autoComplete="new-password" required />
              </label>
            )}
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary" disabled={busy}>
              {busy ? "One moment..." : signup ? "Create account" : "Log in"}
            </button>
            <p className="switch">
              {signup ? "Already have an account?" : "New here?"}{" "}
              <button type="button" className="link" onClick={() => { setSignup(!signup); setError(""); }}>
                {signup ? "Log in" : "Create an account"}
              </button>
            </p>
          </form>
        </section>

        <div className="preview" aria-hidden="true">
          <p className="preview-label">
            Example board <span>Sample jobs. Your own board starts empty when you sign up.</span>
          </p>
          <div className="preview-board">
            {PREVIEW.map(([status, cards]) => (
              <div key={status} className="preview-column">
                <div className="column-head">
                  {status} <span className="count">{cards.length}</span>
                </div>
                {cards.map(([company, role, note]) => (
                  <div key={company} className="card">
                    <strong>{company}</strong>
                    <span className="role">{role}</span>
                    {note && <span className={note.startsWith("Follow") ? "tag due" : "tag"}>{note}</span>}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
