"use client";

import { useCallback, useEffect, useRef } from "react";

function clearCopyLock(el: HTMLElement) {
  el.style.minWidth = "";
  el.style.width = "";
  el.style.minHeight = "";
  el.style.height = "";
  el.style.display = "";
  el.style.textAlign = "";
  el.style.alignItems = "";
  el.style.justifyContent = "";
  el.style.boxSizing = "";
}

function restoreCode(el: HTMLElement) {
  const original = el.dataset.original;
  if (original != null) {
    el.textContent = original;
    delete el.dataset.copying;
    delete el.dataset.original;
    clearCopyLock(el);
  }
}

export function DocsProse({ html }: { html: string }) {
  const activeRef = useRef<HTMLElement | null>(null);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current != null) window.clearTimeout(timeoutRef.current);
      if (activeRef.current) restoreCode(activeRef.current);
    };
  }, []);

  const onClick = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const code = (event.target as HTMLElement).closest("code");
    if (!code || !event.currentTarget.contains(code)) return;
    if (code.dataset.copying === "1") return;

    const original = code.textContent ?? "";
    if (!original) return;

    void navigator.clipboard.writeText(original).catch(() => {});

    if (activeRef.current && activeRef.current !== code) {
      restoreCode(activeRef.current);
    }

    code.dataset.original = original;
    code.dataset.copying = "1";

    const inPre = code.closest("pre") != null;
    code.style.boxSizing = "border-box";
    code.style.display = inPre ? "flex" : "inline-flex";
    code.style.alignItems = "center";
    code.style.justifyContent = "center";
    const { width, height } = code.getBoundingClientRect();
    code.style.width = `${width}px`;
    code.style.height = `${height}px`;
    code.textContent = "copied!";
    activeRef.current = code;

    if (timeoutRef.current != null) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => {
      restoreCode(code);
      if (activeRef.current === code) activeRef.current = null;
      timeoutRef.current = null;
    }, 2000);
  }, []);

  return (
    <div
      className="wf-doc-prose neo-elevated rounded-[var(--wf-radius)] p-6 sm:p-8"
      onClick={onClick}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
