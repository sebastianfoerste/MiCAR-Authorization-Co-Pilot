import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MiCAR Authorization Co-Pilot",
  description: "Internal tool for ART, EMT, and CASP licensing packages.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
