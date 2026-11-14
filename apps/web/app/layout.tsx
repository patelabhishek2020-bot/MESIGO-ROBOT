import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mesigo AI",
  description: "Autonomous Import-Export Business Operating System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;650;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="grid-bg" />
        <div className="scanline" />
        {children}
      </body>
    </html>
  );
}
