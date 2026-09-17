import DOMPurify from "dompurify";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { PRODUCT_NAME } from "../brand";
import type { Account, FolderTree, Message, Thread, ThreadHead, User } from "../types";

type ComposeMode = {
  open: boolean;
  accountId: string;
  to: string;
  subject: string;
  html: string;
  inReplyTo?: string;
  forwardOf?: string;
  draft: boolean;
};

function sanitize(html: string): string {
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ["img", "picture", "source"],
    ADD_ATTR: ["src", "srcset", "alt", "width", "height"],
    ALLOWED_URI_REGEXP:
      /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
  });
}

function providerName(provider: string): string {
  if (provider === "gmail") return "Gmail";
  if (provider === "yandex") return "Яндекс";
  return provider;
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ProviderBadge({ provider }: { provider?: string }) {
  if (!provider) return null;
  const kind = provider === "gmail" || provider === "yandex" ? provider : "";
  return <span className={`provider-badge ${kind}`}>{providerName(provider)}</span>;
}

const PRIMARY_FOLDERS = new Set(["inbox", "sent", "drafts", "trash", "archive", "spam"]);

function isInboxFolder(folderId: string): boolean {
  return folderId === "inbox" || folderId.endsWith(":inbox");
}

function senderDomain(addr: string): string {
  const angle = addr.match(/<([^>]+)>/);
  const email = (angle ? angle[1] : addr).trim();
  const at = email.lastIndexOf("@");
  if (at <= 0 || at === email.length - 1) return "";
  return email
    .slice(at + 1)
    .toLowerCase()
    .replace(/[>\s]+$/g, "");
}

export default function MailApp({ user }: { user: User }) {
  const nav = useNavigate();
  const [trees, setTrees] = useState<FolderTree[]>([]);
  const [folder, setFolder] = useState("inbox");
  const [query, setQuery] = useState("");
  const [q, setQ] = useState("");
  const [heads, setHeads] = useState<ThreadHead[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [thread, setThread] = useState<Thread | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [compose, setCompose] = useState<ComposeMode | null>(null);
  const [error, setError] = useState("");
  const [moreOpen, setMoreOpen] = useState(false);
  const [domainTab, setDomainTab] = useState("all");

  const defaultAccount = useMemo(
    () => accounts.find((a) => a.is_default_compose) || accounts[0],
    [accounts],
  );

  const domainTabs = useMemo(() => {
    if (!isInboxFolder(folder)) return [];
    const counts = new Map<string, number>();
    for (const head of heads) {
      const domain = senderDomain(head.from_addr);
      if (!domain) continue;
      counts.set(domain, (counts.get(domain) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ru"));
  }, [folder, heads]);

  const visibleHeads = useMemo(() => {
    if (!isInboxFolder(folder) || domainTab === "all") return heads;
    return heads.filter((head) => senderDomain(head.from_addr) === domainTab);
  }, [folder, heads, domainTab]);

  const loadFolders = useCallback(async () => {
    setTrees(await api.folders());
    setAccounts(await api.accounts());
  }, []);

  const loadThreads = useCallback(async () => {
    setHeads(await api.threads(folder, q));
  }, [folder, q]);

  useEffect(() => {
    loadFolders().catch((err) => setError(String(err)));
  }, [loadFolders]);

  useEffect(() => {
    loadThreads().catch((err) => setError(String(err)));
    const t = window.setInterval(() => {
      loadThreads().catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(t);
  }, [loadThreads]);

  useEffect(() => {
    setDomainTab("all");
  }, [folder]);

  useEffect(() => {
    if (!active) {
      setThread(null);
      return;
    }
    api
      .thread(active)
      .then(setThread)
      .catch((err) => setError(String(err)));
  }, [active]);

  async function openThread(id: string) {
    setActive(id);
    try {
      await api.read(id, { seen: true });
    } catch {
      /* still open */
    }
  }

  function startCompose(partial: Partial<ComposeMode> = {}) {
    if (!defaultAccount && !partial.accountId) {
      setError("Сначала подключите ящик.");
      nav("/settings");
      return;
    }
    setCompose({
      open: true,
      accountId: partial.accountId || defaultAccount!.id,
      to: partial.to || "",
      subject: partial.subject || "",
      html: partial.html || "<p></p>",
      inReplyTo: partial.inReplyTo,
      forwardOf: partial.forwardOf,
      draft: false,
    });
  }

  function reply(msg: Message) {
    const to = msg.from_addr;
    startCompose({
      accountId: msg.account_id,
      to,
      subject: msg.subject.toLowerCase().startsWith("re:") ? msg.subject : `Re: ${msg.subject}`,
      inReplyTo: msg.id,
      html: "<p></p>",
    });
  }

  function forward(msg: Message) {
    const quoted = msg.body_html || `<pre>${msg.body_text}</pre>`;
    startCompose({
      accountId: msg.account_id,
      subject: msg.subject.toLowerCase().startsWith("fwd:") ? msg.subject : `Fwd: ${msg.subject}`,
      forwardOf: msg.id,
      html: `<p></p><blockquote>${quoted}</blockquote>`,
    });
  }

  async function send(draft = false) {
    if (!compose) return;
    const to = compose.to
      .split(/[,;]/)
      .map((s) => s.trim())
      .filter(Boolean);
    await api.compose({
      account_id: compose.accountId,
      to,
      subject: compose.subject,
      body_html: compose.html,
      in_reply_to: compose.inReplyTo,
      forward_of: compose.forwardOf,
      draft,
    });
    setCompose(null);
    await loadThreads();
  }

  async function actOnLatest(kind: "trash" | "archive") {
    const msg = thread?.messages.find((m) => m.folder_canonical === folder) || thread?.messages[0];
    if (!msg) return;
    if (kind === "trash") await api.trash(msg.id);
    else await api.archive(msg.id);
    setActive(null);
    await loadThreads();
  }

  async function star(msg: Message, flagged: boolean) {
    if (!thread) return;
    await api.read(thread.id, { flagged, message_id: msg.id });
    setThread(await api.thread(thread.id));
  }

  async function logout() {
    await api.logout();
    nav("/login");
  }

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">{PRODUCT_NAME}</div>
        <form
          className="search"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(query);
          }}
        >
          <input placeholder="Поиск (FTS)" value={query} onChange={(e) => setQuery(e.target.value)} />
        </form>
        <button type="button" className="primary" onClick={() => startCompose()}>
          Написать
        </button>
        <Link to="/settings">Ящики</Link>
        <div className="spacer" />
        <span className="muted">
          {user.login} · {user.role}
        </span>
        <button type="button" onClick={logout}>
          Выход
        </button>
      </header>
      <div className="layout">
        <aside className="pane folders">
          {trees.map((tree, idx) => {
            const primary = tree.folders.filter((f) => PRIMARY_FOLDERS.has(f.canonical));
            const extra = tree.folders.filter((f) => !PRIMARY_FOLDERS.has(f.canonical));
            const showAllExtra = moreOpen;
            const extraToShow = showAllExtra ? extra : extra.filter((f) => f.id === folder);
            return (
              <div key={`${tree.kind}-${tree.label ?? idx}`}>
                <h3>{tree.kind === "split" ? tree.label : "Единое дерево"}</h3>
                {primary.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    className={folder === f.id ? "folder active" : "folder"}
                    onClick={() => {
                      setFolder(f.id);
                      setActive(null);
                    }}
                  >
                    {f.name}
                  </button>
                ))}
                {extraToShow.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    className={folder === f.id ? "folder extra active" : "folder extra"}
                    onClick={() => {
                      setFolder(f.id);
                      setActive(null);
                    }}
                  >
                    {f.name}
                  </button>
                ))}
                {extra.length ? (
                  <button
                    type="button"
                    className="folder more-toggle"
                    onClick={() => setMoreOpen((open) => !open)}
                  >
                    {showAllExtra ? "Свернуть остальные" : `Ещё (${extra.length})`}
                  </button>
                ) : null}
              </div>
            );
          })}
          {folder === "trash" || folder.endsWith(":trash") ? (
            <button type="button" className="danger" onClick={() => api.emptyTrash().then(loadThreads)}>
              Очистить корзину
            </button>
          ) : null}
        </aside>
        <section className="pane">
          <div className="list-head">Письма</div>
          {isInboxFolder(folder) && domainTabs.length ? (
            <div className="domain-tabs">
              <button
                type="button"
                className={domainTab === "all" ? "domain-tab active" : "domain-tab"}
                onClick={() => setDomainTab("all")}
              >
                Все ({heads.length})
              </button>
              {domainTabs.map(([domain, count]) => (
                <button
                  key={domain}
                  type="button"
                  className={domainTab === domain ? "domain-tab active" : "domain-tab"}
                  onClick={() => setDomainTab(domain)}
                >
                  @{domain} ({count})
                </button>
              ))}
            </div>
          ) : null}
          {visibleHeads.map((h) => (
            <button
              key={h.id}
              type="button"
              className={`thread${h.unread ? " unread" : ""}${active === h.id ? " active" : ""}`}
              onClick={() => openThread(h.id)}
            >
              <div className="thread-meta">
                <div className="from">
                  {h.flagged ? "★ " : ""}
                  {h.from_addr}
                </div>
                <div className="thread-side">
                  <ProviderBadge provider={h.provider} />
                  <span className="when">{formatWhen(h.last_at)}</span>
                </div>
              </div>
              <div className="subj">{h.subject}</div>
              <div className="snip">{h.snippet}</div>
            </button>
          ))}
          {!visibleHeads.length ? <p className="muted" style={{ padding: 12 }}>Пусто</p> : null}
        </section>
        <section className="pane thread-pane">
          {error ? <div className="error">{error}</div> : null}
          {thread ? (
            <>
              <div className="toolbar">
                <button type="button" onClick={() => thread.messages[0] && reply(thread.messages[thread.messages.length - 1])}>
                  Ответить
                </button>
                <button type="button" onClick={() => thread.messages[0] && forward(thread.messages[thread.messages.length - 1])}>
                  Переслать
                </button>
                <button type="button" className="danger" onClick={() => actOnLatest("trash")}>
                  Удалить
                </button>
                <button type="button" onClick={() => actOnLatest("archive")}>
                  В архив
                </button>
              </div>
              {thread.messages.map((msg) => (
                <article className="msg" key={msg.id}>
                  <header>
                    <div>
                      <div className="msg-badges">
                        <strong>{msg.from_addr}</strong>
                        <ProviderBadge provider={msg.provider} />
                      </div>
                      <div className="muted">{msg.subject}</div>
                      <div className="muted">{formatWhen(msg.sent_at)}</div>
                    </div>
                    <button type="button" onClick={() => star(msg, !msg.flags.includes("\\Flagged"))}>
                      {msg.flags.includes("\\Flagged") ? "★" : "☆"}
                    </button>
                  </header>
                  {msg.body_html ? (
                    <div className="html" dangerouslySetInnerHTML={{ __html: sanitize(msg.body_html) }} />
                  ) : (
                    <pre>{msg.body_text}</pre>
                  )}
                  {msg.attachments.map((a) => (
                    <div key={a.id}>
                      <a href={`/api/v1/mail/attachments/${a.id}`} target="_blank" rel="noreferrer">
                        {a.filename} ({a.size_bytes})
                      </a>
                    </div>
                  ))}
                </article>
              ))}
            </>
          ) : (
            <p className="muted">Выберите цепочку слева — справа вся переписка.</p>
          )}
        </section>
      </div>
      {compose ? (
        <form
          className="compose"
          onSubmit={(e) => {
            e.preventDefault();
            void send(false);
          }}
        >
          <select value={compose.accountId} onChange={(e) => setCompose({ ...compose, accountId: e.target.value })}>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.email}
              </option>
            ))}
          </select>
          <input placeholder="Кому" value={compose.to} onChange={(e) => setCompose({ ...compose, to: e.target.value })} />
          <input
            placeholder="Тема"
            value={compose.subject}
            onChange={(e) => setCompose({ ...compose, subject: e.target.value })}
          />
          <textarea
            rows={10}
            value={compose.html}
            onChange={(e) => setCompose({ ...compose, html: e.target.value })}
          />
          <div className="toolbar">
            <button className="primary" type="submit">
              Отправить
            </button>
            <button type="button" onClick={() => void send(true)}>
              Черновик
            </button>
            <button type="button" onClick={() => setCompose(null)}>
              Закрыть
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
