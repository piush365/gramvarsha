import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GramVarsha — Panchayat-level Weather Advisory",
  description:
    "Terrain-aware rainfall and temperature downscaling with crop-specific advisories for Sangli district panchayats.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
