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
  network_rx_bytes_per_sec?: number;
  network_tx_bytes_per_sec?: number;
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

  useEffect(() => {
    const fetchAllMetrics = async () => {
      try {
        // Fetch VM metrics
        const vmResponse = await fetch(
          `http://localhost:8401/api/metrics/${projectName}/${appName}/metrics`
        );
        
        if (vmResponse.ok) {
          const vmData: MetricsResponse = await vmResponse.json();
          setMetrics(vmData.metrics);
          setVmIp(vmData.vm_ip);
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

    if (projectName && appName) {
      fetchAllMetrics();
      
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
            {[...Array(9)].map((_, i) => (
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

        {/* Section 1: VM Metrics (Node Exporter) */}
        <div className="mb-6">
          <h2 className="text-[15px] font-semibold text-[#0a0a0a] mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Virtual Machine Metrics
          </h2>
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
          </div>
        </div>

        {/* Section 2: Container Metrics (cAdvisor) */}
        <div className="mb-6">
          <h2 className="text-[15px] font-semibold text-[#0a0a0a] mb-4 flex items-center gap-2">
            <Container className="w-4 h-4" />
            Container Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Running Containers */}
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
                  {containerCount}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">active</span>
              </div>
              <div className="mt-3">
                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium ${
                  containerCount > 0 ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-700"
                }`}>
                  {containerCount > 0 ? "Healthy" : "No containers"}
                </span>
              </div>
            </div>

            {/* Container CPU */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-50 rounded-lg">
                    <Cpu className="w-5 h-5 text-indigo-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Container CPU</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[32px] font-semibold text-[#0a0a0a]">
                  {totalContainerCpu.toFixed(1)}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">%</span>
              </div>
              <div className="mt-3">
                <span className="text-[11px] text-[#8b8b8b]">
                  Total across {containerCount} container{containerCount !== 1 ? 's' : ''}
                </span>
              </div>
            </div>

            {/* Container Memory */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-pink-50 rounded-lg">
                    <MemoryStick className="w-5 h-5 text-pink-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Container Memory</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[32px] font-semibold text-[#0a0a0a]">
                  {formatBytes(totalContainerMemory)}
                </span>
              </div>
              <div className="mt-3">
                <span className="text-[11px] text-[#8b8b8b]">
                  Total across {containerCount} container{containerCount !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Application Metrics (Prometheus Middleware) */}
        <div className="mb-6">
          <h2 className="text-[15px] font-semibold text-[#0a0a0a] mb-4 flex items-center gap-2">
            <Globe className="w-4 h-4" />
            Application HTTP Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Request Rate */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-50 rounded-lg">
                    <TrendingUp className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Request Rate</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[32px] font-semibold text-[#0a0a0a]">
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
            <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-50 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Error Rate</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[32px] font-semibold text-[#0a0a0a]">
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
            <div className="p-5 border border-[#e3e8ee] rounded-lg hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-50 rounded-lg">
                    <Clock className="w-5 h-5 text-amber-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Avg Latency (P50)</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[32px] font-semibold text-[#0a0a0a]">
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

        {/* Container Details Table */}
        {containerCount > 0 && (
          <div className="mt-6">
            <h2 className="text-[15px] font-semibold text-[#0a0a0a] mb-4">Container Details</h2>
            <div className="border border-[#e3e8ee] rounded-lg overflow-hidden">
              <table className="min-w-full divide-y divide-[#e3e8ee]">
                <thead className="bg-[#f7f7f7]">
                  <tr>
                    <th className="px-4 py-3 text-left text-[13px] font-medium text-[#8b8b8b]">Container</th>
                    <th className="px-4 py-3 text-left text-[13px] font-medium text-[#8b8b8b]">CPU %</th>
                    <th className="px-4 py-3 text-left text-[13px] font-medium text-[#8b8b8b]">Memory</th>
                    <th className="px-4 py-3 text-left text-[13px] font-medium text-[#8b8b8b]">Network RX</th>
                    <th className="px-4 py-3 text-left text-[13px] font-medium text-[#8b8b8b]">Network TX</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-[#e3e8ee]">
                  {containers.map((container, idx) => (
                    <tr key={idx} className="hover:bg-[#f7f7f7] transition-colors">
                      <td className="px-4 py-3 text-[13px] text-[#0a0a0a] font-mono">
                        {container.name}
                      </td>
                      <td className="px-4 py-3 text-[13px] text-[#0a0a0a]">
                        {container.cpu_percent?.toFixed(2) || '0.00'}%
                      </td>
                      <td className="px-4 py-3 text-[13px] text-[#0a0a0a]">
                        {formatBytes(container.memory_bytes || 0)}
                        {container.memory_percent ? ` (${container.memory_percent.toFixed(1)}%)` : ''}
                      </td>
                      <td className="px-4 py-3 text-[13px] text-[#0a0a0a]">
                        {formatBytes(container.network_rx_bytes_per_sec || 0)}/s
                      </td>
                      <td className="px-4 py-3 text-[13px] text-[#0a0a0a]">
                        {formatBytes(container.network_tx_bytes_per_sec || 0)}/s
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
