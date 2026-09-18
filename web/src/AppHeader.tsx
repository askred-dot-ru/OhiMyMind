import { useState, type ReactNode } from "react";
import { PRODUCT_NAME } from "./brand";
import { BrandSplash } from "./BrandSplash";
import { BrandLockup } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

export function AppHeader({ children }: { children?: ReactNode }) {
  const [splash, setSplash] = useState(false);
  return (
    <>
      <header className="top">
        <button type="button" className="brand" onClick={() => setSplash(true)} aria-label={`${PRODUCT_NAME}: открыть знак`}>
          <BrandLockup />
        </button>
        <div className="spacer" />
        {children}
        <ThemeToggle />
      </header>
      {splash ? <BrandSplash onClose={() => setSplash(false)} /> : null}
    </>
  );
}
