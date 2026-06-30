"use client";

import type { DocNavSection } from "@/lib/docs";

export function DocsMobileNav({ sections }: { sections: DocNavSection[] }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--wf-muted)]">
        Jump to
      </span>
      <select
        className="neo-inset cursor-pointer rounded-full border-0 px-4 py-2.5 text-[13px] text-[var(--wf-text)]"
        defaultValue=""
        onChange={(e) => {
          if (e.target.value) window.location.href = e.target.value;
        }}
      >
        <option value="" disabled>
          Choose a page…
        </option>
        {sections.flatMap((section) =>
          section.items.map((item) => (
            <option key={item.slug} value={`/docs/${item.slug}`}>
              {item.label}
            </option>
          )),
        )}
      </select>
    </label>
  );
}
