/**
 * API base URL — EC2 backend via nip.io
 * On Vercel: empty string uses /api proxy (vercel.json → nip.io) to avoid mixed-content.
 */
window.GRIDLOCK_API =
  window.GRIDLOCK_API ??
  (location.hostname.endsWith(".vercel.app") ? "" : "http://65.2.35.241.nip.io");

function apiUrl(path) {
  const base = (window.GRIDLOCK_API || "").replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return base ? `${base}${p}` : p;
}

window.apiUrl = apiUrl;
