const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getApiUrl() {
  return API_URL;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("mesigo_token");
}

export function setToken(token: string) {
  localStorage.setItem("mesigo_token", token);
}

export function clearToken() {
  localStorage.removeItem("mesigo_token");
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message =
      (data as { error?: { message?: string } })?.error?.message ||
      (data as { detail?: string })?.detail ||
      `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data as T;
}
