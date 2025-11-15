"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AppHeader, PageHeader, Table, Button } from "@/components";
import type { Item } from "@/components/Table";
import { 
  Copy,
  CheckCircle2,
  Activity,
  Server,
  HardDrive,
  Cpu,
  MemoryStick,
  Network,
  Lock,
  Database,
  Package
} from "lucide-react";

interface AddonCredential {
  key: string;
  value: string;
}

interface Addon {
  reference: string;
  name: string;
  type: string;
  version: string;
  plan: string;
  status: string;
  host: string;
  port: string;
  container_name: string;
  as_prefix: string;
  access: string;
  credentials: AddonCredential[];
}

interface ContainerMetrics {
  name: string;
  cpu_percent?: number;
  memory_bytes?: number;
  memory_limit_bytes?: number;
  memory_percent?: number;
  network_rx_bytes_per_sec?: number;
  network_tx_bytes_per_sec?: number;
  fs_read_bytes_per_sec?: number;
  fs_write_bytes_per_sec?: number;
}

export default function AddonDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  const addonRef = params?.addonRef as string;
  
  const [addon, setAddon] = useState<Addon | null>(null);
  const [metrics, setMetrics] = useState<ContainerMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>("");

  // Fetch project domain for breadcrumb
  useEffect(() => {
    const fetchProjectInfo = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/projects/${projectName}`);
        if (response.ok) {
          const data = await response.json();
          setAppDomain(data.domain || projectName);
        }
      } catch (err) {
        console.error("Failed to fetch project info:", err);
      }
    };

    if (projectName) {
      fetchProjectInfo();
    }
  }, [projectName]);

  useEffect(() => {
    const fetchAddon = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/resources/${projectName}/${appName}/addon/${addonRef}`);
        
        if (response.ok) {
          const data = await response.json();
          setAddon(data.addon);
        }
      } catch (err) {
        console.error("Failed to fetch addon:", err);
      } finally {
        setLoading(false);
      }
    };
    
    if (projectName && appName && addonRef) {
      fetchAddon();
    }
  }, [projectName, appName, addonRef]);

  // Fetch container metrics
  useEffect(() => {
    if (!addon) return;

    const fetchMetrics = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/metrics/${projectName}/${appName}/containers`);
        
        if (response.ok) {
          const data = await response.json();
          // Find metrics for this addon's container
          const containerMetrics = data.containers?.find((c: ContainerMetrics) => 
            c.name === addon.container_name || 
            c.name.includes(addon.type) ||
            c.name.includes(addon.reference)
          );
          if (containerMetrics) {
            setMetrics(containerMetrics);
          }
        }
      } catch (err) {
        console.error("Failed to fetch metrics:", err);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Update every 5s

    return () => clearInterval(interval);
  }, [addon, projectName, appName]);

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const maskValue = (value: string) => {
    if (value.length <= 4) return "••••";
    return "•".repeat(value.length - 4) + value.slice(-4);
  };

  const getConnectionString = (addon: Addon) => {
    if (addon.type === "postgres") {
      return `postgresql://${addon.host}:${addon.port}/${addon.name}`;
    }
    if (addon.type === "rabbitmq") {
      return `amqp://${addon.host}:${addon.port}`;
    }
    if (addon.type === "redis") {
      return `redis://${addon.host}:${addon.port}`;
    }
    return `${addon.host}:${addon.port}`;
  };

  const getAddonLogo = (type: string) => {
    const logos: Record<string, string> = {
      postgres: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/postgresql/postgresql-original.svg",
      redis: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/redis/redis-original.svg",
      mongodb: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/mongodb/mongodb-original.svg",
      rabbitmq: "https://www.rabbitmq.com/img/rabbitmq-logo.svg",
      elasticsearch: "https://static-www.elastic.co/v3/assets/bltefdd0b53724fa2ce/blt36f2da8d650732a0/5d0823c3d8ff351753cbc99f/logo-elasticsearch-32-color.svg",
      mysql: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/mysql/mysql-original.svg",
      caddy: "https://caddyserver.com/resources/images/caddy-circle-lock.svg",
      nginx: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nginx/nginx-original.svg",
    };
    return logos[type] || null;
  };

  const formatBytes = (bytes: number): string => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
  };

  const connectionString = addon ? getConnectionString(addon) : "";
  const logo = addon ? getAddonLogo(addon.type) : null;

  return (
    <div>
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        {/* Page Header with Breadcrumb */}
        <PageHeader
          breadcrumbs={[
            { label: appDomain || projectName, href: `/project/${projectName}` },
            { label: appName, href: `/project/${projectName}/app/${appName}` },
            { label: "Resources", href: `/project/${projectName}/app/${appName}/resources` },
          ]}
          title="Add-on Details"
        />

        {loading ? (
          <div className="animate-pulse space-y-6 mt-6">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 bg-[#eef2f5] rounded-lg"></div>
              <div className="flex-1">
                <div className="w-48 h-6 bg-[#eef2f5] rounded mb-2"></div>
                <div className="w-64 h-4 bg-[#eef2f5] rounded"></div>
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 h-64 bg-[#eef2f5] rounded-lg"></div>
              <div className="h-64 bg-[#eef2f5] rounded-lg"></div>
            </div>
          </div>
        ) : !addon ? (
          <div className="text-center py-12">
            <p className="text-[14px] text-[#8b8b8b]">Add-on not found</p>
            <Link 
              href={`/project/${projectName}/app/${appName}/resources`}
              className="text-[13px] text-[#0a0a0a] hover:underline mt-2 inline-block"
            >
              ← Back to Resources
            </Link>
          </div>
        ) : (
          <>
            {/* Addon Header */}
            <div className="flex items-start gap-4 mb-6">
              {logo ? (
                <div className="w-14 h-14 flex items-center justify-center flex-shrink-0 bg-white rounded-lg border border-[#e3e8ee]">
                  <img src={logo} alt={addon.type} className="w-9 h-9 object-contain" />
                </div>
              ) : (
                <div className="w-14 h-14 bg-gray-50 rounded-lg flex items-center justify-center flex-shrink-0 border border-[#e3e8ee]">
                  <Package className="w-7 h-7 text-gray-600" />
                </div>
              )}
              
              <div className="flex-1">
                <h2 className="text-[21px] font-semibold text-[#0a0a0a] mb-2">
                  {addon.reference}
                </h2>
                <div className="flex items-center gap-3 text-[12px] tracking-[0.03em] font-light">
                  <span className="text-[#8b8b8b] capitalize">
                    {addon.type}
                  </span>
                  <span className="text-[#e3e8ee]">·</span>
                  <code className="text-[#8b8b8b] font-mono">
                    v{addon.version}
                  </code>
                  <span className="text-[#e3e8ee]">·</span>
                  <div className="flex items-center gap-1.5">
                    <div className={`w-2 h-2 rounded-full ${
                      addon.status === "running" ? "bg-green-500" :
                      addon.status === "exited" ? "bg-red-500" :
                      "bg-yellow-500"
                    }`}></div>
                    <span className={`font-medium ${
                      addon.status === "running" ? "text-green-600" :
                      addon.status === "exited" ? "text-red-600" :
                      "text-yellow-600"
                    }`}>
                      {addon.status}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Connection Details */}
          <div className="lg:col-span-2 space-y-4">
            {/* Connection String */}
            <div className="border border-[#e3e8ee] rounded-lg p-5 transition-all">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Server className="w-4 h-4" />
                Connection URL
              </h3>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-[12px] font-mono bg-[#f6f8fa] px-3 py-2.5 rounded border border-[#e3e8ee] text-[#0a0a0a] break-all leading-relaxed">
                  {connectionString}
                </code>
                <Button
                  onClick={() => copyToClipboard(connectionString, "connection")}
                  variant="secondary"
                  size="sm"
                  icon={copiedField === "connection" ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                >
                  {copiedField === "connection" ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>

            {/* Connection Parameters */}
            <div className="border border-[#e3e8ee] rounded-lg p-5 transition-all">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Database className="w-4 h-4" />
                Connection Parameters
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-1.5">Host</label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-[12px] font-mono bg-[#f6f8fa] px-3 py-2 rounded border border-[#e3e8ee] text-[#0a0a0a]">
                      {addon.host}
                    </code>
                    <Button
                      onClick={() => copyToClipboard(addon.host, "host")}
                      variant="ghost"
                      size="sm"
                      icon={<Copy className="w-3.5 h-3.5" />}
                    />
                  </div>
                </div>

                <div>
                  <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-1.5">Port</label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-[12px] font-mono bg-[#f6f8fa] px-3 py-2 rounded border border-[#e3e8ee] text-[#0a0a0a]">
                      {addon.port}
                    </code>
                    <Button
                      onClick={() => copyToClipboard(addon.port, "port")}
                      variant="ghost"
                      size="sm"
                      icon={<Copy className="w-3.5 h-3.5" />}
                    />
                  </div>
                </div>

                <div className="col-span-2">
                  <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-1.5">Container</label>
                  <code className="block text-[12px] font-mono bg-[#f6f8fa] px-3 py-2 rounded border border-[#e3e8ee] text-[#0a0a0a]">
                    {addon.container_name}
                  </code>
                </div>

                <div>
                  <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-1.5">Env Prefix</label>
                  <code className="block text-[12px] font-mono bg-[#f6f8fa] px-3 py-2 rounded border border-[#e3e8ee] text-[#0a0a0a]">
                    {addon.as_prefix}_*
                  </code>
                </div>
              </div>
            </div>
          </div>

          {/* Real-time Metrics Sidebar */}
          <div className="space-y-4">
            {/* CPU Usage */}
            <div className="border border-[#e3e8ee] rounded-lg p-5 transition-all">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Cpu className="w-4 h-4" />
                CPU Usage
              </h3>
              <div className="flex items-baseline gap-1 mb-2">
                <span className="text-[21px] text-[#0a0a0a]">
                  {metrics?.cpu_percent !== undefined ? metrics.cpu_percent.toFixed(1) : '—'}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">%</span>
              </div>
              <div className="w-full bg-[#f0f0f0] rounded-full h-1.5">
                <div
                  className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(metrics?.cpu_percent || 0, 100)}%` }}
                ></div>
              </div>
            </div>

            {/* Memory Usage */}
            <div className="border border-[#e3e8ee] rounded-lg p-5 transition-all">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <MemoryStick className="w-4 h-4" />
                Memory Usage
              </h3>
              <div className="mb-2">
                <span className="text-[21px] text-[#0a0a0a]">
                  {metrics?.memory_bytes ? formatBytes(metrics.memory_bytes) : '—'}
                </span>
                {metrics?.memory_limit_bytes && (
                  <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                    of {formatBytes(metrics.memory_limit_bytes)}
                  </p>
                )}
              </div>
              {metrics?.memory_percent !== undefined && (
                <div className="w-full bg-[#f0f0f0] rounded-full h-1.5">
                  <div
                    className="bg-purple-600 h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(metrics.memory_percent, 100)}%` }}
                  ></div>
                </div>
              )}
            </div>

            {/* Network I/O */}
            <div className="border border-[#e3e8ee] rounded-lg p-5 transition-all">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Network className="w-4 h-4" />
                Network I/O
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[12px] tracking-[0.03em] font-light">
                  <span className="text-[#8b8b8b]">RX</span>
                  <span className="text-[#0a0a0a] font-medium">
                    {metrics?.network_rx_bytes_per_sec !== undefined 
                      ? formatBytes(metrics.network_rx_bytes_per_sec) + '/s'
                      : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[12px] tracking-[0.03em] font-light">
                  <span className="text-[#8b8b8b]">TX</span>
                  <span className="text-[#0a0a0a] font-medium">
                    {metrics?.network_tx_bytes_per_sec !== undefined
                      ? formatBytes(metrics.network_tx_bytes_per_sec) + '/s'
                      : '—'}
                  </span>
                </div>
              </div>
            </div>

            {/* Disk I/O */}
            <div className="border border-[#e3e8ee] rounded-lg p-5 transition-all">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <HardDrive className="w-4 h-4" />
                Disk I/O
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[12px] tracking-[0.03em] font-light">
                  <span className="text-[#8b8b8b]">Read</span>
                  <span className="text-[#0a0a0a] font-medium">
                    {metrics?.fs_read_bytes_per_sec !== undefined
                      ? formatBytes(metrics.fs_read_bytes_per_sec) + '/s'
                      : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[12px] tracking-[0.03em] font-light">
                  <span className="text-[#8b8b8b]">Write</span>
                  <span className="text-[#0a0a0a] font-medium">
                    {metrics?.fs_write_bytes_per_sec !== undefined
                      ? formatBytes(metrics.fs_write_bytes_per_sec) + '/s'
                      : '—'}
                  </span>
                </div>
              </div>
            </div>

            {/* Status */}
            <div className="border border-[#e3e8ee] rounded-lg p-5 transition-all">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Activity className="w-4 h-4" />
                Status
              </h3>
              <p className="text-[21px] font-semibold text-green-600 mb-1">Running</p>
              <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                Metrics updating every 5s
              </p>
            </div>
            </div>
          </div>

            {/* Environment Variables (Credentials) Section */}
            {addon.credentials && addon.credentials.length > 0 && (
              <div className="mt-6">
                <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                  <Lock className="w-4 h-4" />
                  Environment Variables ({addon.credentials.length})
                </h3>
                <p className="text-[12px] text-[#8b8b8b] tracking-[0.03em] font-light mb-4">
                  These environment variables are automatically injected with the{" "}
                  <code className="text-[11px] font-mono bg-[#f6f8fa] px-2 py-0.5 rounded border border-[#e3e8ee]">
                    {addon.as_prefix}_
                  </code>{" "}
                  prefix.
                </p>
                
                <Table
                  columns={[
                    {
                      title: "Key",
                      width: "300px",
                      render: (item: Item) => (
                        <div className="flex items-center gap-3">
                          <Lock className="w-4 h-4 text-[#8b8b8b]" />
                          <code className="text-[13px] font-mono text-[#0a0a0a]">
                            {item.data.key}
                          </code>
                        </div>
                      ),
                    },
                    {
                      title: "Value",
                      render: (item: Item) => (
                        <code className="text-[13px] font-mono text-[#8b8b8b]">
                          {maskValue(item.data.value)}
                        </code>
                      ),
                    },
                    {
                      title: "",
                      width: "100px",
                      render: (item: Item) => (
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              copyToClipboard(item.data.value, item.data.key);
                            }}
                            variant="secondary"
                            size="sm"
                            icon={copiedField === item.data.key ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                          >
                            {copiedField === item.data.key ? "Copied" : "Copy"}
                          </Button>
                        </div>
                      ),
                    },
                  ]}
                  data={addon.credentials.map((cred) => ({
                    id: cred.key,
                    type: "credential",
                    data: cred,
                  }))}
                  getRowKey={(item) => `credential-${item.id}`}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
