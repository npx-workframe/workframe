import type { MetadataRoute } from "next";

import { listDocSlugs } from "@/lib/docs";
import { siteUrl } from "@/lib/site-metadata";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: siteUrl, lastModified: now, changeFrequency: "weekly", priority: 1 },
    ...listDocSlugs().map((slug) => ({
      url: `${siteUrl}/docs/${slug}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: 0.7,
    })),
  ];
}
