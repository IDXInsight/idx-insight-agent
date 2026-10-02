import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  // Absolute URL for social previews; set on the deployment (e.g. the Vercel domain).
  metadataBase: process.env.NEXT_PUBLIC_SITE_URL ? new URL(process.env.NEXT_PUBLIC_SITE_URL) : undefined,
  openGraph: { title: "IDX Insight — Temukan konteks. Pahami yang penting.", images: [{ url: "/og.png", width: 1536, height: 1024, alt: "IDX Insight research workspace" }] },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
  title: "IDX Insight — Ruang riset emiten IDX",
  description: "Agen riset untuk emiten IDX: temukan disclosure yang perlu dipantau, pahami konteks keuangannya, dan telusuri bukti setiap temuan dari data Sectors. Informasi dan analisis, bukan rekomendasi investasi.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="id" className="dark"><body>{children}</body></html>;
}
