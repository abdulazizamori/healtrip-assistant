import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans_Arabic } from "next/font/google";
import "./globals.css";

// one typeface with both Arabic and Latin glyphs, so the two languages share size, weight and rhythm
const font = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-ui",
});

export const metadata: Metadata = {
  title: "HealTrip Care Guide",
  description: "Prototype: AI patient decision assistant",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // dir/lang are switched on the client by the language toggle
  return (
    <html lang="en" dir="ltr" className={font.variable} suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
