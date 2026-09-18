import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type RefObject } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { AppHeader } from "../AppHeader";
import { formatWhen } from "../datetime";
import { EmailHtml, EmailText } from "../EmailHtml";
import { MsgAttachments } from "../MsgAttachments";
import {
  Ico,
  IcoArchive,
  IcoDone,
  IcoForward,
  IcoImportant,
  IcoReply,
  IcoTrash,
  IcoUnimportant,
} from "../mailIcons";
import type { Account, FolderTree, Message, Thread, ThreadHead, User } from "../types";

function plainPreview(raw: string | null | undefined): string {
  if (!raw) return "";
  const node = document.createElement("textarea");
  node.innerHTML = raw;
  return (node.value || "")
    .replace(/[\u200b-\u200d\ufeff]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

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

function providerName(provider: string): string {
  if (provider === "gmail") return "Gmail";
  if (provider === "yandex") return "Яндекс";
  return provider;
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

const NAV_KEY = "ohimymind-nav-open";

function readNavOpen(): boolean {
  try {
    return localStorage.getItem(NAV_KEY) !== "0";
  } catch {
    return true;
  }
}

function NavToggle({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className="nav-toggle"
      onClick={onClick}
      aria-pressed={open}
      title={open ? "Скрыть потоки" : "Показать потоки"}
      aria-label={open ? "Скрыть панель потоков" : "Показать панель потоков"}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
        <rect x="3.5" y="4.5" width="17" height="15" rx="2" strokeWidth="1.75" />
        <path d="M9 4.5v15" strokeWidth="1.75" />
      </svg>
    </button>
  );
}

function matchesQuery(head: ThreadHead, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  return [head.subject, head.from_addr, head.snippet].some((part) => (part || "").toLowerCase().includes(needle));
}

function visibleList(heads: ThreadHead[], tab: string, q: string): ThreadHead[] {
  return (tab === "all" ? heads : heads.filter((head) => senderDomain(head.from_addr) === tab)).filter((head) =>
    matchesQuery(head, q),
  );
}

function tabsFrom(list: ThreadHead[]) {
  const counts = new Map<string, { total: number; unread: number }>();
  for (const head of list) {
    const domain = senderDomain(head.from_addr);
    if (!domain) continue;
    const cur = counts.get(domain) || { total: 0, unread: 0 };
    cur.total += 1;
    if (head.unread) cur.unread += 1;
    counts.set(domain, cur);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1].total - a[1].total || a[0].localeCompare(b[0], "ru"))
    .map(([domain, stats]) => ({ domain, count: stats.total, unread: stats.unread }));
}

function ruLetters(n: number): string {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return `${n} письмо`;
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return `${n} письма`;
  return `${n} писем`;
}

function confirmTrash(count = 1): boolean {
  if (count <= 1) return window.confirm("Удалить это письмо?");
  return window.confirm(`Удалить ${ruLetters(count)}?`);
}

type TileMenu = {
  x: number;
  y: number;
  head: ThreadHead;
  important: boolean;
  ids: string[];
};

function ruUnimpCount(n: number): string {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return `${n} не важное письмо`;
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return `${n} не важных письма`;
  return `${n} не важных писем`;
}

function offsetInScroll(scroll: HTMLElement, el: HTMLElement): number {
  return el.getBoundingClientRect().top - scroll.getBoundingClientRect().top + scroll.scrollTop;
}

function MailBucket({
  title,
  empty,
  heads,
  query,
  onQuery,
  tab,
  onTab,
  searchRef,
  shortcut,
  active,
  picked,
  onTileClick,
  onMenu,
  rootRef,
  unimp,
  onClear,
}: {
  title: string;
  empty: string;
  heads: ThreadHead[];
  query: string;
  onQuery: (value: string) => void;
  tab: string;
  onTab: (value: string) => void;
  searchRef?: RefObject<HTMLInputElement | null>;
  shortcut?: string;
  active: string | null;
  picked: Set<string>;
  onTileClick: (head: ThreadHead, event: MouseEvent<HTMLButtonElement>) => void;
  onMenu: (event: MouseEvent, head: ThreadHead) => void;
  rootRef?: RefObject<HTMLDivElement | null>;
  unimp?: boolean;
  onClear?: () => void;
}) {
  const tabs = tabsFrom(heads);
  const unreadAll = heads.some((head) => head.unread);
  const visible = visibleList(heads, tab, query);
  return (
    <div ref={rootRef} className={`list-bucket${unimp ? " list-bucket-unimp" : ""}`}>
      <div className="list-bucket-head">
      <div className="list-bucket-title-row">
      <h3 className="list-bucket-title">{title}</h3>
      {onClear ? (
        <button type="button" className="list-bucket-clear" onClick={onClear}>
          <IcoTrash />
          Очистить
        </button>
      ) : null}
      </div>
      <form
        className="omnibar"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          ref={searchRef}
          placeholder={shortcut ? `Поиск (${shortcut})` : "Поиск"}
          value={query}
          onChange={(e) => onQuery(e.target.value)}
        />
        {shortcut ? <kbd>{shortcut}</kbd> : null}
      </form>
      <div className="domain-tabs">
        <button
          type="button"
          className={`domain-tab${tab === "all" ? " active" : ""}${unreadAll ? " has-unread" : ""}`}
          onClick={() => onTab("all")}
        >
          Все ({heads.length})
        </button>
        {tabs.map((item) => (
          <button
            key={item.domain}
            type="button"
            className={`domain-tab${tab === item.domain ? " active" : ""}${item.unread ? " has-unread" : ""}`}
            onClick={() => onTab(item.domain)}
          >
            @{item.domain} ({item.count})
          </button>
        ))}
      </div>
      </div>
      {visible.map((h) => {
        const domain = senderDomain(h.from_addr);
        const layers = (h.message_count ?? 1) > 2 ? 2 : (h.message_count ?? 1) > 1 ? 1 : 0;
        return (
          <div key={h.id} className="thread-stack" data-layers={layers}>
            <button
              type="button"
              className={`thread${h.unread ? " unread" : ""}${h.flagged ? " starred" : ""}${active === h.id ? " active" : ""}${picked.has(h.id) ? " picked" : ""}`}
              onMouseDown={(event) => {
                if (event.shiftKey) event.preventDefault();
              }}
              onClick={(event) => onTileClick(h, event)}
              onContextMenu={(event) => onMenu(event, h)}
            >
              <div className="thread-kicker">
                <span className="thread-kicker-left">
                  {domain ? <span className={h.unread ? "chip has-unread" : "chip"}>@{domain}</span> : null}
                  <ProviderBadge provider={h.provider} />
                </span>
                <span className="when">{formatWhen(h.last_at)}</span>
              </div>
              <div className="subj">
                {h.flagged ? <span className="star">★</span> : null}
                <span className="subj-text">{h.subject || "(без темы)"}</span>
              </div>
              <div className="snip">{plainPreview(h.snippet)}</div>
              <div className="from">{h.from_addr}</div>
            </button>
          </div>
        );
      })}
      {!visible.length ? <p className="muted list-empty">{empty}</p> : null}
    </div>
  );
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
  const [qImp, setQImp] = useState("");
  const [qUnimp, setQUnimp] = useState("");
  const [tabImp, setTabImp] = useState("all");
  const [tabUnimp, setTabUnimp] = useState("all");
  const [unimportant, setUnimportant] = useState<string[]>([]);
  const [menu, setMenu] = useState<TileMenu | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [anchorId, setAnchorId] = useState<string | null>(null);
  const [doneBusy, setDoneBusy] = useState<string | null>(null);
  const [unimpRaised, setUnimpRaised] = useState(false);
  const [raisePad, setRaisePad] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const listScrollRef = useRef<HTMLDivElement>(null);
  const unimpRef = useRef<HTMLDivElement>(null);
  const raisePadRef = useRef(0);
  const searchShortcut = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘K" : "Ctrl K";
  const [navOpen, setNavOpen] = useState(readNavOpen);

  function toggleNav() {
    setNavOpen((open) => {
      const next = !open;
      try {
        localStorage.setItem(NAV_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  const unimportantSet = useMemo(() => new Set(unimportant), [unimportant]);

  const importantAll = useMemo(() => {
    if (!isInboxFolder(folder)) return heads;
    return heads.filter((head) => {
      const domain = senderDomain(head.from_addr);
      return !domain || !unimportantSet.has(domain);
    });
  }, [folder, heads, unimportantSet]);

  const unimportantAll = useMemo(() => {
    if (!isInboxFolder(folder)) return [];
    return heads.filter((head) => {
      const domain = senderDomain(head.from_addr);
      return Boolean(domain && unimportantSet.has(domain));
    });
  }, [folder, heads, unimportantSet]);

  const defaultAccount = useMemo(
    () => accounts.find((a) => a.is_default_compose) || accounts[0],
    [accounts],
  );

  const visibleHeads = useMemo(() => (isInboxFolder(folder) ? [] : heads), [folder, heads]);

  const picked = useMemo(() => new Set(selectedIds), [selectedIds]);

  const tileOrder = useMemo(() => {
    if (isInboxFolder(folder)) {
      return [...visibleList(importantAll, tabImp, qImp), ...visibleList(unimportantAll, tabUnimp, qUnimp)];
    }
    return visibleHeads;
  }, [folder, importantAll, unimportantAll, tabImp, tabUnimp, qImp, qUnimp, visibleHeads]);

  const loadFolders = useCallback(async () => {
    setTrees(await api.folders());
    setAccounts(await api.accounts());
    const data = await api.unimportantDomains();
    setUnimportant(data.domains);
  }, []);

  const loadThreads = useCallback(async () => {
    const search = isInboxFolder(folder) ? "" : q;
    setHeads(await api.threads(folder, search));
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
    setTabImp("all");
    setTabUnimp("all");
    setQImp("");
    setQUnimp("");
    setUnimpRaised(false);
    setRaisePad(0);
    raisePadRef.current = 0;
    setSelectedIds([]);
    setAnchorId(null);
    setMenu(null);
    listScrollRef.current?.scrollTo({ top: 0 });
  }, [folder]);

  useEffect(() => {
    if (!unimportantAll.length) {
      setUnimpRaised(false);
      setRaisePad(0);
      raisePadRef.current = 0;
    }
  }, [unimportantAll.length]);

  function applyUnimpRaise() {
    const sc = listScrollRef.current;
    const un = unimpRef.current;
    if (!sc || !un) return;
    raisePadRef.current = 0;
    setRaisePad(0);
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const box = listScrollRef.current;
        const bucket = unimpRef.current;
        if (!box || !bucket) return;
        const fits = box.scrollHeight <= box.clientHeight + 1;
        if (fits) {
          const extra = Math.max(0, box.clientHeight - box.scrollHeight);
          raisePadRef.current = extra;
          setRaisePad(extra);
          box.scrollTo({ top: 0, behavior: "smooth" });
          return;
        }
        box.scrollTo({ top: Math.max(0, offsetInScroll(box, bucket)), behavior: "smooth" });
      });
    });
  }

  function raiseUnimp() {
    setUnimpRaised(true);
    applyUnimpRaise();
  }

  function lowerUnimp() {
    setUnimpRaised(false);
    raisePadRef.current = 0;
    setRaisePad(0);
    listScrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }

  function onInboxListScroll() {
    if (raisePadRef.current > 0) return;
    const sc = listScrollRef.current;
    const un = unimpRef.current;
    if (!sc || !un) return;
    const top = offsetInScroll(sc, un);
    if (sc.scrollTop >= top - 12) setUnimpRaised(true);
    else if (sc.scrollTop <= 16) setUnimpRaised(false);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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

  useEffect(() => {
    const live = new Set(heads.map((head) => head.id));
    setSelectedIds((prev) => {
      const next = prev.filter((id) => live.has(id));
      return next.length === prev.length ? prev : next;
    });
    setAnchorId((prev) => (prev && live.has(prev) ? prev : null));
  }, [heads]);

  async function openThread(id: string) {
    setActive(id);
    try {
      await api.read(id, { seen: true });
    } catch {
      /* still open */
    }
  }

  function rangeIds(fromId: string | null, toId: string): string[] {
    const ids = tileOrder.map((head) => head.id);
    const to = ids.indexOf(toId);
    if (to < 0) return [toId];
    const from = fromId ? ids.indexOf(fromId) : to;
    if (from < 0) return [toId];
    const lo = Math.min(from, to);
    const hi = Math.max(from, to);
    return ids.slice(lo, hi + 1);
  }

  function handleTileClick(head: ThreadHead, event: MouseEvent<HTMLButtonElement>) {
    if (event.shiftKey) {
      event.preventDefault();
      setSelectedIds(rangeIds(anchorId, head.id));
      if (!anchorId) setAnchorId(head.id);
      return;
    }
    setSelectedIds([head.id]);
    setAnchorId(head.id);
    void openThread(head.id);
  }

  function handleMenu(event: MouseEvent, head: ThreadHead, important: boolean) {
    event.preventDefault();
    const ids = selectedIds.includes(head.id) ? selectedIds : [head.id];
    if (!selectedIds.includes(head.id)) {
      setSelectedIds([head.id]);
      setAnchorId(head.id);
    }
    setMenu({ x: event.clientX, y: event.clientY, head, important, ids });
  }

  function headsForIds(ids: string[]): ThreadHead[] {
    const map = new Map(heads.map((head) => [head.id, head]));
    return ids.map((id) => map.get(id)).filter((head): head is ThreadHead => Boolean(head));
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

  async function trashMsg(msg: Message) {
    if (!confirmTrash()) return;
    await api.trash(msg.id);
    if (!thread) {
      await loadThreads();
      return;
    }
    const left = thread.messages.filter((m) => m.id !== msg.id);
    if (!left.length) setActive(null);
    else setThread({ ...thread, messages: left });
    await loadThreads();
  }

  async function clearUnimpInbox() {
    if (!window.confirm("Удалить все не важные письма из входящих?")) return;
    setError("");
    try {
      await api.clearUnimportantInbox(folder);
      setActive(null);
      await loadThreads();
    } catch (err) {
      setError(err instanceof Error ? err.message : "не удалось очистить");
    }
  }

  async function archiveThread(msg: Message) {
    await api.archive(msg.id);
    setActive(null);
    await loadThreads();
  }

  async function markDone(msg: Message) {
    if (doneBusy) return;
    setDoneBusy(msg.id);
    setError("");
    try {
      await api.done(msg.id);
      setActive(null);
      await loadThreads();
    } catch (err) {
      setError(err instanceof Error ? err.message : "не удалось выполнить");
    } finally {
      setDoneBusy(null);
    }
  }

  async function latestFromHead(head: ThreadHead): Promise<Message | null> {
    const packed = await api.thread(head.id);
    if (!packed.messages.length) return null;
    if (head.latest_message_id) {
      const hit = packed.messages.find((item) => item.id === head.latest_message_id);
      if (hit) return hit;
    }
    return [...packed.messages].sort((a, b) => (a.sent_at || "").localeCompare(b.sent_at || "")).at(-1) ?? null;
  }

  async function runMenuAction(kind: "reply" | "forward" | "trash" | "archive" | "done") {
    if (!menu) return;
    const focus = menu.head;
    const targets = headsForIds(menu.ids);
    const batch = kind === "reply" || kind === "forward" ? [focus] : targets.length ? targets : [focus];
    setMenu(null);
    setError("");
    if (kind === "trash" && !confirmTrash(batch.length)) return;
    const hitIds = new Set(batch.map((head) => head.id));
    try {
      if (kind === "done") setDoneBusy(focus.id);
      for (const head of batch) {
        const msg = await latestFromHead(head);
        if (!msg) continue;
        if (kind === "reply") {
          reply(msg);
          return;
        }
        if (kind === "forward") {
          forward(msg);
          return;
        }
        if (kind === "trash") await api.trash(msg.id);
        else if (kind === "archive") await api.archive(msg.id);
        else await api.done(msg.id);
      }
      if (kind === "trash" || kind === "archive" || kind === "done") {
        if (active && hitIds.has(active)) setActive(null);
        setSelectedIds([]);
        setAnchorId(null);
        await loadThreads();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "не удалось выполнить действие");
      await loadThreads();
    } finally {
      if (kind === "done") setDoneBusy(null);
    }
  }

  async function setSelectionImportance(important: boolean) {
    if (!menu) return;
    const targets = headsForIds(menu.ids);
    setMenu(null);
    const domains = [
      ...new Set(targets.map((head) => senderDomain(head.from_addr)).filter(Boolean)),
    ];
    if (!domains.length) return;
    setError("");
    try {
      let next = unimportant;
      for (const domain of domains) {
        const data = important ? await api.removeUnimportantDomain(domain) : await api.addUnimportantDomain(domain);
        next = data.domains;
      }
      setUnimportant(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "не удалось сменить важность");
    }
  }

  useEffect(() => {
    if (!menu) return;
    function close(event?: Event) {
      if (event && event.target instanceof Element && event.target.closest(".ctx-menu")) return;
      setMenu(null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
    };
  }, [menu]);

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
      <AppHeader>
        <button type="button" className="primary" onClick={() => startCompose()}>
          Написать
        </button>
        <Link to="/settings">Ящики</Link>
        <span className="muted">
          {user.login} · {user.role}
        </span>
        <button type="button" onClick={logout}>
          Выход
        </button>
      </AppHeader>
      <div className={navOpen ? "layout" : "layout nav-collapsed"}>
        <aside className={navOpen ? "pane folders" : "pane folders folders-collapsed"}>
          {navOpen ? (
            <>
          <div className="folders-head">
            <div className="nav-kicker">Мои потоки</div>
            <NavToggle open={navOpen} onClick={toggleNav} />
          </div>
          <p className="muted nav-sub">Почта — поток №1</p>
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
            </>
          ) : (
            <>
              <NavToggle open={navOpen} onClick={toggleNav} />
              <button type="button" className="folders-rail-label" onClick={toggleNav}>
                Потоки
              </button>
            </>
          )}
        </aside>
        <section className="pane list-pane">
          {isInboxFolder(folder) ? (
            <>
            <div
              ref={listScrollRef}
              className={`list-scroll${unimportantAll.length ? " has-unimp-dock" : ""}`}
              onScroll={onInboxListScroll}
            >
              <div className="list-raise-spacer" style={{ height: raisePad }} aria-hidden="true" />
              <MailBucket
                title="Важные"
                empty="Важных нет"
                heads={importantAll}
                query={qImp}
                onQuery={setQImp}
                tab={tabImp}
                onTab={setTabImp}
                searchRef={searchRef}
                shortcut={searchShortcut}
                active={active}
                picked={picked}
                onTileClick={handleTileClick}
                onMenu={(event, head) => handleMenu(event, head, true)}
              />
              <MailBucket
                title="Не важные"
                empty="Не важных нет"
                heads={unimportantAll}
                query={qUnimp}
                onQuery={setQUnimp}
                tab={tabUnimp}
                onTab={setTabUnimp}
                rootRef={unimpRef}
                unimp
                onClear={unimportantAll.length ? () => void clearUnimpInbox() : undefined}
                active={active}
                picked={picked}
                onTileClick={handleTileClick}
                onMenu={(event, head) => handleMenu(event, head, false)}
              />
            </div>
            {unimportantAll.length ? (
              <div className="unimp-dock">
                <button
                  type="button"
                  className="unimp-dock-count"
                  onClick={raiseUnimp}
                  aria-label={`Показать не важные, ${ruUnimpCount(unimportantAll.length)}`}
                >
                  {ruUnimpCount(unimportantAll.length)}
                </button>
                {unimpRaised ? (
                  <button
                    type="button"
                    className="unimp-dock-down"
                    onClick={lowerUnimp}
                    title="Вернуть важные"
                    aria-label="Вернуть важные"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 9l6 6 6-6" />
                    </svg>
                  </button>
                ) : null}
              </div>
            ) : null}
            </>
          ) : (
            <>
          <div className="list-chrome">
          <form
            className="omnibar"
            onSubmit={(e) => {
              e.preventDefault();
              setQ(query);
            }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={searchRef}
              placeholder={`Поиск знаний, писем, тегов (${searchShortcut})`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <kbd>{searchShortcut}</kbd>
          </form>
          </div>
          <div className="list-scroll">
          {visibleHeads.map((h) => {
            const domain = senderDomain(h.from_addr);
            const layers = (h.message_count ?? 1) > 2 ? 2 : (h.message_count ?? 1) > 1 ? 1 : 0;
            return (
              <div key={h.id} className="thread-stack" data-layers={layers}>
              <button
                type="button"
                className={`thread${h.unread ? " unread" : ""}${h.flagged ? " starred" : ""}${active === h.id ? " active" : ""}${picked.has(h.id) ? " picked" : ""}`}
                onMouseDown={(event) => {
                  if (event.shiftKey) event.preventDefault();
                }}
                onClick={(event) => handleTileClick(h, event)}
                onContextMenu={(event) => handleMenu(event, h, true)}
              >
                <div className="thread-kicker">
                  <span className="thread-kicker-left">
                    {domain ? <span className={h.unread ? "chip has-unread" : "chip"}>@{domain}</span> : null}
                    <ProviderBadge provider={h.provider} />
                  </span>
                  <span className="when">{formatWhen(h.last_at)}</span>
                </div>
                <div className="subj">
                  {h.flagged ? <span className="star">★</span> : null}
                  <span className="subj-text">{h.subject || "(без темы)"}</span>
                </div>
                <div className="snip">{plainPreview(h.snippet)}</div>
                <div className="from">{h.from_addr}</div>
              </button>
              </div>
            );
          })}
          {!visibleHeads.length ? <p className="muted list-empty">Пусто</p> : null}
          </div>
            </>
          )}
        </section>
        <section className="pane thread-pane">
          {error ? <div className="error thread-error">{error}</div> : null}
          {thread ? (
            <div className="thread-scroll">
              {thread.messages.map((msg) => {
                const flags = msg.flags || [];
                const flagged = flags.includes("\\Flagged");
                const unread = !flags.includes("\\Seen");
                return (
                <article
                  className={`msg${unread ? " unread" : ""}${flagged ? " starred" : ""}`}
                  key={msg.id}
                >
                  <header>
                    <div className="msg-head-main">
                      <div className="msg-badges">
                        <button
                          type="button"
                          className="star-btn"
                          title={flagged ? "Снять звезду" : "Пометить звездой"}
                          onClick={() => star(msg, !flagged)}
                        >
                          <Ico>
                            <path
                              d="M12 3.6 14.5 9l6 .9-4.3 4.2 1 5.9L12 17.2 6.8 20l1-5.9L3.5 9.9 9.5 9z"
                              strokeWidth="1.75"
                              fill={flagged ? "currentColor" : "none"}
                            />
                          </Ico>
                        </button>
                        <strong>{msg.from_addr}</strong>
                        <ProviderBadge provider={msg.provider} />
                      </div>
                      <div className="muted">{msg.subject}</div>
                    </div>
                    <div className="msg-head-side">
                      <span className="when">{formatWhen(msg.sent_at)}</span>
                      <div className="msg-actions">
                        <button type="button" title="Ответить" onClick={() => reply(msg)}>
                          <IcoReply />
                          Ответить
                        </button>
                        <button type="button" title="Переслать" onClick={() => forward(msg)}>
                          <IcoForward />
                          Переслать
                        </button>
                        <button type="button" className="danger" title="Удалить" onClick={() => void trashMsg(msg)}>
                          <IcoTrash />
                          Удалить
                        </button>
                        <button type="button" title="В архив" onClick={() => void archiveThread(msg)}>
                          <IcoArchive />
                          В архив
                        </button>
                        <button
                          type="button"
                          className="primary"
                          title="Выполнить"
                          disabled={doneBusy === msg.id}
                          onClick={() => void markDone(msg)}
                        >
                          <IcoDone />
                          {doneBusy === msg.id ? "Отправка…" : "Выполнить"}
                        </button>
                      </div>
                    </div>
                  </header>
                  {msg.body_html ? (
                    <EmailHtml html={msg.body_html} title={msg.subject} />
                  ) : (
                    <EmailText text={msg.body_text} />
                  )}
                  <MsgAttachments attachments={msg.attachments || []} sentAt={msg.sent_at} />
                </article>
                );
              })}
              </div>
          ) : (
            <p className="muted empty-inspector">Выберите карточку слева — справа контекст потока.</p>
          )}
        </section>
      </div>
      {menu ? (
        <div
          className="ctx-menu"
          style={{
            left: Math.min(menu.x, window.innerWidth - 228),
            top: Math.min(menu.y, window.innerHeight - 320),
          }}
          role="menu"
        >
          <button type="button" onClick={() => void runMenuAction("reply")}>
            <IcoReply />
            Ответить
          </button>
          <button type="button" onClick={() => void runMenuAction("forward")}>
            <IcoForward />
            Переслать
          </button>
          <button type="button" className="danger" onClick={() => void runMenuAction("trash")}>
            <IcoTrash />
            {menu.ids.length > 1 ? `Удалить (${menu.ids.length})` : "Удалить"}
          </button>
          <button type="button" onClick={() => void runMenuAction("archive")}>
            <IcoArchive />
            {menu.ids.length > 1 ? `В архив (${menu.ids.length})` : "В архив"}
          </button>
          <button type="button" className="primary" onClick={() => void runMenuAction("done")}>
            <IcoDone />
            {menu.ids.length > 1 ? `Выполнить (${menu.ids.length})` : "Выполнить"}
          </button>
          {isInboxFolder(folder) ? (
            menu.important ? (
              <button
                type="button"
                disabled={!headsForIds(menu.ids).some((head) => senderDomain(head.from_addr))}
                onClick={() => void setSelectionImportance(false)}
              >
                <IcoUnimportant />
                В не важное
              </button>
            ) : (
              <button
                type="button"
                disabled={!headsForIds(menu.ids).some((head) => senderDomain(head.from_addr))}
                onClick={() => void setSelectionImportance(true)}
              >
                <IcoImportant />
                В важное
              </button>
            )
          ) : null}
        </div>
      ) : null}
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
