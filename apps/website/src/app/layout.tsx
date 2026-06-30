import type { Metadata, Viewport } from "next";
import { Inter_Tight, JetBrains_Mono } from "next/font/google";

import { PwaRegister } from "@/components/pwa-register";
import { SiteScrollRoot } from "@/components/site-scroll-root";
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

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://workfra.me";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#e0e0e6",
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Workframe",
  description:
    "The Social OS for Autonomous Businesses. Install a private workspace where humans and agents collaborate.",
  applicationName: "Workframe",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/favicon.svg",
    apple: "/favicon.svg",
  },
  openGraph: {
    type: "website",
    url: siteUrl,
    siteName: "Workframe",
    title: "Workframe",
    description:
      "The Social OS for Autonomous Businesses. Install a private workspace where humans and agents collaborate.",
    images: [{ url: "/demo-poster.png", width: 1200, height: 630, alt: "Workframe" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Workframe",
    description:
      "The Social OS for Autonomous Businesses. Install a private workspace where humans and agents collaborate.",
    images: ["/demo-poster.png"],
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
