"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ProjectHeader, PageHeader } from "@/components";
import { Loader2, Database } from "lucide-react";
import { getAddonLogo } from "@/lib/addonLogos";

interface Addon {
  name: string;
  type: string;
  version?: string;
  port?: number;
  vm?: string;
}

interface Project {
  name: string;
  addons_config?: Record<string, Record<string, any>>;
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

export default function ProjectAddonsPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const [project, setProject] = useState<Project | null>(null);
  const [addons, setAddons] = useState<Array<{ category: string; name: string; config: any }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch project details
        const response = await fetch(`http://localhost:8401/api/projects/${projectName}`);
        if (!response.ok) {
          throw new Error("Failed to fetch project");
        }
        const projectData = await response.json();
        setProject(projectData);

        // Parse addons from addons_config
        if (projectData.addons_config) {
          const addonsList: Array<{ category: string; name: string; config: any }> = [];
          Object.entries(projectData.addons_config).forEach(([category, instances]: [string, any]) => {
            if (instances && typeof instances === "object") {
              Object.entries(instances).forEach(([name, config]: [string, any]) => {
                addonsList.push({ category, name, config });
              });
            }
          });
          setAddons(addonsList);
        }
      } catch (err) {
        console.error("Failed to fetch data:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    if (projectName) {
      fetchData();
    }
  }, [projectName]);

  if (loading) {
    return (
      <div>
        <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
        <ProjectHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: "Projects", href: "/" },
              { label: projectName || "Loading...", href: `/project/${projectName}` },
            ]}
            menuLabel="Addons"
            title="Add-ons & Services"
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

  if (error) {
    return (
      <div>
        <ProjectHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: "Projects", href: "/" },
              { label: projectName || "Error", href: `/project/${projectName}` },
            ]}
            menuLabel="Addons"
            title="Add-ons & Services"
          />
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">Failed to load addons: {error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <ProjectHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Projects", href: "/" },
            { label: projectName, href: `/project/${projectName}` },
          ]}
          menuLabel="Addons"
          title="Add-ons & Services"
        />

        {addons.length === 0 ? (
          <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
            <div className="w-16 h-16 bg-[#f6f8fa] rounded-full flex items-center justify-center mx-auto mb-4">
              <Database className="w-6 h-6 text-[#8b8b8b]" />
            </div>
            <p className="text-[14px] text-[#0a0a0a] mb-2">No add-ons detected</p>
            <p className="text-[13px] text-[#8b8b8b] max-w-md mx-auto">
              Add-ons provide databases, caching, queues, and other services to your project
            </p>
          </div>
        ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {addons.map((addon) => {
              const addonType = addon.config?.type || addon.name;
              const logo = getAddonLogo(addonType);

              return (
                <div
                  key={`${addon.category}-${addon.name}`}
                  onClick={() =>
                    router.push(`/project/${projectName}/app/${projectName}/addons/${addon.name}`)
                  }
                  className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg cursor-pointer"
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      {logo ? (
                        <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                          {logo}
                        </div>
                      ) : (
                        <div className="w-10 h-10 flex items-center justify-center bg-gray-50 rounded-lg border border-[#e3e8ee] shrink-0">
                          <Database className="w-6 h-6 text-gray-600" />
                        </div>
                      )}
                      <div>
                        <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1 capitalize">
                          {addon.name}
                        </h3>
                      </div>
                    </div>
                  </div>

                  {/* Type */}
                  <div className="flex items-baseline gap-1 mb-3">
                    <span className="text-[21px] text-[#0a0a0a] capitalize">
                      {addonType}
                    </span>
                  </div>

                  {/* Version - Full Width */}
                  {addon.config?.version && (
                    <div className="pt-3 border-t border-[#e3e8ee] mb-3">
                      <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Version</p>
                      <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                        {addon.config.version}
                      </code>
                    </div>
                  )}

                  {/* Port & VM */}
                  {(addon.config?.port || addon.config?.vm) && (
                    <div className={addon.config?.version ? "" : "pt-3 border-t border-[#e3e8ee]"}>
                      {addon.config?.port && (
                        <div className="mb-2">
                          <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Port</p>
                          <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                            {addon.config.port}
                          </code>
                        </div>
                      )}
                      {addon.config?.vm && (
                        <div>
                          <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">VM</p>
                          <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light capitalize">
                            {addon.config.vm}
                          </code>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
