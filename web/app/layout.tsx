import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Photo Checker",
  description: "Smart photo deduplication",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#060a10] min-h-screen">
        {children}
      </body>
    </html>
  );
}
