"use client";

import { useState } from "react";
import { api } from "./api";

export default function Landing({ onLogin }) {
  const [signup, setSignup] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = JSON.stringify(Object.fromEntries(new FormData(e.target)));
      onLogin(await api(signup ? "/register" : "/login", { method: "POST", body }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <main className="landing">
      <section className="pitch">
        <h1>Job Tracker</h1>
        <p>Keep every application in one place and never forget to follow up.</p>
        <ul>
          <li>Paste a posting link and the company and role fill in</li>
          <li>Drag jobs from saved to applied, interview and offer</li>
          <li>Get reminded when it's time to follow up</li>
          <li>Keep notes and export everything to CSV</li>
        </ul>
      </section>

      <form className="auth" onSubmit={submit}>
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
        {error && <p className="error">{error}</p>}
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
    </main>
  );
}
