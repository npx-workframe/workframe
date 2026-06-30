"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { DocNavSection } from "@/lib/docs";

export function DocsSidebar({ sections }: { sections: DocNavSection[] }) {
  const pathname = usePathname();
  const activeSlug = pathname.split("/").filter(Boolean).pop() ?? "";

  return (
    <aside className="wf-docs-sidebar neo-inset hidden w-56 shrink-0 flex-col self-start rounded-[var(--wf-radius)] lg:sticky lg:flex">
      <p className="shrink-0 p-2 pb-0 text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--wf-muted)]">
        Documentation
      </p>
      <nav className="wf-docs-sidebar-nav flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto overflow-x-hidden p-2">
        {sections.map((section) => (
          <div key={section.title} className="flex flex-col gap-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--wf-muted)]/80">
              {section.title}
            </p>
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {section.items.map((item) => {
                const active = item.slug === activeSlug;
                return (
                  <li key={item.slug}>
                    <Link
                      href={`/docs/${item.slug}`}
                      className={`wf-docs-rail-link block cursor-pointer rounded-lg px-2 py-2 text-[13px] leading-snug ${
                        active
                          ? "wf-docs-rail-link--active neo-raised font-medium text-[var(--wf-text)]"
                          : "text-[var(--wf-muted)]"
                      }`}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
