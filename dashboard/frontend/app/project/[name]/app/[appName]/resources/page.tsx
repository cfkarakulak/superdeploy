"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppHeader, PageHeader, Button } from "@/components";
import { getAddonLogo, getStatusDot } from "@/lib/addonLogos";
import { 
  Cpu, 
  Server, 
  Package,
  Database
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

interface Process {
  name: string;
  command: string;
  replicas: number;
  port?: number;
  run_on?: string;
}

interface Addon {
  reference: string;
  name: string;
  type: string;
  category: string;
  version: string;
  plan: string;
  as_prefix?: string;
  as?: string;
  access: string;
  status: string;
  host?: string;
  port?: string;
  container_name?: string;
  source?: string;
}

interface AppInfo {
  name: string;
  type: string;
  port: number;
  vm: string;
  vm_name?: string;
  vm_ip?: string;
  replicas: number;
  deployment: {
    version?: string;
    git_sha?: string;
    deployed_at?: string;
    deployed_by?: string;
    branch?: string;
  };
  processes: Array<{
    container: string;
    status: string;
    id: string;
  }>;
  resources: Record<string, { cpu: string; memory: string }>;
}

export default function ResourcesPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  
  const [processes, setProcesses] = useState<Process[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>("");

  useEffect(() => {
    const fetchResources = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/resources/${projectName}/${appName}`);
        
        if (response.ok) {
          const data = await response.json();
          setProcesses(data.formation || []);
          setAddons(data.addons || []);
          setAppInfo(data.app_info || null);
        } else {
          setError(`Failed to fetch resources: ${response.statusText}`);
        }
      } catch (err) {
        console.error("Failed to fetch resources:", err);
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
      fetchResources();
      fetchAppInfo();
    }
  }, [projectName, appName]);

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
      background: linear-gradient(
        to right,
        #eef2f5 0%,
        #e6eaef 20%,
        #eef2f5 40%,
        #eef2f5 100%
      );
      background-size: 1000px 100%;
    }
  `;

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
          menuLabel="Resources"
          title="Resources & Add-ons"
        />

        {loading ? (
          <div className="space-y-6 mt-6">
            {/* Process Formation Skeleton */}
            <div>
              <div className="flex items-center gap-2 mb-[8px]">
                <div className="w-4 h-4 rounded skeleton-shimmer"></div>
                <div className="w-44 h-3 rounded skeleton-shimmer"></div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(1)].map((_, cardIdx) => (
                  <div key={cardIdx} className="h-[220px] rounded-lg skeleton-shimmer"></div>
                ))}
              </div>
            </div>

            {/* Add-ons Skeleton */}
            <div>
              <div className="flex items-center gap-2 mb-[8px]">
                <div className="w-4 h-4 rounded skeleton-shimmer"></div>
                <div className="w-44 h-3 rounded skeleton-shimmer"></div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(3)].map((_, cardIdx) => (
                  <div key={cardIdx} className="h-[250px] rounded-lg skeleton-shimmer"></div>
                ))}
              </div>
            </div>
          </div>
        ) : error ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">Failed to load resources: {error}</p>
          </div>
        ) : (
          <div className="space-y-6 mt-6">
            {/* Process Formation Section */}
            <div>
              <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Cpu className="w-4 h-4" />
                Process Formation ({processes.length})
              </h2>

              {processes.length === 0 ? (
                <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
                  <div className="w-16 h-16 bg-[#f6f8fa] rounded-full flex items-center justify-center mx-auto mb-4">
                    <Server className="w-6 h-6 text-[#8b8b8b]" />
                  </div>
                  <p className="text-[14px] text-[#0a0a0a] mb-2">No processes configured</p>
                  <p className="text-[13px] text-[#8b8b8b] mb-4">Deploy your application to see process formation</p>
                  <Button variant="primary" size="md">
                    Deploy Application
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {processes.map((process) => {
                    return (
                      <div
                        key={process.name}
                        className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg"
                      >
                        {/* Header */}
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-50 rounded-lg">
                              <Cpu className="w-5 h-5 text-blue-600" />
                            </div>
                            <div>
                              <h3 className="text-[13px] text-[#8b8b8b] font-light">{process.name}</h3>
                            </div>
                          </div>
                          {process.port && (
                            <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                              :{process.port}
                            </span>
                          )}
                        </div>

                        {/* Replicas */}
                        <div className="flex items-baseline gap-1">
                          <span className="text-[21px] text-[#0a0a0a]">
                            {process.replicas}
                          </span>
                          <span className="text-[16px] text-[#8b8b8b]">
                            {process.replicas === 1 ? 'replica' : 'replicas'}
                          </span>
                        </div>

                        {/* Command - Full Width */}
                        <div className="pt-3 border-t border-[#e3e8ee]">
                          <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Command</p>
                          <code className="block text-[11px] text-[#0a0a0a] font-mono font-light break-all leading-relaxed">
                            {process.command}
                          </code>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Add-ons Section */}
            <div>
              <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Database className="w-4 h-4" />
                Attached Add-ons ({addons.length})
              </h2>

              {addons.length === 0 ? (
                <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
                  <div className="w-16 h-16 bg-[#f6f8fa] rounded-full flex items-center justify-center mx-auto mb-4">
                    <Package className="w-6 h-6 text-[#8b8b8b]" />
                  </div>
                  <p className="text-[14px] text-[#0a0a0a] mb-2">No add-ons detected</p>
                  <p className="text-[13px] text-[#8b8b8b] mb-4 max-w-md mx-auto">
                    Add-ons may need to be attached to this app. Install databases, caching, queues, and other services.
                  </p>
                  <Button 
                    variant="primary"
                    size="md"
                    onClick={() => router.push(`/project/${projectName}/addons`)}
                  >
                    Browse Add-ons
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {addons.map((addon) => {
                    const logo = getAddonLogo(addon.type);
                    const statusDot = getStatusDot(addon.status);
                    
                    return (
                      <div
                        key={addon.reference}
                        className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg cursor-pointer"
                        onClick={() => router.push(`/project/${projectName}/app/${appName}/addons/${addon.reference}`)}
                      >
                        {/* Header */}
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center gap-3">
                            {logo ? (
                              <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] flex-shrink-0">
                                {logo}
                              </div>
                            ) : (
                              <div className="w-10 h-10 flex items-center justify-center bg-gray-50 rounded-lg border border-[#e3e8ee] flex-shrink-0">
                                <Package className="w-6 h-6 text-gray-600" />
                              </div>
                            )}
                            <div>
                              <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">{addon.reference}</h3>
                              <div className="flex items-center gap-1.5">
                                <div className={`w-2 h-2 rounded-full ${statusDot} flex-shrink-0`}></div>
                                <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                                  {addon.status.replace(/\s*\([^)]*\)/g, '')}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Type */}
                        <div className="flex items-baseline gap-1 mb-3">
                          <span className="text-[21px] text-[#0a0a0a] capitalize">
                            {addon.type}
                          </span>
                        </div>

                        {/* Version - Full Width */}
                        <div className="pt-3 border-t border-[#e3e8ee] mb-3">
                          <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Version</p>
                          <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                            {addon.version}
                          </code>
                        </div>

                        {/* Env Prefix - Full Width */}
                        <div>
                          <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Environment Prefix</p>
                          <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                            {(addon.as_prefix || addon.as || addon.type.toUpperCase())}_*
                          </code>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
