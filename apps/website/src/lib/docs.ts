import fs from "node:fs";
import path from "node:path";

import { marked } from "marked";

export type DocHeading = {
  id: string;
  text: string;
  level: 2 | 3;
};

export type DocNavItem = {
  slug: string;
  label: string;
  description?: string;
};

export type DocNavSection = {
  title: string;
  items: DocNavItem[];
};

export type DocPage = {
  slug: string;
  title: string;
  description?: string;
  sourcePath: string;
  content: string;
  html: string;
  headings: DocHeading[];
};

const DOCS_ROOT = path.resolve(process.cwd(), "../../docs");
const README_PATH = path.join(DOCS_ROOT, "README.md");

const SLUG_RE = /^[a-z0-9-]+$/;

function slugify(text: string) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .trim();
}

function titleFromMarkdown(content: string, fallback: string) {
  const match = content.match(/^#\s+(.+)$/m);
  return match?.[1]?.trim() ?? fallback;
}

function relPathToSlug(relPath: string): string | null {
  const normalized = relPath.replace(/\\/g, "/");
  if (normalized.startsWith("public/") && normalized.endsWith(".md")) {
    return normalized.slice("public/".length, -".md".length);
  }
  if (normalized === "VERSION.md") return "version";
  if (normalized === "LICENSING.md") return "licensing";
  return null;
}

function slugToAbsPath(slug: string): string | null {
  if (!SLUG_RE.test(slug)) return null;
  if (slug === "version") return path.join(DOCS_ROOT, "VERSION.md");
  if (slug === "licensing") return path.join(DOCS_ROOT, "LICENSING.md");
  const publicPath = path.join(DOCS_ROOT, "public", `${slug}.md`);
  if (fs.existsSync(publicPath)) return publicPath;
  return null;
}

function isPublishableRelPath(relPath: string) {
  const normalized = relPath.replace(/\\/g, "/");
  return (
    (normalized.startsWith("public/") && normalized.endsWith(".md")) ||
    normalized === "VERSION.md" ||
    normalized === "LICENSING.md"
  );
}

function extractHeadings(content: string): DocHeading[] {
  const headings: DocHeading[] = [];
  for (const line of content.split("\n")) {
    const match = line.match(/^(#{2,3})\s+(.+)$/);
    if (!match) continue;
    const level = match[1].length as 2 | 3;
    const text = match[2]
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .trim();
    headings.push({ id: slugify(text), text, level });
  }
  return headings;
}

function addHeadingIds(html: string, headings: DocHeading[]) {
  let h2 = 0;
  let h3 = 0;
  return html.replace(/<h([23])>(.*?)<\/h\1>/g, (_, level: string, inner: string) => {
    const pool =
      level === "2"
        ? headings.filter((h) => h.level === 2)
        : headings.filter((h) => h.level === 3);
    const idx = level === "2" ? h2++ : h3++;
    const id = pool[idx]?.id ?? slugify(inner.replace(/<[^>]+>/g, ""));
    return `<h${level} id="${id}" class="wf-doc-anchor">${inner}</h${level}>`;
  });
}

function renderMarkdown(content: string, headings: DocHeading[]) {
  const html = marked.parse(content, { async: false }) as string;
  const withoutTitle = html.replace(/^\s*<h1[^>]*>[\s\S]*?<\/h1>\s*/i, "");
  return addHeadingIds(withoutTitle, headings);
}

export function getDocsNavigation(): DocNavSection[] {
  if (!fs.existsSync(README_PATH)) return [];

  const readme = fs.readFileSync(README_PATH, "utf8");
  const sections: DocNavSection[] = [];
  const seen = new Set<string>();

  const parts = readme.split(/^## /m).slice(1);
  for (const part of parts) {
    const [titleLine, ...rest] = part.split("\n");
    const title = titleLine.trim();
    if (title === "Maintainer layout") break;

    const items: DocNavItem[] = [];
    for (const line of rest) {
      const match = line.match(/^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*([^|]*)\|/);
      if (!match) continue;

      const relPath = match[2].replace(/^\.\//, "");
      if (!isPublishableRelPath(relPath)) continue;

      const slug = relPathToSlug(relPath);
      if (!slug || seen.has(slug)) continue;
      seen.add(slug);

      const absPath = slugToAbsPath(slug);
      if (!absPath || !fs.existsSync(absPath)) continue;

      const content = fs.readFileSync(absPath, "utf8");
      items.push({
        slug,
        label: titleFromMarkdown(content, match[1]),
        description: match[3].trim() || undefined,
      });
    }

    if (items.length > 0) sections.push({ title, items });
  }

  return sections;
}

export function listDocSlugs(): string[] {
  const slugs = new Set<string>();
  for (const section of getDocsNavigation()) {
    for (const item of section.items) slugs.add(item.slug);
  }
  return [...slugs];
}

export function getDocPage(slug: string): DocPage | null {
  const absPath = slugToAbsPath(slug);
  if (!absPath || !fs.existsSync(absPath)) return null;

  const content = fs.readFileSync(absPath, "utf8");
  const headings = extractHeadings(content);
  const html = renderMarkdown(content, headings);

  const navItem = getDocsNavigation()
    .flatMap((s) => s.items)
    .find((i) => i.slug === slug);

  return {
    slug,
    title: titleFromMarkdown(content, slug),
    description: navItem?.description,
    sourcePath: path.relative(DOCS_ROOT, absPath).replace(/\\/g, "/"),
    content,
    html,
    headings,
  };
}

export function getDefaultDocSlug() {
  return getDocsNavigation()[0]?.items[0]?.slug ?? "overview";
}
