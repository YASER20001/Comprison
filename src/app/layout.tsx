import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ComprisonTool - Advanced File Comparison System",
  description: "Professional file comparison tool with Excel export and visual dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
