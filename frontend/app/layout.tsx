import "./globals.css";
import React from "react";

export const metadata = {
  title: "Bright Smile Dental - Voice Assistant",
  description: "Deterministic rule-based dental appointment voice assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
