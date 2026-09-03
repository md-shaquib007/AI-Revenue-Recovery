import "./globals.css";
import React from "react";

export const metadata = {
  title: "REVIVE | Autonomous Revenue Recovery Agent for Razorpay",
  description: "Financially Safe, Event-Driven Revenue Recovery Agent for Razorpay",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#080c14] text-slate-100 min-h-screen antialiased selection:bg-blue-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}
