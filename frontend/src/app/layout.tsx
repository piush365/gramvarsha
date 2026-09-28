import type { Metadata, Viewport } from "next";
import {
  IBM_Plex_Mono,
  IBM_Plex_Sans,
  IBM_Plex_Sans_Condensed,
  IBM_Plex_Sans_Devanagari,
  Tiro_Devanagari_Hindi,
  Tiro_Devanagari_Marathi,
} from "next/font/google";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import SiteHeader from "@/components/SiteHeader";

const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-plex" });
const plexDeva = IBM_Plex_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-deva",
});
const plexCond = IBM_Plex_Sans_Condensed({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-plex-cond" });
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono" });
const tiroMr = Tiro_Devanagari_Marathi({ subsets: ["devanagari"], weight: "400", variable: "--font-tiro-mr" });
const tiroHi = Tiro_Devanagari_Hindi({ subsets: ["devanagari"], weight: "400", variable: "--font-tiro-hi" });

export const metadata: Metadata = {
  title: "GramVarsha AI · Panchayat-level weather advisories",
  description:
    "Downscales the block-level weather forecast to every gram panchayat in Miraj taluka, Sangli, with explainable ML and crop advisories in Marathi, Hindi and English. SIH26074.",
};

export const viewport: Viewport = { themeColor: "#1B3A5C", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const fonts = [plex, plexDeva, plexCond, plexMono, tiroMr, tiroHi].map((f) => f.variable).join(" ");
  return (
    <html lang="en" className={fonts}>
      <body className="flex min-h-screen flex-col">
        <SiteHeader />
        <div className="flex flex-1 flex-col">{children}</div>
        <footer className="border-t border-line bg-card px-4 py-4 text-xs text-muted sm:px-6">
          Pilot demo: Miraj taluka, Sangli. Coarse forecast from Open-Meteo as IMD proxy; IMD/AWS feeds plug into
          the same pipeline.
          <span className="block pt-1 sm:inline sm:pl-2 sm:pt-0">
            Team Hexadecimal, Walchand College of Engineering, Sangli · SIH26074
          </span>
        </footer>
      </body>
    </html>
  );
}
