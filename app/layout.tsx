import type { Metadata } from "next";
import "./globals.css";

const title = "Significance — claim-state records for AI-assisted mathematics";
const description =
  "Attributable, version-bound records of mathematical claims, evidence, interpretations, and open verification needs.";

export const metadata: Metadata = {
  title,
  description,
  openGraph: { title, description },
  twitter: { card: "summary", title, description },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
