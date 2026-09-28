import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://idx-insight-design.philosatriya.chatgpt.site"),
  openGraph: { title: "IDX Insight — Temukan konteks. Pahami yang penting.", images: [{ url: "/og.png", width: 1536, height: 1024, alt: "IDX Insight research workspace" }] },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
  title: "IDX Insight — Ruang riset perbankan",
  description: "Prototipe IDX Insight Agent. Temukan disclosure, pahami konteks, dan telusuri bukti. Semua angka dan kejadian adalah ilustrasi desain.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="id" className="dark"><body>{children}</body></html>;
}
