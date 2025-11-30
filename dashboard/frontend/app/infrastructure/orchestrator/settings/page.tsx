"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components";
import OrchestratorHeader from "@/components/OrchestratorHeader";
import { Settings, Trash2 } from "lucide-react";

interface Orchestrator {
  id: number;
  name: string;
  deployed: boolean;
  ip?: string;
}

export default function OrchestratorSettingsPage() {
  const [orchestrator, setOrchestrator] = useState<Orchestrator | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOrchestrator = async () => {
      try {
        const response = await fetch("http://localhost:8401/api/projects/orchestrator");
        if (response.ok) {
          const data = await response.json();
          setOrchestrator(data);
        }
      } catch (err) {
        console.error("Failed to fetch orchestrator:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchOrchestrator();
  }, []);

  return (
    <div>
      <OrchestratorHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Infrastructure", href: "/" },
            { label: "Orchestrator", href: "/infrastructure/orchestrator" },
          ]}
          menuLabel="Settings"
          title="Orchestrator Settings"
        />

        <div className="space-y-6 mt-6">
          {/* Danger Zone */}
          <div>
            <h2 className="flex items-center gap-2 text-[11px] text-red-600 leading-tight tracking-[0.03em] mb-[8px] font-light">
              <Trash2 className="w-4 h-4" />
              Danger Zone
            </h2>
            <div className="border border-red-200 rounded-lg p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-[14px] text-[#0a0a0a] font-medium mb-1">Destroy Orchestrator</h3>
                  <p className="text-[13px] text-[#8b8b8b]">
                    This will permanently delete the orchestrator VM and all monitoring data.
                  </p>
                </div>
                <button
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-[13px] font-medium rounded-lg transition-colors"
                  onClick={() => {
                    alert("Run: superdeploy orchestrator:down");
                  }}
                >
                  Destroy
                </button>
              </div>
              <div className="mt-4 p-3 bg-red-50 rounded">
                <code className="text-[12px] text-red-700 font-mono">
                  superdeploy orchestrator:down
                </code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

