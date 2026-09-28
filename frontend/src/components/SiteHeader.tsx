"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Map" },
  { href: "/farmer", label: "Farmer view" },
  { href: "/officer", label: "Officer" },
  { href: "/validation", label: "Validation" },
  { href: "/about", label: "How it works" },
];

export default function SiteHeader() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-[1000] border-b border-navy/20 bg-navy text-white">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight">GramVarsha</span>
          <span className="font-[family-name:var(--font-mr)] text-base text-amber">ग्रामवर्षा</span>
        </Link>
        <nav className="-mx-1 flex min-w-0 flex-1 basis-full gap-1 overflow-x-auto text-sm [scrollbar-width:none] sm:basis-auto" aria-label="Main">
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded px-2.5 py-1 transition-colors ${
                  active ? "bg-white/15 text-white" : "text-white/75 hover:bg-white/10 hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <span className="hidden text-xs text-white/60 lg:inline">Miraj taluka · Sangli · Maharashtra</span>
      </div>
    </header>
  );
}
