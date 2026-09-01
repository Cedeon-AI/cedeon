import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";
import { Providers } from "@/components/providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Cedeon — Reinsurance intelligence from contract to recovery",
    template: "%s · Cedeon",
  },
  description:
    "The intelligence system for ceded reinsurance. Cedeon turns treaties into executable terms, watches losses against them, and opens the desk on one ranked queue — recoveries to review, notices coming due, contract changes, what doesn't reconcile — each backed by a citation, a deterministic calculation and a human decision.",
};

/**
 * Stamp the saved theme onto <html> before first paint so there is no flash.
 * "system" (or nothing saved) leaves the attribute off and lets the OS setting win.
 */
const themeScript = `(function(){try{var t=localStorage.getItem("cedeon-theme");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t;}}catch(e){}})();`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${mono.variable} min-h-dvh antialiased`}>
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: static no-flash theme script, runs before paint */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
