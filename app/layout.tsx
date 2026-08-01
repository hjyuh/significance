import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const title = "Significance — claim-state records for AI-assisted mathematics";
const description =
  "Attributable, version-bound records of mathematical claims, evidence, interpretations, and open verification needs.";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "significance-math.example";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "https";
  const metadataBase = new URL(`${protocol}://${host}`);
  const image = new URL("/og.png", metadataBase).toString();

  return {
    metadataBase,
    title,
    description,
    openGraph: { title, description, images: [{ url: image, width: 1743, height: 909 }] },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
