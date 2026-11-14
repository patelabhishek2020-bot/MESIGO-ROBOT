"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "@/lib/api";

const LINKS = [
  { href: "/dashboard", label: "Overview" },
  { href: "/wizard", label: "Setup Wizard" },
  { href: "/brain", label: "Central Brain" },
  { href: "/console", label: "Voice / Text" },
  { href: "/approvals", label: "Approvals" },
  { href: "/agents", label: "Agents 2–12" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  function logout() {
    clearToken();
    router.replace("/");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">MESIGO AI</span>
          <div className="brand-name">Control Deck</div>
          <span className="badge ok">
            <span className="live-dot" /> LIVE
          </span>
        </div>
        <nav className="nav">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={pathname.startsWith(link.href) ? "active" : ""}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div style={{ marginTop: "auto" }}>
          <button className="btn ghost" type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
