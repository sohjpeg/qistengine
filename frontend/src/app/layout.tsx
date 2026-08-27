import type { Metadata } from "next";
import localFont from "next/font/local";
import { Toaster } from "sonner";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

const plexSans = localFont({
  variable: "--font-plex-sans",
  display: "swap",
  src: [
    { path: "../../public/fonts/ibm-plex-sans-400.woff2", weight: "400", style: "normal" },
    { path: "../../public/fonts/ibm-plex-sans-500.woff2", weight: "500", style: "normal" },
    { path: "../../public/fonts/ibm-plex-sans-600.woff2", weight: "600", style: "normal" },
  ],
});

const plexMono = localFont({
  variable: "--font-plex-mono",
  display: "swap",
  src: [
    { path: "../../public/fonts/ibm-plex-mono-400.woff2", weight: "400", style: "normal" },
    { path: "../../public/fonts/ibm-plex-mono-500.woff2", weight: "500", style: "normal" },
    { path: "../../public/fonts/ibm-plex-mono-600.woff2", weight: "600", style: "normal" },
  ],
});

const plexSerif = localFont({
  variable: "--font-plex-serif",
  display: "swap",
  src: [
    { path: "../../public/fonts/ibm-plex-serif-500.woff2", weight: "500", style: "normal" },
    { path: "../../public/fonts/ibm-plex-serif-600.woff2", weight: "600", style: "normal" },
  ],
});

const nastaliq = localFont({
  variable: "--font-nastaliq",
  display: "swap",
  src: [{ path: "../../public/fonts/noto-nastaliq-urdu-400.woff2", weight: "400", style: "normal" }],
});

export const metadata: Metadata = {
  title: "QistEngine — alternative credit scoring",
  description:
    "Alternative credit scoring for unbanked individuals and micro-merchants in Pakistan. Demonstration model on synthetic data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      dir="ltr"
      className={`${plexSans.variable} ${plexMono.variable} ${plexSerif.variable} ${nastaliq.variable}`}
    >
      <body>
        <SiteHeader />
        <main className="mx-auto w-full max-w-content px-6 py-6">{children}</main>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "var(--surface)",
              border: "1px solid var(--rule)",
              borderRadius: "var(--r-md)",
              boxShadow: "var(--shadow-pop)",
              color: "var(--ink)",
              fontFamily: "var(--font-plex-sans), sans-serif",
              fontSize: "14px",
            },
          }}
        />
      </body>
    </html>
  );
}
