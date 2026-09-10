import type { Metadata, Viewport } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/query-provider";
import { ThemeProvider } from "@/components/theme-provider";
import { PwaProvider } from "@/components/pwa-provider";

export const metadata: Metadata = {
  applicationName: "Sway",
  title: "Sway",
  description: "Tasks, calendar, reminders, and Google Calendar import in one focused app.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Sway",
  },
  icons: {
    icon: [
      { url: "/icons/sway-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/sway-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/sway-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/sway-180.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f5f7" },
    { media: "(prefers-color-scheme: dark)", color: "#12161d" },
  ],
  viewportFit: "cover",
  width: "device-width",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>
          <PwaProvider>
            <QueryProvider>{children}</QueryProvider>
          </PwaProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
