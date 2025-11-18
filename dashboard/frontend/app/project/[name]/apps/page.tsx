"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ProjectHeader, PageHeader } from "@/components";
import { Loader2, Package, Github } from "lucide-react";

interface App {
  id: number;
  name: string;
  repo: string;
  owner: string;
}

interface Project {
  name: string;
  apps_config?: Record<string, any>;
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

export default function ProjectAppsPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const [project, setProject] = useState<Project | null>(null);
  const [apps, setApps] = useState<App[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch project details
        const projectResponse = await fetch(`http://localhost:8401/api/projects/${projectName}`);
        if (!projectResponse.ok) {
          throw new Error("Failed to fetch project");
        }
        const projectData = await projectResponse.json();
        setProject(projectData);

        // Fetch apps
        const appsResponse = await fetch(`http://localhost:8401/api/projects/${projectName}/apps`);
        if (!appsResponse.ok) {
          throw new Error("Failed to fetch apps");
        }
        const appsData = await appsResponse.json();
        setApps(appsData);
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
            menuLabel="Apps"
            title="Applications"
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
            menuLabel="Apps"
            title="Applications"
          />
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">Failed to load apps: {error}</p>
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
          menuLabel="Apps"
          title="Applications"
        />

        {apps.length === 0 ? (
          <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
            <div className="w-16 h-16 bg-[#f6f8fa] rounded-full flex items-center justify-center mx-auto mb-4">
              <Package className="w-6 h-6 text-[#8b8b8b]" />
            </div>
            <p className="text-[14px] text-[#0a0a0a] mb-2">No applications found</p>
            <p className="text-[13px] text-[#8b8b8b]">
              Add applications to your project to get started
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {apps.map((app) => {
              const appConfig = project?.apps_config?.[app.name];
              return (
                <div
                  key={app.id}
                  onClick={() => router.push(`/project/${projectName}/app/${app.name}`)}
                  className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg cursor-pointer"
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-blue-50 rounded-lg">
                        <Package className="w-5 h-5 text-blue-600" />
                      </div>
                      <div>
                        <h3 className="text-[13px] text-[#8b8b8b] font-light">{app.name}</h3>
                      </div>
                    </div>
                    {appConfig?.port && (
                      <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                        :{appConfig.port}
                      </span>
                    )}
                  </div>

                  {/* Replicas */}
                  {appConfig?.replicas && (
                    <div className="flex items-baseline gap-1 mb-3">
                      <span className="text-[21px] text-[#0a0a0a]">
                        {appConfig.replicas}
                      </span>
                      <span className="text-[16px] text-[#8b8b8b]">
                        {appConfig.replicas === 1 ? 'replica' : 'replicas'}
                      </span>
                    </div>
                  )}

                  {/* Repository - Full Width */}
                  <div className="pt-3 border-t border-[#e3e8ee] mb-3">
                    <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Repository</p>
                    <div className="flex items-center gap-2">
                      <Github className="w-3.5 h-3.5 text-[#8b8b8b]" />
                      <code className="text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                        {app.owner}/{app.repo}
                      </code>
                    </div>
                  </div>

                  {/* VM - Full Width */}
                  {appConfig?.vm && (
                    <div>
                      <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">VM</p>
                      <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light capitalize">
                        {appConfig.vm}
                      </code>
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

