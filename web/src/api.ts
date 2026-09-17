import type { Account, FolderTree, Thread, ThreadHead, User } from "./types";

function formatDetail(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object" || !("detail" in data)) {
    return fallback;
  }
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === "string") {
    if (detail === "login_taken") return "логин занят";
    if (detail === "invalid_credentials") return "неверный логин или пароль";
    if (detail === "gmail_oauth_not_configured") return "Gmail OAuth не настроен";
    if (detail === "imap_login_failed") return "не удалось войти в IMAP";
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const rec = item as { loc?: unknown; msg?: unknown; type?: unknown };
        const loc = Array.isArray(rec.loc)
          ? rec.loc.filter((p) => p !== "body" && p !== "query").join(".")
          : "";
        if (rec.type === "string_too_short" && loc.includes("password")) {
          return "Пароль: минимум 8 символов";
        }
        if (typeof rec.msg === "string") {
          return loc ? `${loc}: ${rec.msg}` : rec.msg;
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (res.status === 204) {
    return undefined as T;
  }
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!res.ok) {
    const err = new Error(formatDetail(data, res.statusText));
    (err as Error & { status: number }).status = res.status;
    throw err;
  }
  return data as T;
}

export const api = {
  me: () => request<User>("/api/v1/me"),
  login: (login: string, password: string) =>
    request<User>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ login, password }) }),
  register: (login: string, password: string) =>
    request("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ login, password }) }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  accounts: () => request<Account[]>("/api/v1/mail/accounts"),
  createYandex: (email: string, app_password: string) =>
    request<Account>("/api/v1/mail/accounts", {
      method: "POST",
      body: JSON.stringify({ provider: "yandex", email, app_password }),
    }),
  gmailStart: () => request<{ authorization_url: string }>("/api/v1/mail/accounts/gmail/start", { method: "POST" }),
  patchAccount: (id: string, body: { unified?: boolean; is_default_compose?: boolean }) =>
    request<Account>(`/api/v1/mail/accounts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  folders: () => request<FolderTree[]>("/api/v1/mail/folders"),
  threads: (folder: string, q: string) => {
    const params = new URLSearchParams({ folder });
    if (q.trim()) params.set("q", q.trim());
    return request<ThreadHead[]>(`/api/v1/mail/threads?${params.toString()}`);
  },
  thread: (id: string) => request<Thread>(`/api/v1/mail/threads/${id}`),
  read: (id: string, body: { seen?: boolean; flagged?: boolean; message_id?: string }) =>
    request(`/api/v1/mail/threads/${id}/read`, { method: "POST", body: JSON.stringify(body) }),
  trash: (id: string) => request(`/api/v1/mail/messages/${id}/trash`, { method: "POST" }),
  archive: (id: string) => request(`/api/v1/mail/messages/${id}/archive`, { method: "POST" }),
  emptyTrash: () => request("/api/v1/mail/folders/trash/empty", { method: "POST" }),
  compose: (body: {
    account_id: string;
    to: string[];
    cc?: string[];
    subject: string;
    body_html: string;
    in_reply_to?: string;
    forward_of?: string;
    draft?: boolean;
  }) => request("/api/v1/mail/messages", { method: "POST", body: JSON.stringify(body) }),
};
