const STORAGE_KEY = "tollgate-admin-session";

export const loadSession = () => sessionStorage.getItem(STORAGE_KEY) ?? "";
export const saveSession = (token: string) => sessionStorage.setItem(STORAGE_KEY, token);
export const clearSession = () => sessionStorage.removeItem(STORAGE_KEY);

/** Exchanges admin credentials for a session token. Throws with a message fit for the login form. */
export async function requestSessionToken(username: string, password: string): Promise<string> {
  const response = await fetch("/api/v1/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const body = (await response.json().catch(() => ({}))) as { session_token?: string; error?: { message?: string } };
  if (!response.ok || !body.session_token) {
    throw new Error(body.error?.message ?? `Login failed (${response.status}). Check your credentials and try again.`);
  }
  return body.session_token;
}
