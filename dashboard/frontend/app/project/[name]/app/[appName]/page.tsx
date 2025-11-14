"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";
import { Cpu, MemoryStick, HardDrive, Container, Clock, Activity } from "lucide-react";

interface AppMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  container_count: number;
  uptime_seconds: number;
}

interface MetricsResponse {
  app: string;
  project: string;
  vm_ip: string;
  metrics: AppMetrics;
}

export default function AppOverviewPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [metrics, setMetrics] = useState<AppMetrics | null>(null);
  const [vmIp, setVmIp] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(
          `http://localhost:8401/api/metrics/${projectName}/${appName}/metrics`
        );
        
        if (!response.ok) {
          throw new Error("Failed to fetch metrics");
        }
        
        const data: MetricsResponse = await response.json();
        setMetrics(data.metrics);
        setVmIp(data.vm_ip);
      } catch (err) {
        console.error("Failed to fetch metrics:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    if (projectName && appName) {
      fetchMetrics();
      
      // Refresh metrics every 10 seconds
      const interval = setInterval(fetchMetrics, 10000);
      return () => clearInterval(interval);
    }
  }, [projectName, appName]);

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const getStatusColor = (usage: number) => {
    if (usage >= 90) return "text-red-600 bg-red-50";
    if (usage >= 70) return "text-orange-600 bg-orange-50";
    return "text-green-600 bg-green-50";
  };

  if (loading) {
    return (
      <div>
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumb={{
              label: "Overview",
              href: `/project/${projectName}/app/${appName}`,
            }}
            title="Application Overview"
          />
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-32 bg-[#f7f7f7] rounded-lg"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div>
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumb={{
              label: "Overview",
              href: `/project/${projectName}/app/${appName}`,
            }}
            title="Application Overview"
          />
          
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">Failed to load metrics: {error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumb={{
            label: "Overview",
            href: `/project/${projectName}/app/${appName}`,
          }}
          title="Application Overview"
        />

        {/* VM Info Banner */}
        <div className="mb-6 p-4 bg-[#f7f7f7] rounded-lg border border-[#e3e8ee]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#8b8b8b]" />
              <span className="text-[13px] text-[#8b8b8b]">VM IP:</span>
              <code className="text-[13px] text-[#0a0a0a] font-mono bg-white px-2 py-1 rounded border border-[#e3e8ee]">
                {vmIp}
              </code>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </div>
              <span className="text-[13px] text-green-600 font-medium">Live</span>
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* CPU Usage */}
          <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-50 rounded-lg">
                  <Cpu className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light">CPU Usage</h3>
                </div>
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-[32px] font-semibold text-[#0a0a0a]">
                {metrics.cpu_usage.toFixed(1)}
              </span>
              <span className="text-[16px] text-[#8b8b8b]">%</span>
            </div>
            <div className="mt-3 w-full bg-[#f0f0f0] rounded-full h-1.5">
              <div
                className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(metrics.cpu_usage, 100)}%` }}
              ></div>
            </div>
          </div>

          {/* Memory Usage */}
          <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-50 rounded-lg">
                  <MemoryStick className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light">Memory Usage</h3>
                </div>
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-[32px] font-semibold text-[#0a0a0a]">
                {metrics.memory_usage.toFixed(1)}
              </span>
              <span className="text-[16px] text-[#8b8b8b]">%</span>
            </div>
            <div className="mt-3 w-full bg-[#f0f0f0] rounded-full h-1.5">
              <div
                className="bg-purple-600 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(metrics.memory_usage, 100)}%` }}
              ></div>
            </div>
          </div>

          {/* Disk Usage */}
          <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-50 rounded-lg">
                  <HardDrive className="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light">Disk Usage</h3>
                </div>
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-[32px] font-semibold text-[#0a0a0a]">
                {metrics.disk_usage.toFixed(1)}
              </span>
              <span className="text-[16px] text-[#8b8b8b]">%</span>
            </div>
            <div className="mt-3 w-full bg-[#f0f0f0] rounded-full h-1.5">
              <div
                className="bg-orange-600 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(metrics.disk_usage, 100)}%` }}
              ></div>
            </div>
          </div>

          {/* Containers */}
          <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-teal-50 rounded-lg">
                  <Container className="w-5 h-5 text-teal-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light">Running Containers</h3>
                </div>
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-[32px] font-semibold text-[#0a0a0a]">
                {metrics.container_count}
              </span>
              <span className="text-[16px] text-[#8b8b8b]">active</span>
            </div>
            <div className="mt-3">
              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium ${
                metrics.container_count > 0 ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-700"
              }`}>
                {metrics.container_count > 0 ? "Healthy" : "No containers"}
              </span>
            </div>
          </div>

          {/* Uptime */}
          <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-50 rounded-lg">
                  <Clock className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light">System Uptime</h3>
                </div>
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-[32px] font-semibold text-[#0a0a0a]">
                {formatUptime(metrics.uptime_seconds)}
              </span>
            </div>
            <div className="mt-3">
              <span className="text-[12px] text-[#8b8b8b]">
                {Math.floor(metrics.uptime_seconds / 86400)} days total
              </span>
            </div>
          </div>

          {/* Status Summary */}
          <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow bg-gradient-to-br from-[#f7f7f7] to-white">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">Overall Status</h3>
                <span className="text-[18px] font-semibold text-[#0a0a0a]">
                  {metrics.cpu_usage < 80 && metrics.memory_usage < 80 && metrics.disk_usage < 80
                    ? "Healthy"
                    : metrics.cpu_usage > 90 || metrics.memory_usage > 90 || metrics.disk_usage > 90
                    ? "Critical"
                    : "Warning"}
                </span>
              </div>
              <div className={`p-2 rounded-lg ${
                metrics.cpu_usage < 80 && metrics.memory_usage < 80 && metrics.disk_usage < 80
                  ? "bg-green-50"
                  : "bg-orange-50"
              }`}>
                <Activity className={`w-5 h-5 ${
                  metrics.cpu_usage < 80 && metrics.memory_usage < 80 && metrics.disk_usage < 80
                    ? "text-green-600"
                    : "text-orange-600"
                }`} />
              </div>
            </div>
            <div className="space-y-2 mt-4">
              <div className="flex justify-between text-[12px]">
                <span className="text-[#8b8b8b]">CPU</span>
                <span className={`font-medium ${
                  metrics.cpu_usage < 70 ? "text-green-600" : metrics.cpu_usage < 90 ? "text-orange-600" : "text-red-600"
                }`}>
                  {metrics.cpu_usage < 70 ? "Normal" : metrics.cpu_usage < 90 ? "High" : "Critical"}
                </span>
              </div>
              <div className="flex justify-between text-[12px]">
                <span className="text-[#8b8b8b]">Memory</span>
                <span className={`font-medium ${
                  metrics.memory_usage < 70 ? "text-green-600" : metrics.memory_usage < 90 ? "text-orange-600" : "text-red-600"
                }`}>
                  {metrics.memory_usage < 70 ? "Normal" : metrics.memory_usage < 90 ? "High" : "Critical"}
                </span>
              </div>
              <div className="flex justify-between text-[12px]">
                <span className="text-[#8b8b8b]">Disk</span>
                <span className={`font-medium ${
                  metrics.disk_usage < 70 ? "text-green-600" : metrics.disk_usage < 90 ? "text-orange-600" : "text-red-600"
                }`}>
                  {metrics.disk_usage < 70 ? "Normal" : metrics.disk_usage < 90 ? "High" : "Critical"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Auto-refresh notice */}
        <div className="mt-6 text-center text-[12px] text-[#8b8b8b]">
          <span>Metrics auto-refresh every 10 seconds</span>
        </div>
      </div>
    </div>
  );
}
