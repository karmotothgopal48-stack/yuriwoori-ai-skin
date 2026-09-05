import type { Metadata } from "next";
import { Cormorant, Inter } from "next/font/google";
import "./globals.css";

const cormorant = Cormorant({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-cormorant",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "YuriWoori — Understand your skin.",
  description: "AI-powered skin analysis and personalized Korean skincare routines.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${cormorant.variable} ${inter.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}