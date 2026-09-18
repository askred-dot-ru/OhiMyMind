import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { AppHeader } from "../AppHeader";
import type { Account } from "../types";

function gmailRedirectUris(): string[] {
  const path = "/api/v1/mail/accounts/gmail/callback";
  const host = window.location.hostname;
  const primary =
    host === "localhost" || host === "127.0.0.1"
      ? `${window.location.origin}${path}`
      : `http://127.0.0.1:8798${path}`;
  const twin = primary.includes("://127.0.0.1")
    ? primary.replace("://127.0.0.1", "://localhost")
    : primary.replace("://localhost", "://127.0.0.1");
  return primary === twin ? [primary] : [primary, twin];
}

export default function Settings() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [domains, setDomains] = useState<string[]>([]);
  const [domainDraft, setDomainDraft] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const [rows, data] = await Promise.all([api.accounts(), api.unimportantDomains()]);
    setAccounts(rows);
    setDomains(data.domains);
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail") === "ok") setNotice("Gmail подключён.");
    load().catch((err) => setError(err instanceof Error ? err.message : "ошибка"));
  }, []);

  async function addYandex(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.createYandex(email, password);
      setEmail("");
      setPassword("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "не удалось подключить Яндекс");
    }
  }

  async function gmail() {
    setError("");
    try {
      const data = await api.gmailStart();
      window.location.href = data.authorization_url;
    } catch (err) {
      const status = (err as Error & { status?: number }).status;
      if (status === 409) setError("Gmail OAuth не настроен (GOOGLE_OAUTH_* пустые).");
      else setError(err instanceof Error ? err.message : "ошибка Gmail");
    }
  }

  async function toggleUnified(acc: Account) {
    await api.patchAccount(acc.id, { unified: !acc.unified });
    await load();
  }

  async function makeDefault(acc: Account) {
    await api.patchAccount(acc.id, { is_default_compose: true });
    await load();
  }

  async function addDomain(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const data = await api.addUnimportantDomain(domainDraft);
      setDomains(data.domains);
      setDomainDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "не удалось добавить домен");
    }
  }

  async function removeDomain(domain: string) {
    const data = await api.removeUnimportantDomain(domain);
    setDomains(data.domains);
  }

  return (
    <div className="settings-page">
      <AppHeader>
        <Link to="/">К потоку</Link>
      </AppHeader>
      <div className="settings">
      <h1>Ящики</h1>
      {notice ? <div className="muted">{notice}</div> : null}
      {error ? <div className="error">{error}</div> : null}
      {accounts.map((acc) => (
        <div className="account" key={acc.id}>
          <strong>
            {acc.email} · {acc.provider}
          </strong>
          <label>
            <input type="checkbox" checked={acc.unified} onChange={() => toggleUnified(acc)} /> единое дерево
          </label>
          <label>
            <input type="radio" name="from" checked={acc.is_default_compose} onChange={() => makeDefault(acc)} /> From по
            умолчанию
          </label>
        </div>
      ))}
      <form className="card" onSubmit={addYandex} style={{ width: "100%" }}>
        <h2>Яндекс (пароль приложения)</h2>
        <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input
          placeholder="пароль приложения"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button className="primary" type="submit">
          Подключить Яндекс
        </button>
      </form>
      <div className="card" style={{ width: "100%" }}>
        <h2>Не важные домены</h2>
        <p className="muted">Письма с этих From-доменов во входящих попадают во второй раздел списка.</p>
        {domains.length ? (
          <ul className="domain-edit-list">
            {domains.map((domain) => (
              <li key={domain}>
                <span>@{domain}</span>
                <button type="button" onClick={() => void removeDomain(domain)}>
                  Убрать
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Список пуст</p>
        )}
        <form className="domain-edit-form" onSubmit={addDomain}>
          <input
            placeholder="ozon.ru"
            value={domainDraft}
            onChange={(e) => setDomainDraft(e.target.value)}
          />
          <button className="primary" type="submit">
            Добавить
          </button>
        </form>
      </div>
      <div className="card" style={{ width: "100%" }}>
        <h2>Gmail (OAuth)</h2>
        <p className="muted">
          Клиент — <strong>Web application</strong>. Consent screen: статус <strong>Testing</strong>, не Publish.
          В Test users — тот Gmail, которым входите. Scope IMAP:{" "}
          <code>https://mail.google.com/</code>. Если Google пишет «не прошло проверку» — вы не в Test
          users или приложение опубликовано; для себя проверку Google проходить не нужно.
        </p>
        <p className="muted">
          Authorized redirect URIs — обе строки, без пробела в конце:
        </p>
        <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>
          {gmailRedirectUris().join("\n")}
        </pre>
        <button className="primary" type="button" onClick={gmail}>
          Подключить Gmail
        </button>
      </div>
      </div>
    </div>
  );
}
