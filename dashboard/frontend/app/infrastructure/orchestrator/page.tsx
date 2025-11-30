"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components";
import OrchestratorHeader from "@/components/OrchestratorHeader";
import { Loader2, Settings, Server, Network, Key, Globe } from "lucide-react";

interface Orchestrator {
  id: number;
  name: string;
  deployed: boolean;
  ip?: string;
  grafana_url?: string;
  prometheus_url?: string;
  region?: string;
  zone?: string;
  machine_type?: string;
  gcp_project?: string;
  ssl_email?: string;
  ssh_key_path?: string;
  ssh_public_key_path?: string;
  ssh_user?: string;
}

// Shimmer animation styles
const shimmerStyles = `
  @keyframes shimmer {
    0% {
      background-position: -1000px 0;
    }
    100% {
      background-position: 1000px 0;
    }
  }
  
  .skeleton-shimmer {
    animation: shimmer 2s infinite linear;
    background: linear-gradient(to right, #eef2f5 4%, #ffffff 25%, #eef2f5 36%);
    background-size: 1000px 100%;
  }
`;

export default function OrchestratorConfigurationPage() {
  const [orchestrator, setOrchestrator] = useState<Orchestrator | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchOrchestrator = async () => {
      try {
        const response = await fetch("http://localhost:8401/api/projects/orchestrator");
        if (!response.ok) {
          throw new Error("Failed to fetch orchestrator");
        }
        const data = await response.json();
        setOrchestrator(data);
      } catch (err) {
        console.error("Failed to fetch orchestrator:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchOrchestrator();
  }, []);

  if (loading) {
    return (
      <div>
        <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
        <OrchestratorHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: "Infrastructure", href: "/" },
              { label: "Orchestrator", href: "/infrastructure/orchestrator" },
            ]}
            menuLabel="Configuration"
            title="Orchestrator Configuration"
          />

          {/* Skeleton */}
          <div className="space-y-6 mt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(4)].map((_, idx) => (
                <div key={idx} className="h-[250px] rounded-lg skeleton-shimmer"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !orchestrator) {
    return (
      <div>
        <OrchestratorHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: "Infrastructure", href: "/" },
              { label: "Orchestrator", href: "/infrastructure/orchestrator" },
            ]}
            menuLabel="Configuration"
            title="Orchestrator Configuration"
          />
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">
              {error || "Orchestrator not found. Run `superdeploy orchestrator:init` to set up."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <OrchestratorHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Infrastructure", href: "/" },
            { label: "Orchestrator", href: "/infrastructure/orchestrator" },
          ]}
          menuLabel="Configuration"
          title="Orchestrator Configuration"
        />

        {!orchestrator.deployed && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-yellow-700 text-sm">
              Orchestrator is not deployed yet. Run <code className="bg-yellow-100 px-2 py-0.5 rounded">superdeploy orchestrator:up</code> to deploy.
            </p>
          </div>
        )}

        <div className="space-y-6 mt-6">
          {/* Orchestrator Configuration Section */}
          <div>
            <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
              <Settings className="w-4 h-4" />
              Orchestrator Configuration
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Status & Info */}
              <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                      <Settings className="w-6 h-6 text-purple-600" />
                    </div>
                    <div>
                      <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">Status</h3>
                    </div>
                  </div>
                </div>

                <div className="flex items-baseline gap-2 mb-3">
                  <span className="text-[21px] text-[#0a0a0a] capitalize">
                    Orchestrator
                  </span>
                  {orchestrator.deployed && (
                    <span className="px-2 py-0.5 bg-green-50 text-green-700 text-[10px] font-medium rounded-full">
                      ● Running
                    </span>
                  )}
                </div>

                <div className="pt-3 border-t border-[#e3e8ee]">
                  <div className="mb-2">
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">External IP</p>
                    <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                      {orchestrator.ip || "-"}
                    </code>
                  </div>
                  <div>
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">SSL Email</p>
                    <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                      {orchestrator.ssl_email || "-"}
                    </code>
                  </div>
                </div>
              </div>

              {/* GCP Configuration */}
              <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                      <Server className="w-6 h-6 text-orange-600" />
                    </div>
                    <div>
                      <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">GCP Configuration</h3>
                    </div>
                  </div>
                </div>

                <div className="flex items-baseline gap-1 mb-3">
                  <span className="text-[21px] text-[#0a0a0a]">
                    {orchestrator.gcp_project || "-"}
                  </span>
                </div>

                <div className="pt-3 border-t border-[#e3e8ee]">
                  <div className="mb-2">
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Region</p>
                    <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                      {orchestrator.region || "-"}
                    </code>
                  </div>
                  <div className="mb-2">
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Zone</p>
                    <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                      {orchestrator.zone || "-"}
                    </code>
                  </div>
                  <div>
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Machine Type</p>
                    <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                      {orchestrator.machine_type || "-"}
                    </code>
                  </div>
                </div>
              </div>

              {/* SSH Configuration */}
              <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                      <Key className="w-6 h-6 text-purple-600" />
                    </div>
                    <div>
                      <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">SSH Configuration</h3>
                    </div>
                  </div>
                </div>

                <div className="flex items-baseline gap-1 mb-3">
                  <span className="text-[21px] text-[#0a0a0a]">
                    {orchestrator.ssh_user || "-"}
                  </span>
                </div>

                <div className="pt-3 border-t border-[#e3e8ee]">
                  <div className="mb-2">
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Key Path</p>
                    <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light truncate">
                      {orchestrator.ssh_key_path || "-"}
                    </code>
                  </div>
                  <div>
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Public Key Path</p>
                    <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light truncate">
                      {orchestrator.ssh_public_key_path || "-"}
                    </code>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div>
            <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
              <Globe className="w-4 h-4" />
              Quick Actions
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {orchestrator.grafana_url && (
                <a
                  href={orchestrator.grafana_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg flex items-center gap-3"
                >
                  <div className="w-10 h-10 flex items-center p-2 justify-center bg-orange-50 rounded-lg shrink-0">
                    <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#F46800">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/>
                      <circle cx="12" cy="12" r="5"/>
                    </svg>
                  </div>
                  <div>
                    <p className="text-[14px] text-[#0a0a0a] font-medium">Open Grafana</p>
                    <p className="text-[11px] text-[#8b8b8b]">Metrics & Dashboards</p>
                  </div>
                </a>
              )}
              {orchestrator.prometheus_url && (
                <a
                  href={orchestrator.prometheus_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg flex items-center gap-3"
                >
                  <div className="w-10 h-10 flex items-center p-2 justify-center bg-red-50 rounded-lg shrink-0">
                    <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#E6522C">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                  </div>
                  <div>
                    <p className="text-[14px] text-[#0a0a0a] font-medium">Open Prometheus</p>
                    <p className="text-[11px] text-[#8b8b8b]">Time Series Database</p>
                  </div>
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
