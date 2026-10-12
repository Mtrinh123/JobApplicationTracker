export async function api(path, options = {}) {
  // Proxied to the backend by next.config.mjs
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join(", ")
      : body.detail;
    const error = new Error(detail || `Request failed (${res.status})`);
    error.status = res.status;
    throw error;
  }
  return res.status === 204 ? null : res.json();
}
