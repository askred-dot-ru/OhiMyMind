import DOMPurify from "dompurify";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { onThemeChange, readTheme, type Theme } from "./theme";

function sanitize(html: string): string {
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ["img", "picture", "source"],
    ADD_ATTR: ["src", "srcset", "alt", "width", "height"],
    ALLOWED_URI_REGEXP:
      /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
  });
}

function contentHeight(iframe: HTMLIFrameElement): number {
  const doc = iframe.contentDocument;
  if (!doc?.documentElement) return 0;
  return Math.max(doc.documentElement.scrollHeight, doc.body?.scrollHeight ?? 0, 1) + 8;
}

function growTo(el: HTMLElement, next: number, instant: boolean) {
  const prev = el.getBoundingClientRect().height;
  if (Math.abs(next - prev) < 0.5) return;
  if (instant) {
    el.style.transitionDuration = "0s";
    el.style.height = `${next}px`;
    void el.offsetHeight;
    el.style.transitionDuration = "";
    return;
  }
  const delta = Math.abs(next - prev);
  el.style.transitionDuration = `${Math.min(0.72, 0.22 + delta / 1800)}s`;
  el.style.height = `${next}px`;
}

function themePaint(): { bg: string; text: string; muted: string; accent: string } {
  const css = getComputedStyle(document.documentElement);
  return {
    bg: css.getPropertyValue("--bg-2").trim() || "#1d2025",
    text: css.getPropertyValue("--text").trim() || "#edeff2",
    muted: css.getPropertyValue("--muted").trim() || "#8c929e",
    accent: css.getPropertyValue("--accent").trim() || "#3b82f6",
  };
}

function frameCss(theme: Theme): string {
  const scrollHide = `
  html, body { overflow: hidden !important; width: 100%; max-width: 100%; }
  html { scrollbar-width: none; }
  ::-webkit-scrollbar { width: 0 !important; height: 0 !important; display: none !important; }
`;
  if (theme === "light") {
    return `
  html { color-scheme: light; }
  html, body { margin: 0; padding: 0; background: transparent; color: #1e2022; }
  img, video { max-width: 100%; height: auto; }
  ${scrollHide}
`;
  }
  const { bg, text, muted, accent } = themePaint();
  return `
  html { color-scheme: dark; }
  html, body {
    margin: 0;
    padding: 0;
    background: ${bg} !important;
    color: ${text} !important;
  }
  body *:not(img):not(picture):not(source):not(video):not(svg):not(path) {
    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;
  }
  body, p, div, td, th, li, span, font, center, article, section, h1, h2, h3, h4, h5, h6, pre, label {
    color: ${text} !important;
  }
  [bgcolor] { background-color: transparent !important; }
  a { color: ${accent} !important; }
  blockquote { color: ${muted} !important; }
  img, video { max-width: 100%; height: auto; background: none !important; }
  ${scrollHide}
`;
}

export function EmailText({ text }: { text: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const pre = preRef.current;
    if (!wrap || !pre) return;
    growTo(wrap, 0, true);
    const id = requestAnimationFrame(() => growTo(wrap, pre.scrollHeight, false));
    return () => cancelAnimationFrame(id);
  }, [text]);

  return (
    <div ref={wrapRef} className="msg-body-grow">
      <pre ref={preRef}>{text}</pre>
    </div>
  );
}

export function EmailHtml({ html, title }: { html: string; title: string }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const raf = useRef(0);
  const roRef = useRef<ResizeObserver | null>(null);
  const [theme, setTheme] = useState<Theme>(() => readTheme());

  useEffect(() => onThemeChange(setTheme), []);

  const srcDoc = useMemo(() => {
    const origin = window.location.origin;
    const body = sanitize(html);
    return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="${theme}">
<base href="${origin}/" target="_blank">
<style>${frameCss(theme)}</style>
</head>
<body>${body}</body>
</html>`;
  }, [html, theme]);

  const fit = useCallback((instant = false) => {
    const iframe = ref.current;
    if (!iframe) return;
    growTo(iframe, contentHeight(iframe), instant);
  }, []);

  const scheduleFit = useCallback(() => {
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => fit(false));
  }, [fit]);

  useEffect(
    () => () => {
      cancelAnimationFrame(raf.current);
      roRef.current?.disconnect();
    },
    [],
  );

  const onLoad = useCallback(() => {
    const iframe = ref.current;
    const doc = iframe?.contentDocument;
    if (!iframe || !doc) return;
    growTo(iframe, 0, true);
    scheduleFit();
    for (const img of Array.from(doc.images)) {
      if (img.complete) continue;
      img.addEventListener("load", scheduleFit);
      img.addEventListener("error", scheduleFit);
    }
    roRef.current?.disconnect();
    const ro = new ResizeObserver(scheduleFit);
    ro.observe(doc.documentElement);
    if (doc.body) ro.observe(doc.body);
    roRef.current = ro;
  }, [scheduleFit]);

  return (
    <iframe
      ref={ref}
      className="html-frame"
      title={title || "Письмо"}
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      referrerPolicy="no-referrer"
      scrolling="no"
      srcDoc={srcDoc}
      onLoad={onLoad}
    />
  );
}
