import type { Metadata } from "next";
import "../styles/globals.css";
import { DeploymentLogProvider } from "@/contexts/DeploymentLogContext";
import GlobalDeploymentLog from "@/components/GlobalDeploymentLog";

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
        <DeploymentLogProvider>
          <div className="min-h-screen">
            <div className="max-w-[760px] mx-auto px-8 py-6">
              {children}
            </div>
          </div>
          <GlobalDeploymentLog />
        </DeploymentLogProvider>
      </body>
    </html>
  );
}
