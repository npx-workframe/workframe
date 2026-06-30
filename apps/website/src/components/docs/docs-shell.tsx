import Link from "next/link";

import { DocsMobileNav } from "@/components/docs/docs-mobile-nav";
import { DocsSidebar } from "@/components/docs/docs-sidebar";
import { SiteNavbar } from "@/components/site-navbar";
import type { DocNavSection } from "@/lib/docs";

export function DocsShell({
  sections,
  children,
}: {
  sections: DocNavSection[];
  children: React.ReactNode;
}) {
  return (
    <div className="wf-docs-layout flex min-h-dvh flex-col">
      <div className="wf-docs-header wf-page-bg wf-page-bg--viewport sticky top-0 z-10">
        <SiteNavbar wide docsActive />
      </div>

      <div className="mx-auto flex w-full max-w-6xl flex-1 gap-6 px-6 py-8 sm:px-10 lg:gap-8">
        <DocsSidebar sections={sections} />
        <div className="min-w-0 flex-1">{children}</div>
      </div>

      <div className="mx-auto w-full max-w-6xl px-6 pb-2 lg:hidden">
        <DocsMobileNav sections={sections} />
      </div>

      <footer className="safe-bottom mb-2.5 px-6 pb-12 pt-8 text-center font-[family-name:var(--wf-font-mono)] text-[11px] uppercase tracking-[0.12em] text-[var(--wf-muted)] sm:px-10 sm:pb-14">
        © 2026 Workfra.me ·{" "}
        <Link href="/" className="cursor-pointer hover:text-[var(--wf-text)]">
          Home
        </Link>
      </footer>
    </div>
  );
}
