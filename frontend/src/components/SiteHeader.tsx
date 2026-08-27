"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/apply", label: "Applicant portal" },
  { href: "/dashboard", label: "Underwriting queue" },
  { href: "/analytics", label: "Portfolio analytics" },
];

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="no-print border-b border-rule-strong bg-surface">
      <div className="mx-auto flex h-[52px] max-w-content items-center gap-6 px-6">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="font-mono text-h2 font-semibold tracking-tight text-brand">QistEngine</span>
          <span className="hidden text-caption text-ink-faint sm:inline">
            alternative credit scoring
          </span>
        </Link>
        <nav className="ms-4 flex items-center gap-1">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-sm px-3 py-1.5 text-body-strong transition-tokens",
                  active ? "bg-brand-tint text-brand" : "text-ink-muted hover:bg-surface-sunk hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <span className="ms-auto hidden text-mono-sm text-ink-faint md:inline">
          Demonstration · synthetic data
        </span>
      </div>
    </header>
  );
}
