import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "AI Data Profiler — Understand Your Dataset Before You Build Your Model",
  description:
    "Upload a CSV or Excel file and automatically discover data-quality problems, statistical patterns, ML-readiness issues, and actionable recommendations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
