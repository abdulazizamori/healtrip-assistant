import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealTrip Care Guide",
  description: "Prototype: AI patient decision assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // dir/lang are switched on the client by the language toggle
  return (
    <html lang="en" dir="ltr">
      <body>{children}</body>
    </html>
  );
}
