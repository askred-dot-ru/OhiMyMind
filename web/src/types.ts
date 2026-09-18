export type User = { login: string; role: string };

export type Account = {
  id: string;
  provider: string;
  email: string;
  unified: boolean;
  is_default_compose: boolean;
  imap_host: string;
  smtp_host: string;
};

export type FolderNode = {
  id: string;
  canonical: string;
  name: string;
  account_id: string | null;
};

export type FolderTree = {
  kind: string;
  label: string | null;
  folders: FolderNode[];
};

export type ThreadHead = {
  id: string;
  subject: string;
  from_addr: string;
  snippet: string;
  last_at: string | null;
  unread: boolean;
  flagged: boolean;
  account_id: string;
  folder_canonical: string;
  provider: string;
  message_count: number;
  latest_message_id?: string;
};

export type AttachmentMeta = {
  id: string;
  filename: string;
  mime: string;
  size_bytes: number;
  content_id?: string;
};

export type Message = {
  id: string;
  account_id: string;
  provider: string;
  folder_canonical: string;
  subject: string;
  from_addr: string;
  to: string[];
  cc: string[];
  sent_at: string | null;
  body_text: string;
  body_html: string;
  flags: string[];
  attachments: AttachmentMeta[];
};

export type Thread = {
  id: string;
  messages: Message[];
};
