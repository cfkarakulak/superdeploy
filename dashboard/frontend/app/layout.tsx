import type { Metadata } from "next";
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
      <body className="antialiased">
        <div className="min-h-screen">
          <div className="max-w-[820px] mx-auto px-8 py-6">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
