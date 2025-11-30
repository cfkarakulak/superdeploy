"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components";
import OrchestratorHeader from "@/components/OrchestratorHeader";
import { Loader2, Database, ExternalLink } from "lucide-react";

interface Orchestrator {
  id: number;
  name: string;
  deployed: boolean;
  ip?: string;
  grafana_url?: string;
  prometheus_url?: string;
}

interface MonitoringAddon {
  name: string;
  type: string;
  description: string;
  url?: string;
  status: "running" | "stopped" | "not_configured";
  icon: React.ReactNode;
  bgColor: string;
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

// Grafana Logo
const GrafanaLogo = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#F46800">
    <path d="M22.04 11.73c-.04-.55-.08-1.09-.26-1.58-.1-.3-.23-.57-.4-.82-.18-.26-.38-.5-.63-.71a4.64 4.64 0 00-2.19-1.05c-.44-.1-.9-.1-1.33-.02-.18.03-.37.08-.55.15-.04.01-.07.02-.1.04-.03-.07-.05-.14-.09-.21-.55-1.02-1.48-1.77-2.55-2.14-.53-.19-1.09-.27-1.66-.25-.6.03-1.2.18-1.74.44-.27.13-.52.28-.76.46-.04.03-.07.06-.11.09-.02-.02-.04-.04-.06-.06a5.4 5.4 0 00-1.05-.7c-.68-.34-1.43-.5-2.18-.46-.74.05-1.46.27-2.1.66-.63.39-1.17.92-1.57 1.55-.2.32-.37.67-.48 1.04-.12.37-.18.76-.18 1.14 0 .2.02.39.05.59.01.09.03.17.05.26-.08.03-.16.05-.24.09-.82.32-1.52.88-2.02 1.6-.5.71-.77 1.54-.78 2.38-.01.42.05.85.18 1.25.13.4.32.78.57 1.12.25.34.55.65.9.9.35.25.74.45 1.15.58.21.07.42.11.64.15.11.01.23.03.34.03.03.09.07.18.11.27.32.69.81 1.28 1.42 1.73.6.45 1.3.77 2.04.91.37.07.75.1 1.12.08.38-.02.75-.09 1.11-.21.36-.12.7-.29 1.02-.51.16-.11.31-.23.45-.37.04.05.09.1.14.14.6.54 1.34.91 2.13 1.1.78.18 1.6.17 2.38-.03.39-.1.76-.25 1.11-.45.35-.2.68-.44.97-.73.14-.14.28-.29.4-.46.04.03.08.05.12.08.74.45 1.6.69 2.46.67.43-.01.86-.08 1.27-.22.41-.14.8-.35 1.14-.61.34-.27.65-.59.9-.95.25-.36.44-.77.56-1.2.06-.21.1-.43.12-.66.01-.11.02-.23.02-.34.06-.02.12-.04.18-.07.66-.27 1.23-.7 1.68-1.24.45-.54.78-1.18.94-1.87.08-.34.12-.69.12-1.04 0-.35-.04-.71-.13-1.05-.09-.34-.22-.67-.4-.97-.18-.31-.4-.59-.66-.83-.13-.12-.26-.24-.41-.35-.07-.05-.15-.1-.22-.15.02-.06.03-.11.05-.17z"/>
    <circle cx="12" cy="12" r="4.5" fill="white"/>
    <circle cx="12" cy="12" r="3" fill="#F46800"/>
  </svg>
);

// Prometheus Logo
const PrometheusLogo = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#E6522C">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/>
    <path d="M12 6v12M8 10l4-4 4 4M8 14l4 4 4-4" fill="none" stroke="#E6522C" strokeWidth="1.5"/>
  </svg>
);

// Loki Logo
const LokiLogo = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6" fill="#F9A825">
    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
    <path d="M2 17l10 5 10-5" fill="none" stroke="#F9A825" strokeWidth="2"/>
    <path d="M2 12l10 5 10-5" fill="none" stroke="#F9A825" strokeWidth="2"/>
  </svg>
);

export default function OrchestratorAddonsPage() {
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

  // Build monitoring addons list
  const getMonitoringAddons = (): MonitoringAddon[] => {
    if (!orchestrator) return [];

    return [
      {
        name: "Grafana",
        type: "grafana",
        description: "Metrics visualization and dashboards",
        url: orchestrator.grafana_url,
        status: orchestrator.grafana_url ? "running" : "not_configured",
        icon: <GrafanaLogo />,
        bgColor: "bg-orange-50",
      },
      {
        name: "Prometheus",
        type: "prometheus",
        description: "Time series database and alerting",
        url: orchestrator.prometheus_url,
        status: orchestrator.prometheus_url ? "running" : "not_configured",
        icon: <PrometheusLogo />,
        bgColor: "bg-red-50",
      },
      {
        name: "Loki",
        type: "loki",
        description: "Log aggregation system",
        url: orchestrator.ip ? `http://${orchestrator.ip}:3100` : undefined,
        status: orchestrator.deployed ? "running" : "not_configured",
        icon: <LokiLogo />,
        bgColor: "bg-amber-50",
      },
    ];
  };

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
            menuLabel="Addons"
            title="Monitoring Services"
          />

          {/* Skeleton */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, idx) => (
              <div key={idx} className="h-40 rounded-lg skeleton-shimmer"></div>
            ))}
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
            menuLabel="Addons"
            title="Monitoring Services"
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

  const addons = getMonitoringAddons();

  return (
    <div>
      <OrchestratorHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Infrastructure", href: "/" },
            { label: "Orchestrator", href: "/infrastructure/orchestrator" },
          ]}
          menuLabel="Addons"
          title="Monitoring Services"
        />

        {!orchestrator.deployed && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-yellow-700 text-sm">
              Orchestrator is not deployed. Run <code className="bg-yellow-100 px-2 py-0.5 rounded">superdeploy orchestrator:up</code> to deploy monitoring services.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {addons.map((addon) => (
            <div
              key={addon.name}
              className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 flex items-center p-2 justify-center rounded-lg border border-[#e3e8ee] shrink-0 ${addon.bgColor}`}>
                    {addon.icon}
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">
                      Monitoring
                    </h3>
                  </div>
                </div>
              </div>

              {/* Name */}
              <div className="flex items-baseline gap-2 mb-3">
                <span className="text-[21px] text-[#0a0a0a]">
                  {addon.name}
                </span>
                {addon.status === "running" && (
                  <span className="px-2 py-0.5 bg-green-50 text-green-700 text-[10px] font-medium rounded-full">
                    ● Running
                  </span>
                )}
              </div>

              {/* Description */}
              <div className="pt-3 border-t border-[#e3e8ee] mb-3">
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Description</p>
                <p className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">
                  {addon.description}
                </p>
              </div>

              {/* Open Link */}
              {addon.url && (
                <a
                  href={addon.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-[11px] text-blue-600 hover:text-blue-700 font-medium"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open {addon.name}
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

