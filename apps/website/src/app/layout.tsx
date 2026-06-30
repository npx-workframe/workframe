import type { Metadata, Viewport } from "next";
import { Inter_Tight, JetBrains_Mono } from "next/font/google";

import { PwaRegister } from "@/components/pwa-register";
import { SiteScrollRoot } from "@/components/site-scroll-root";
import {
  ogImage,
  openGraphDefaults,
  siteDescription,
  siteName,
  siteTitle,
  siteUrl,
  twitterDefaults,
} from "@/lib/site-metadata";
import "./globals.css";

const interTight = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#e0e0e6",
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: siteTitle,
    template: `%s · ${siteName}`,
  },
  description: siteDescription,
  applicationName: siteName,
  keywords: [
    "Workframe",
    "Hermes",
    "AI agents",
    "autonomous business",
    "multi-agent",
    "self-hosted",
    "BYOK",
    "agent workspace",
    "create-workframe",
  ],
  authors: [{ name: siteName, url: siteUrl }],
  creator: siteName,
  publisher: siteName,
  category: "technology",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/favicon.svg",
    apple: "/favicon.svg",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    ...openGraphDefaults,
    url: siteUrl,
    title: siteTitle,
    description: siteDescription,
    images: [ogImage],
  },
  twitter: {
    ...twitterDefaults,
    title: siteTitle,
    description: siteDescription,
    images: [ogImage.url],
  },
  alternates: {
    canonical: siteUrl,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${interTight.variable} ${jetbrainsMono.variable} h-full overflow-hidden`}
    >
      <body className="flex h-full min-h-0 flex-col overflow-hidden font-[family-name:var(--wf-font-sans)]">
        <SiteScrollRoot>
          <PwaRegister />
          {children}
        </SiteScrollRoot>
      </body>
    </html>
  );
}
