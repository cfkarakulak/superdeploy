import type { Metadata } from "next";
import { Header } from "@/components/Header";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "SuperDeploy Dashboard",
  description: "Heroku-like management dashboard for SuperDeploy",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-white">
        <div className="min-h-screen flex flex-col">
          <Header />
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
