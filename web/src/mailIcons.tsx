export function Ico({ children }: { children: React.ReactNode }) {
  return (
    <svg className="msg-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      {children}
    </svg>
  );
}

export function IcoReply() {
  return (
    <Ico>
      <path d="M9 14 4 9l5-5" strokeWidth="1.75" />
      <path d="M20 20v-7a4 4 0 0 0-4-4H4" strokeWidth="1.75" />
    </Ico>
  );
}

export function IcoForward() {
  return (
    <Ico>
      <path d="m15 14 5-5-5-5" strokeWidth="1.75" />
      <path d="M4 20v-7a4 4 0 0 1 4-4h12" strokeWidth="1.75" />
    </Ico>
  );
}

export function IcoTrash() {
  return (
    <Ico>
      <path d="M4 7h16" strokeWidth="1.75" />
      <path d="M9 7V5h6v2" strokeWidth="1.75" />
      <path d="M6 7v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7" strokeWidth="1.75" />
      <path d="M10 11v6M14 11v6" strokeWidth="1.75" />
    </Ico>
  );
}

export function IcoArchive() {
  return (
    <Ico>
      <path d="M3 7h18v3H3z" strokeWidth="1.75" />
      <path d="M5 10v9h14v-9" strokeWidth="1.75" />
      <path d="M10 14h4" strokeWidth="1.75" />
    </Ico>
  );
}

export function IcoDone() {
  return (
    <Ico>
      <circle cx="12" cy="12" r="8" strokeWidth="1.75" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5" strokeWidth="1.75" />
    </Ico>
  );
}

export function IcoUnimportant() {
  return (
    <Ico>
      <path d="M12 4v12" strokeWidth="1.75" />
      <path d="m7 11 5 5 5-5" strokeWidth="1.75" />
    </Ico>
  );
}

export function IcoFloppy() {
  return (
    <Ico>
      <path d="M5 4h11l4 4v12H5V4z" strokeWidth="1.75" />
      <path d="M8 4v5h8V4" strokeWidth="1.75" />
      <path d="M8 20v-6h8v6" strokeWidth="1.75" />
    </Ico>
  );
}

export function IcoImportant() {
  return (
    <Ico>
      <path d="M12 20V8" strokeWidth="1.75" />
      <path d="m7 13 5-5 5 5" strokeWidth="1.75" />
    </Ico>
  );
}
