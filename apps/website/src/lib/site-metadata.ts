import type { Metadata } from "next";

export const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://workfra.me";

export const siteName = "Workframe";

export const siteTitle =
  "Workframe. A workspace for humans and persistent AI coworkers.";

export const siteDescription =
  "Communities exchange messages. Workframe teams exchange work.";

export const ogImage = {
  url: "/og-default.png",
  width: 1200,
  height: 630,
  alt: "Workframe. A workspace for humans and persistent AI coworkers.",
  type: "image/png",
} as const;

export const openGraphDefaults = {
  type: "website" as const,
  locale: "en_US",
  siteName,
  images: [ogImage],
};

export const twitterDefaults = {
  card: "summary_large_image" as const,
  images: [ogImage.url],
};

export function docCanonical(slug: string) {
  return `${siteUrl}/docs/${slug}`;
}

export function mergePageMetadata(
  partial: Metadata,
  path: string,
): Metadata {
  const url = path.startsWith("http") ? path : `${siteUrl}${path}`;
  return {
    ...partial,
    alternates: { canonical: url, ...partial.alternates },
    openGraph: {
      ...openGraphDefaults,
      url,
      ...partial.openGraph,
      images: partial.openGraph?.images ?? [ogImage],
    },
    twitter: {
      ...twitterDefaults,
      ...partial.twitter,
      images: partial.twitter?.images ?? [ogImage.url],
    },
  };
}
