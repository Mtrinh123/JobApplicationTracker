"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Brand from "../brand";

export default function Settings() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  // One status line per section: { text, error }
  const [status, setStatus] = useState({});
  const [busy, setBusy] = useState("");
  const deleteDialog = useRef(null);

  useEffect(() => { api("/me").then(setUser).catch(() => router.replace("/")); }, []);

  const say = (section, text, error = false) => setStatus((s) => ({ ...s, [section]: { text, error } }));

  async function attempt(section, work) {
    setBusy(section);
    say(section, "");
    try {
      await work();
    } catch (e) {
      if (e.status === 401) return router.replace("/");
      say(section, e.message, true);
    } finally {
      setBusy("");
    }
  }

  const resend = () =>
    attempt("account", async () => {
      await api("/verify-email/resend", { method: "POST" });
      say("account", `Sent. Check ${user.email}, including the spam folder.`);
    });

  const toggleReminders = (e) => {
    const reminders = e.target.checked;
    attempt("reminders", async () => {
      setUser(await api("/me", { method: "PATCH", body: JSON.stringify({ reminders }) }));
      say("reminders", reminders ? "Reminder emails are on." : "Reminder emails are off.");
    });
  };

  function changePassword(e) {
    e.preventDefault();
    const form = e.target;
    const body = JSON.stringify(Object.fromEntries(new FormData(form)));
    attempt("password", async () => {
      await api("/me/password", { method: "POST", body });
      form.reset();
      say("password", "Password changed. You've been signed out on every other device.");
    });
  }

  function deleteAccount(e) {
    e.preventDefault();
    const body = JSON.stringify(Object.fromEntries(new FormData(e.target)));
    attempt("delete", async () => {
      await api("/me", { method: "DELETE", body });
      router.replace("/");
    });
  }

  async function logout() {
    await api("/logout", { method: "POST" }).catch(() => {});
    router.replace("/");
  }

  // A plain function, not a component: the live region must stay mounted for screen readers to announce changes
  const statusLine = (section) => (
    <p className={status[section]?.error ? "form-status error" : "form-status"} role="status">
      {status[section]?.text}
    </p>
  );

  if (!user) return null;

  return (
    <>
      <header className="nav">
        <Link href="/" className="brand-link" aria-label="Job Tracker, back to your board"><Brand /></Link>
        <div className="tools">
          <span className="who">{user.is_demo ? "Demo account" : user.email}</span>
          <Link href="/" className="button">Back to board</Link>
          <button onClick={logout}>Log out</button>
        </div>
      </header>

      <main className="settings">
        <h1>Settings</h1>
        {user.is_demo && (
          <p className="notice" role="status">
            This is a demo account, so there's no real email or password behind it. Log out to delete it, or create
            your own account to keep a board.
          </p>
        )}

        <section className="panel" aria-labelledby="account-title">
          <div className="panel-head">
            <h2 id="account-title">Account</h2>
            <p>The email you log in with and where reminders are sent.</p>
          </div>
          <div className="row">
            <span className="row-value">{user.email}</span>
            <span className={user.email_verified ? "badge ok" : "badge warn"}>
              {user.email_verified ? "Confirmed" : "Not confirmed"}
            </span>
          </div>
          {!user.email_verified && (
            <button type="button" onClick={resend} disabled={busy === "account"}>
              {busy === "account" ? "Sending..." : "Resend confirmation email"}
            </button>
          )}
          {statusLine("account")}
        </section>

        <section className="panel" aria-labelledby="reminders-title">
          <div className="panel-head">
            <h2 id="reminders-title">Email reminders</h2>
            <p>A daily email listing the jobs that are due for a follow-up.</p>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={user.reminders}
              onChange={toggleReminders}
              disabled={!user.email_verified || busy === "reminders"}
            />
            Email me when follow-ups are due
          </label>
          {!user.email_verified && <p className="note">Confirm your email first to get reminders.</p>}
          {statusLine("reminders")}
        </section>

        <section className="panel" aria-labelledby="password-title">
          <div className="panel-head">
            <h2 id="password-title">Password</h2>
            <p>Changing it signs you out everywhere else.</p>
          </div>
          <form className="stack" onSubmit={changePassword}>
            <label>
              Current password
              <input name="current_password" type="password" autoComplete="current-password" required />
            </label>
            <label>
              New password
              <input name="new_password" type="password" autoComplete="new-password" minLength={8} required />
              <small>At least 8 characters.</small>
            </label>
            <button className="primary" disabled={busy === "password"}>
              {busy === "password" ? "Saving..." : "Change password"}
            </button>
          </form>
          {statusLine("password")}
        </section>

        <section className="panel danger-zone" aria-labelledby="delete-section-title">
          <div className="panel-head">
            <h2 id="delete-section-title">Delete account</h2>
            <p>Permanently removes your account and every saved job. Export a CSV from the board first if you want a copy.</p>
          </div>
          <button type="button" className="danger" onClick={() => { say("delete", ""); deleteDialog.current.showModal(); }}>
            Delete account
          </button>
        </section>

        <dialog ref={deleteDialog} aria-labelledby="delete-title">
          <form className="auth" onSubmit={deleteAccount}>
            <h2 id="delete-title">Delete your account?</h2>
            <p>
              This permanently deletes <strong>{user.email}</strong> and all of your saved jobs. It can't be undone.
            </p>
            <label>
              Enter your password to confirm
              <input name="password" type="password" autoComplete="current-password" required />
            </label>
            {status.delete?.text && <p className="error" role="alert">{status.delete.text}</p>}
            <div className="actions">
              <button type="button" onClick={() => deleteDialog.current.close()}>Cancel</button>
              <button className="danger solid" disabled={busy === "delete"}>
                {busy === "delete" ? "Deleting..." : "Delete forever"}
              </button>
            </div>
          </form>
        </dialog>
      </main>
    </>
  );
}
