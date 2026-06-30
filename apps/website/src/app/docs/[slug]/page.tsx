import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DocsArticle } from "@/components/docs/docs-article";
import { DocsShell } from "@/components/docs/docs-shell";
import { getDocPage, getDocsNavigation, listDocSlugs } from "@/lib/docs";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return listDocSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const page = getDocPage(slug);
  if (!page) return { title: "Docs · Workframe" };
  return {
    title: `${page.title} · Workframe Docs`,
    description: page.description,
  };
}

export default async function DocPage({ params }: PageProps) {
  const { slug } = await params;
  const page = getDocPage(slug);
  if (!page) notFound();

  const sections = getDocsNavigation();

  return (
    <DocsShell sections={sections}>
      <DocsArticle page={page} />
    </DocsShell>
  );
}
