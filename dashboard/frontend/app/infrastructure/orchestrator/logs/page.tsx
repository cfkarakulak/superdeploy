"use client";

import { PageHeader } from "@/components";
import OrchestratorHeader from "@/components/OrchestratorHeader";
import { Terminal } from "lucide-react";

export default function OrchestratorLogsPage() {
  return (
    <div>
      <OrchestratorHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Infrastructure", href: "/" },
            { label: "Orchestrator", href: "/infrastructure/orchestrator" },
          ]}
          menuLabel="Logs"
          title="Aggregated Logs"
        />

        <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
          <div className="w-16 h-16 bg-[#f6f8fa] rounded-full flex items-center justify-center mx-auto mb-4">
            <Terminal className="w-6 h-6 text-[#8b8b8b]" />
          </div>
          <p className="text-[14px] text-[#0a0a0a] mb-2">View logs via CLI</p>
          <p className="text-[13px] text-[#8b8b8b] max-w-md mx-auto mb-4">
            Use the SuperDeploy CLI to stream logs from all your projects
          </p>
          <code className="inline-block bg-[#f6f8fa] px-4 py-2 rounded text-[13px] font-mono text-[#0a0a0a]">
            superdeploy cheapa:logs
          </code>
        </div>
      </div>
    </div>
  );
}

