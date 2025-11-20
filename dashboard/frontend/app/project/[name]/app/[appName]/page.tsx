"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";
import { 
  Cpu, 
  MemoryStick, 
  HardDrive, 
  Container, 
  Activity, 
  Zap, 
  TrendingUp, 
  AlertCircle,
  Globe,
  Clock
} from "lucide-react";

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

interface AppMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  uptime_seconds: number;
}

interface MetricsResponse {
  app: string;
  project: string;
  vm_ip: string;
  metrics: AppMetrics;
}

interface ContainerMetrics {
  name: string;
  cpu_percent?: number;
  memory_bytes?: number;
  memory_percent?: number;
  memory_limit_bytes?: number;
  fs_read_bytes_per_sec?: number;
  fs_write_bytes_per_sec?: number;
}

interface ApplicationMetrics {
  request_rate_per_sec: number;
  error_rate_per_sec: number;
  error_percentage: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
  active_requests: number;
}

export default function AppOverviewPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [metrics, setMetrics] = useState<AppMetrics | null>(null);
  const [vmIp, setVmIp] = useState<string>("");
  const [containers, setContainers] = useState<ContainerMetrics[]>([]);
  const [appMetrics, setAppMetrics] = useState<ApplicationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>(""); // Will be loaded from API

  useEffect(() => {
    const fetchAllMetrics = async () => {
      try {
        // Fetch VM metrics (all VMs in project)
        const vmResponse = await fetch(
          `http://localhost:8401/api/metrics/${projectName}/vms`
        );
        
        if (vmResponse.ok) {
          const vmData = await vmResponse.json();
          // Find the app VM (or first VM if no role specified)
          const appVm = vmData.vms?.find((vm: any) => vm.role === 'app') || vmData.vms?.[0];
          if (appVm) {
            setMetrics({
              cpu_usage: appVm.cpu_usage || 0,
              memory_usage: appVm.memory_usage || 0,
              disk_usage: appVm.disk_usage || 0,
              container_count: 0,
              uptime_seconds: appVm.uptime_seconds || 0,
            });
            setVmIp(appVm.ip);
          }
        }

        // Fetch container metrics (cAdvisor)
        const containerResponse = await fetch(
          `http://localhost:8401/api/metrics/${projectName}/${appName}/containers`
        );
        
        if (containerResponse.ok) {
          const containerData = await containerResponse.json();
          setContainers(containerData.containers || []);
        }

        // Fetch application metrics (PrometheusMiddleware)
        const appResponse = await fetch(
          `http://localhost:8401/api/metrics/${projectName}/${appName}/application`
        );
        
        if (appResponse.ok) {
          const appData = await appResponse.json();
          setAppMetrics(appData.metrics);
        }
      } catch (err) {
        console.error("Failed to fetch metrics:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    const fetchAppInfo = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/projects/${projectName}`);
        if (response.ok) {
          const data = await response.json();
          setAppDomain(data.domain || projectName);
        }
      } catch (err) {
        console.error("Failed to fetch project info:", err);
        setAppDomain(projectName);
      }
    };

    if (projectName && appName) {
      fetchAllMetrics();
      fetchAppInfo();
      
      // Refresh metrics every 10 seconds
      const interval = setInterval(fetchAllMetrics, 10000);
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

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
  };

  // Calculate aggregated container metrics
  const totalContainerCpu = containers.reduce((sum, c) => sum + (c.cpu_percent || 0), 0);
  const totalContainerMemory = containers.reduce((sum, c) => sum + (c.memory_bytes || 0), 0);
  const containerCount = containers.length;

  if (loading) {
    return (
      <div>
        <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: appDomain || "Loading...", href: `/project/${projectName}` },
              { label: appName, href: `/project/${projectName}/app/${appName}` },
            ]}
            menuLabel="Overview"
            title="Application Metrics"
          />
          
          {/* Section 1: VM Metrics Skeleton */}
          <div className="mb-6">
            {/* Section title skeleton */}
            <div className="flex items-center gap-2 mb-[6px]">
              <div className="w-4 h-4 rounded skeleton-shimmer"></div>
              <div className="w-48 h-3 rounded skeleton-shimmer"></div>
            </div>
            
            {/* VM Metrics cards skeleton (shorter height) */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(3)].map((_, cardIdx) => (
                <div key={cardIdx} className="h-[140px] rounded-lg skeleton-shimmer"></div>
              ))}
            </div>
          </div>

          {/* Section 2: HTTP Metrics Skeleton */}
          <div className="mb-6">
            {/* Section title skeleton */}
            <div className="flex items-center gap-2 mb-[6px]">
              <div className="w-4 h-4 rounded skeleton-shimmer"></div>
              <div className="w-48 h-3 rounded skeleton-shimmer"></div>
            </div>
            
            {/* HTTP Metrics cards skeleton (shorter height) */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(3)].map((_, cardIdx) => (
                <div key={cardIdx} className="h-[140px] rounded-lg skeleton-shimmer"></div>
              ))}
            </div>
          </div>

          {/* Section 3: Running Containers Skeleton */}
          <div className="mb-6">
            {/* Section title skeleton */}
            <div className="flex items-center gap-2 mb-[6px]">
              <div className="w-4 h-4 rounded skeleton-shimmer"></div>
              <div className="w-48 h-3 rounded skeleton-shimmer"></div>
            </div>
            
            {/* Container cards skeleton (taller height) */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(3)].map((_, cardIdx) => (
                <div key={cardIdx} className="h-[260px] rounded-lg skeleton-shimmer"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div>
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: appDomain || "Loading...", href: `/project/${projectName}` },
              { label: appName, href: `/project/${projectName}/app/${appName}` },
            ]}
            menuLabel="Overview"
            title="Application Metrics"
          />
          
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">Failed to load metrics: {error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: appDomain || "Loading...", href: `/project/${projectName}` },
            { label: appName, href: `/project/${projectName}/app/${appName}` },
          ]}
          menuLabel="Overview"
          title="Application Metrics"
        />

        {/* Section 1: VM Metrics (Node Exporter) */}
        <div className="mb-6">
          <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.02em] mb-[6px] font-light">
            <Activity className="w-4 h-4" />
            Virtual Machine Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* CPU Usage */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-50 rounded-lg">
                    <Cpu className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">CPU Usage</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
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
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-50 rounded-lg">
                    <MemoryStick className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <h3 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">MEM Usage</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
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
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-orange-50 rounded-lg">
                    <HardDrive className="w-5 h-5 text-orange-600" />
                  </div>
                  <div>
                    <h3 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">Disk Usage</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
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
          </div>
        </div>

        {/* Section 2: Application Metrics (Prometheus Middleware) */}
        <div className="mb-6">
          <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.02em] mb-[6px] font-light">
            <Globe className="w-4 h-4" />
            Application HTTP Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Request Rate */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-50 rounded-lg">
                    <TrendingUp className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <h3 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">Request Rate</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
                  {appMetrics?.request_rate_per_sec.toFixed(1) || '0.0'}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">req/s</span>
              </div>
              <div className="mt-3">
                <span className="text-[11px] text-[#8b8b8b]">
                  {appMetrics ? `${(appMetrics.request_rate_per_sec * 60).toFixed(0)} requests/min` : 'No data'}
                </span>
              </div>
            </div>

            {/* Error Rate */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-50 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600" />
                  </div>
                  <div>
                    <h3 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">Error Rate</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
                  {appMetrics?.error_percentage.toFixed(1) || '0.0'}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">%</span>
              </div>
              <div className="mt-3">
                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium ${
                  !appMetrics || appMetrics.error_percentage < 1 
                    ? "bg-green-50 text-green-700" 
                    : appMetrics.error_percentage < 5
                    ? "bg-yellow-50 text-yellow-700"
                    : "bg-red-50 text-red-700"
                }`}>
                  {!appMetrics || appMetrics.error_percentage < 1 
                    ? "Healthy" 
                    : appMetrics.error_percentage < 5
                    ? "Warning"
                    : "Critical"}
                </span>
              </div>
            </div>

            {/* Average Latency */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-50 rounded-lg">
                    <Clock className="w-5 h-5 text-amber-600" />
                  </div>
                  <div>
                    <h3 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">Avg Latency (P50)</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
                  {appMetrics?.latency_p50_ms.toFixed(0) || '0'}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">ms</span>
              </div>
              <div className="mt-3">
                <span className="text-[11px] text-[#8b8b8b]">
                  P95: {appMetrics?.latency_p95_ms.toFixed(0) || '0'}ms • P99: {appMetrics?.latency_p99_ms.toFixed(0) || '0'}ms
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Running Containers */}
        {containerCount > 0 && (
          <div className="mb-6">
            <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.02em] mb-[6px] font-light">
              <Container className="w-4 h-4" />
              Running Containers ({containerCount})
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {containers.map((container, idx) => (
                <div key={idx} className="p-5 border border-[#e3e8ee] rounded-lg">
                  {/* Container Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-teal-50 rounded-lg">
                        <Container className="w-5 h-5 text-teal-600" />
                      </div>
                      <div>
                        <h3 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">{container.name}</h3>
                      </div>
                    </div>
                  </div>

                  {/* CPU Usage */}
                  <div className="mb-4">
                    <div className="flex items-baseline gap-2 mb-1">
                      <span className="text-[22px] text-[#0a0a0a]">
                        {container.cpu_percent?.toFixed(1) || '0.0'}
                      </span>
                      <span className="text-[14px] text-[#8b8b8b]">% CPU</span>
                    </div>
                    <div className="w-full bg-[#f0f0f0] rounded-full h-1.5">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(container.cpu_percent || 0, 100)}%` }}
                      ></div>
                    </div>
                  </div>

                  {/* Memory Usage */}
                  <div className="mb-4">
                    <div className="flex items-baseline gap-2 mb-1">
                      <span className="text-[22px] text-[#0a0a0a]">
                        {formatBytes(container.memory_bytes || 0)}
                      </span>
                      {container.memory_limit_bytes && container.memory_limit_bytes > 0 && (
                        <span className="text-[13px] text-[#8b8b8b]">
                          / {formatBytes(container.memory_limit_bytes)}
                        </span>
                      )}
                    </div>
                    {container.memory_percent !== undefined && (
                      <div className="w-full bg-[#f0f0f0] rounded-full h-1.5">
                        <div
                          className="bg-purple-600 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(container.memory_percent, 100)}%` }}
                        ></div>
                      </div>
                    )}
                  </div>

                  {/* Disk I/O */}
                  <div className="pt-3 border-t border-[#e3e8ee]">
                    <div className="flex items-center justify-between text-[12px] mb-1">
                      <span className="text-[#8b8b8b]">Disk Read</span>
                      <span className="text-[#0a0a0a]">
                        {formatBytes(container.fs_read_bytes_per_sec || 0)}/s
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[12px]">
                      <span className="text-[#8b8b8b]">Disk Write</span>
                      <span className="text-[#0a0a0a]">
                        {formatBytes(container.fs_write_bytes_per_sec || 0)}/s
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
