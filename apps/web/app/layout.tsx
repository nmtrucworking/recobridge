import type { Metadata } from "next";
import { Manrope, Space_Grotesk } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-body",
  subsets: ["latin", "vietnamese"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin", "vietnamese"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const origin = `${protocol}://${host}`;

  return {
    title: "RecoBridge — Gợi ý đúng gu",
    description: "Trải nghiệm mua sắm cá nhân hóa được vận hành bởi RecoEngine.",
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: {
      title: "RecoBridge — Gu của bạn, được hiểu đúng.",
      description: "Kết nối dữ liệu, cá nhân hóa lựa chọn.",
      type: "website",
      locale: "vi_VN",
      url: origin,
      images: [{ url: `${origin}/og.png`, width: 1200, height: 630, alt: "RecoBridge — Gu của bạn, được hiểu đúng." }],
    },
    twitter: {
      card: "summary_large_image",
      title: "RecoBridge — Gu của bạn, được hiểu đúng.",
      description: "Kết nối dữ liệu, cá nhân hóa lựa chọn.",
      images: [`${origin}/og.png`],
    },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body className={`${manrope.variable} ${spaceGrotesk.variable}`}>{children}</body>
    </html>
  );
}
