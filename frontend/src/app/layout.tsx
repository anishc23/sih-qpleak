import type { Metadata } from "next";
import { Archivo, Eczar, Spline_Sans_Mono } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

// Drawn by Rosetta for scholarly publishing in India; Latin and Devanagari
// come from the same family, which an Indian examination board will need.
const display = Eczar({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

// A grotesque drawn for print forms. This application is mostly dense tables
// at 12-13px, which is exactly where it holds.
const body = Archivo({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
  display: "swap",
});

// Even colour across 64 characters, so a SHA-256 digest reads as a woven band
// rather than noise, with 0/O and 1/l kept apart for hash comparison by eye.
const mono = Spline_Sans_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SecureLock — Examination Custody Register",
  description:
    "Questions are sealed as they are written, every hand-off is recorded, and the finished paper does not open until the contract's hour.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
