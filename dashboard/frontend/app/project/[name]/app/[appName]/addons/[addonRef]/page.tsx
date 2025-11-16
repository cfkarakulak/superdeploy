"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppHeader, PageHeader, Table, Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components";
import { getAddonLogo } from "@/lib/addonLogos";
import type { Item } from "@/components/Table";
import { 
  Copy,
  CheckCircle2,
  HardDrive,
  Cpu,
  MemoryStick,
  Network,
  Lock,
  Package
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
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  const addonRef = params?.addonRef as string;
  
  const [addon, setAddon] = useState<Addon | null>(null);
  const [metrics, setMetrics] = useState<ContainerMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>(projectName);
  const [viewModalOpen, setViewModalOpen] = useState(false);
  const [viewingCredential, setViewingCredential] = useState<AddonCredential | null>(null);

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
        // Include addons parameter to get all project containers (app + addons)
        const response = await fetch(`http://localhost:8401/api/metrics/${projectName}/${appName}/containers?include_addons=true`);
        
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

  const openViewModal = (credential: AddonCredential) => {
    setViewingCredential(credential);
    setViewModalOpen(true);
  };

  const maskValue = (value: string) => {
    if (value.length <= 4) return "••••";
    // Max 20 characters
    const masked = "•".repeat(Math.min(value.length - 4, 16)) + value.slice(-4);
    return masked.length > 20 ? masked.slice(0, 20) : masked;
  };

  const formatBytes = (bytes: number): string => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
  };

  const logo = addon ? getAddonLogo(addon.type) : null;

  return (
    <div>
      <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        {/* Page Header with Breadcrumb */}
        <PageHeader
          breadcrumbs={[
            { label: appDomain || projectName, href: `/project/${projectName}` },
            { label: appName, href: `/project/${projectName}/app/${appName}` },
            { label: "Resources", href: `/project/${projectName}/app/${appName}/resources` },
          ]}
          menuLabel={addon?.reference || addonRef}
          title="Add-on Details"
        />

        {loading ? (
          <div className="space-y-6 mt-6">
            {/* Addon Header Skeleton */}
            <div className="flex items-start gap-4 mb-6">
              <div className="w-14 h-14 skeleton-shimmer rounded-lg shrink-0"></div>
              <div className="flex-1">
                <div className="w-48 h-[18px] skeleton-shimmer rounded mb-2"></div>
                <div className="w-64 h-[12px] skeleton-shimmer rounded"></div>
              </div>
            </div>
            
            {/* Info Boxes Skeleton - 4 boxes horizontal */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-[88px] skeleton-shimmer rounded-lg"></div>
              ))}
            </div>
            
            {/* Environment Variables Section Skeleton */}
            <div>
              <div className="w-48 h-[16px] skeleton-shimmer rounded mb-3"></div>
              <div className="h-[320px] skeleton-shimmer rounded-lg"></div>
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
                <div className="w-14 h-14 p-3 flex items-center justify-center shrink-0 bg-white rounded-lg border border-[#e3e8ee]">
                  {logo}
                </div>
              ) : (
                <div className="w-14 h-14 bg-gray-50 rounded-lg flex items-center justify-center shrink-0 border border-[#e3e8ee]">
                  <Package className="w-7 h-7 text-gray-600" />
                </div>
              )}
              
              <div className="flex-1">
                <h2 className="text-[18px] text-[#0a0a0a] mb-1">
                  {addon.reference}
                </h2>
                <div className="flex items-center gap-1 text-[12px] tracking-[0.03em] font-light">
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
                      addon.status.includes("Up") || addon.status === "running" ? "bg-green-500" :
                      addon.status === "exited" ? "bg-red-500" :
                      "bg-yellow-500"
                    }`}></div>
                    <span className={`font-normal text-[11px] tracking-[0.03em] ${
                      addon.status.includes("Up") || addon.status === "running" ? "text-green-600" :
                      addon.status === "exited" ? "text-red-600" :
                      "text-yellow-600"
                    }`}>
                      {addon.status}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Info Boxes - Horizontal Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
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
                  MEM Usage
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
            </div>

            {/* Environment Variables (Credentials) Section */}
            <div className="mt-6">
              <h3 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-4 font-light">
                <Lock className="w-4 h-4" />
                Environment Variables {addon.credentials && addon.credentials.length > 0 && `(${addon.credentials.length})`}
              </h3>
              
              {addon.credentials && addon.credentials.length > 0 ? (
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
                  ]}
                  data={addon.credentials.map((cred) => ({
                    id: cred.key,
                    type: "credential",
                    data: cred,
                  }))}
                  getRowKey={(item) => `credential-${item.id}`}
                  onRowClick={(item) => openViewModal(item.data)}
                />
              ) : (
                <div className="border border-[#e3e8ee] rounded-lg p-8 text-center">
                  <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                    No environment variables available for this add-on
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* View Credential Modal */}
      <Dialog open={viewModalOpen} onOpenChange={setViewModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>View Environment Variable</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-2">Key</label>
              <code className="block text-[13px] font-mono bg-[#f6f8fa] px-3 py-2.5 rounded border border-[#e3e8ee] text-[#0a0a0a]">
                {viewingCredential?.key}
              </code>
            </div>
            
            <div>
              <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-2">Value</label>
              <code className="block text-[13px] font-mono bg-[#f6f8fa] px-3 py-2.5 rounded border border-[#e3e8ee] text-[#0a0a0a] break-all">
                {viewingCredential?.value}
              </code>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => setViewModalOpen(false)}
            >
              Close
            </Button>
            <Button
              onClick={() => {
                if (viewingCredential) {
                  copyToClipboard(viewingCredential.value, viewingCredential.key);
                }
              }}
              icon={copiedField === viewingCredential?.key ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            >
              {copiedField === viewingCredential?.key ? "Copied" : "Copy Value"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

