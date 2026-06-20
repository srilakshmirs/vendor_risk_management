import "@repo/ui/styles.css";
import "./globals.css";
import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { Sidebar } from "../components/Sidebar";
import { ThemeProvider } from "../components/ThemeProvider";

export const metadata: Metadata = {
  title: "VRM Intelligence — Société Générale TPRM",
  description:
    "AI-powered third-party vendor risk management. 400 vendors, 7 anomaly types, continuous scoring.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={GeistSans.className}>
        <ThemeProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 flex flex-col min-w-0">{children}</main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
