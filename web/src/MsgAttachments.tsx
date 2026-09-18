import type { MouseEvent } from "react";
import { formatWhen } from "./datetime";
import { IcoFloppy } from "./mailIcons";
import type { AttachmentMeta } from "./types";

const RASTER = new Set(["jpg", "jpeg", "png", "gif", "webp", "bmp", "avif"]);
const IMAGE_MAX_BYTES = 8 * 1024 * 1024;

export function attUrl(id: string, download = false): string {
  return download ? `/api/v1/mail/attachments/${id}?download=1` : `/api/v1/mail/attachments/${id}`;
}

export function isImageAtt(att: AttachmentMeta): boolean {
  const name = att?.filename || "";
  const mime = (att?.mime || "").toLowerCase();
  if ((att?.size_bytes || 0) > IMAGE_MAX_BYTES) return false;
  if (mime.includes("svg") || mime.includes("xml")) return false;
  if (mime.startsWith("image/")) return true;
  const ext = name.split(".").pop()?.toLowerCase() || "";
  return RASTER.has(ext);
}

function formatSize(bytes: number): string {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n < 0) return "";
  if (n < 1024) return `${Math.round(n)} Б`;
  if (n < 1024 * 1024) {
    const kb = n / 1024;
    return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} КБ`;
  }
  const mb = n / (1024 * 1024);
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} МБ`;
}

function fileKind(filename: string, mime: string): string {
  const ext = (filename || "").split(".").pop()?.toLowerCase() || "";
  const m = (mime || "").toLowerCase();
  if (m.includes("pdf") || ext === "pdf") return "pdf";
  if (m.includes("zip") || m.includes("compress") || ["zip", "rar", "7z", "gz", "tar"].includes(ext)) return "zip";
  if (m.includes("word") || ["doc", "docx", "rtf", "odt"].includes(ext)) return "doc";
  if (m.includes("excel") || m.includes("spreadsheet") || ["xls", "xlsx", "csv", "ods"].includes(ext)) return "xls";
  if (m.includes("powerpoint") || m.includes("presentation") || ["ppt", "pptx", "odp"].includes(ext)) return "ppt";
  if (m.startsWith("audio/") || ["mp3", "wav", "ogg", "flac", "m4a"].includes(ext)) return "audio";
  if (m.startsWith("video/") || ["mp4", "mov", "avi", "mkv", "webm"].includes(ext)) return "video";
  if (m.startsWith("text/") || ["txt", "md", "json", "xml", "log"].includes(ext)) return "txt";
  return "file";
}

function glyphLabel(filename: string): string {
  const name = filename || "";
  const ext = name.split(".").pop() || "";
  if (!ext || ext === name) return "FILE";
  return ext.slice(0, 4).toUpperCase();
}

function openAtt(id: string) {
  window.open(attUrl(id), "_blank", "noopener,noreferrer");
}

export function MsgAttachments({
  attachments,
  sentAt,
}: {
  attachments: AttachmentMeta[] | null | undefined;
  sentAt: string | null;
}) {
  const list = Array.isArray(attachments) ? attachments : [];
  const images = list.filter(isImageAtt);
  const files = list.filter((att) => !isImageAtt(att));
  if (!images.length && !files.length) return null;
  return (
    <>
      {images.length ? (
        <div className="msg-images">
          {images.map((att) => (
            <button
              key={att.id}
              type="button"
              className="msg-image"
              title={att.filename}
              onClick={() => openAtt(att.id)}
            >
              <img src={attUrl(att.id)} alt={att.filename || ""} loading="lazy" decoding="async" />
            </button>
          ))}
        </div>
      ) : null}
      {files.length ? (
        <div className="msg-files">
          {files.map((att) => {
            const kind = fileKind(att.filename, att.mime);
            return (
              <div key={att.id} className="file-tile">
                <button type="button" className="file-tile-open" onClick={() => openAtt(att.id)}>
                  <span className={`file-glyph file-glyph-${kind}`} aria-hidden="true">
                    {glyphLabel(att.filename)}
                  </span>
                  <span className="file-tile-meta">
                    <span className="file-tile-name">{att.filename || "файл"}</span>
                    <span className="file-tile-sub">
                      {formatSize(att.size_bytes)}
                      {sentAt ? ` · ${formatWhen(sentAt)}` : ""}
                    </span>
                  </span>
                </button>
                <a
                  className="file-tile-save"
                  href={attUrl(att.id, true)}
                  download={att.filename}
                  title="Скачать"
                  aria-label={`Скачать ${att.filename}`}
                  onClick={(event: MouseEvent<HTMLAnchorElement>) => event.stopPropagation()}
                >
                  <IcoFloppy />
                </a>
              </div>
            );
          })}
        </div>
      ) : null}
    </>
  );
}
