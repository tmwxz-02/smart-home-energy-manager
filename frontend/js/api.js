// The only place that talks to the Python backend. Every request carries the
// current workspace ("home" or "demo") in the X-Workspace header.

const STORAGE_KEY = "shem.workspace";

function readWorkspace() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "demo" ? "demo" : "home";
  } catch {
    return "home";
  }
}

let workspace = readWorkspace();

export function hasStoredWorkspace() {
  try { return localStorage.getItem(STORAGE_KEY) !== null; } catch { return false; }
}

export function getWorkspace() {
  return workspace;
}

export function setWorkspace(value) {
  workspace = value === "demo" ? "demo" : "home";
  try { localStorage.setItem(STORAGE_KEY, workspace); } catch { /* private mode: keep in memory */ }
}

export class ApiError extends Error {
  constructor(message, status, details = []) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

export async function request(method, path, body) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: { "Content-Type": "application/json", "X-Workspace": workspace },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is start.bat (python app.py) still running?", 0);
  }
  let data = null;
  try { data = await response.json(); } catch { /* not JSON */ }
  if (!response.ok) {
    throw new ApiError(data?.error || `Request failed (${response.status})`, response.status, data?.details || []);
  }
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body = {}) => request("POST", path, body),
  put: (path, body = {}) => request("PUT", path, body),
};

// Build a query string, skipping empty values.
export function qs(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

// URL for a file download (CSV): the workspace travels as a query parameter.
export function downloadUrl(path, params = {}) {
  return `/api${path}${qs({ ...params, ws: workspace })}`;
}
