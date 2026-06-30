import type { DocPage } from "@/lib/docs";

import { DocsProse } from "@/components/docs/docs-prose";

export function DocsArticle({ page }: { page: DocPage }) {
  return (
    <article className="min-w-0 flex-1">
      <header className="mb-8">
        <p className="mb-2 font-[family-name:var(--wf-font-mono)] text-[11px] uppercase tracking-[0.12em] text-[var(--wf-muted)]">
          {page.sourcePath}
        </p>
        <h1 className="text-[2rem] font-semibold leading-tight tracking-[-0.03em] text-[var(--wf-text)] sm:text-[2.25rem]">
          {page.title}
        </h1>
        {page.description ? (
          <p className="mt-3 max-w-2xl text-[16px] leading-7 text-[var(--wf-muted)]">
            {page.description}
          </p>
        ) : null}
      </header>

      <DocsProse html={page.html} />
    </article>
  );
}
