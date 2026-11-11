import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "ForgeSight AI — Industrial AI Intelligence Platform",
  description:
    "Machine Learning, Deep Learning, Computer Vision, RAG, and AI Agents for manufacturing quality, predictive maintenance, and operational intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
