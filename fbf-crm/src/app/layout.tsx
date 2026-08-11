import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FBF CRM",
  description: "Forged by Freedom — clients, inventory, and orders",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "FBF CRM",
    statusBarStyle: "black-translucent",
  },
  icons: {
    icon: "/icon-192.svg",
    apple: "/icon-192.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#ff6a00",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
