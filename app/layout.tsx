import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Syllabus Expert",
  description: "Parse and structure course syllabus text",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, padding: 0 }}>
        {children}
      </body>
    </html>
  );
}
