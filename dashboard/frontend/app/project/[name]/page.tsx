"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ProjectHeader, PageHeader, RefreshButton } from "@/components";
import { Loader2, Settings, Server, Database, Network, Key, Globe, Github } from "lucide-react";

interface Project {
  id: number;
  name: string;
  description?: string;
  domain?: string;
  ssl_email?: string;
  github_org?: string;
  gcp_project?: string;
  gcp_region?: string;
  gcp_zone?: string;
  ssh_key_path?: string;
  ssh_public_key_path?: string;
  ssh_user?: string;
  docker_registry?: string;
  docker_organization?: string;
  vpc_subnet?: string;
  docker_subnet?: string;
  vms?: Record<string, any>;
  apps_config?: Record<string, any>;
  addons_config?: Record<string, any>;
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

export default function ProjectConfigurationPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProject = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`http://localhost:8401/api/projects/${projectName}`);
      if (!response.ok) {
        throw new Error("Failed to fetch project");
      }
      const data = await response.json();
      setProject(data);
    } catch (err) {
      console.error("Failed to fetch project:", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [projectName]);

  useEffect(() => {
    // Redirect orchestrator to infrastructure route
    if (projectName === "orchestrator") {
      router.replace("/infrastructure/orchestrator");
      return;
    }

    if (projectName) {
      fetchProject();
    }
  }, [projectName, router, fetchProject]);

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
            menuLabel="Configuration"
            title="Project Configuration"
          />

          {/* Skeleton */}
          <div className="space-y-6 mt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(5)].map((_, idx) => (
                <div key={idx} className="h-[250px] rounded-lg skeleton-shimmer"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div>
        <ProjectHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: "Projects", href: "/" },
              { label: projectName || "Error", href: `/project/${projectName}` },
            ]}
            menuLabel="Configuration"
            title="Project Configuration"
          />
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">Failed to load project: {error}</p>
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
            { label: project.name, href: `/project/${projectName}` },
          ]}
          menuLabel="Configuration"
          title="Project Configuration"
          rightAction={
            <RefreshButton 
              projectName={projectName} 
              onRefreshComplete={fetchProject}
            />
          }
        />

        <div className="space-y-6 mt-6">
          {/* Project Configuration Section */}
          <div>
            <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
              <Settings className="w-4 h-4" />
              Project Configuration
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Project Information */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                  <Settings className="w-6 h-6 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">Project Information</h3>
                </div>
              </div>
            </div>

            {/* Project Name */}
            <div className="flex items-baseline gap-1 mb-3">
              <span className="text-[21px] text-[#0a0a0a] capitalize">
                {project.name}
              </span>
            </div>

            {/* Other fields */}
            <div className="pt-3 border-t border-[#e3e8ee]">
              <div className="mb-2">
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Domain</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.domain || "-"}
                </code>
              </div>
              <div className="mb-2">
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">SSL Email</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.ssl_email || "-"}
                </code>
              </div>
              <div>
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">GitHub Organization</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.github_org || "-"}
                </code>
              </div>
            </div>
          </div>

          {/* GCP Configuration */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            {/* Header */}
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

            {/* GCP Project */}
            <div className="flex items-baseline gap-1 mb-3">
              <span className="text-[21px] text-[#0a0a0a]">
                {project.gcp_project || "-"}
              </span>
            </div>

            {/* Other fields */}
            <div className="pt-3 border-t border-[#e3e8ee]">
              <div className="mb-2">
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Region</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.gcp_region || "-"}
                </code>
              </div>
              <div>
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Zone</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.gcp_zone || "-"}
                </code>
              </div>
            </div>
          </div>

          {/* Docker Configuration */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                  <Database className="w-6 h-6 text-teal-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">Docker Configuration</h3>
                </div>
              </div>
            </div>

            {/* Docker Registry */}
            <div className="flex items-baseline gap-1 mb-3">
              <span className="text-[21px] text-[#0a0a0a]">
                {project.docker_registry || "-"}
              </span>
            </div>

            {/* Other fields */}
            <div className="pt-3 border-t border-[#e3e8ee]">
              <div>
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Organization</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.docker_organization || "-"}
                </code>
              </div>
            </div>
          </div>

          {/* Network Configuration */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                  <Network className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">Network Configuration</h3>
                </div>
              </div>
            </div>

            {/* VPC Subnet */}
            <div className="flex items-baseline gap-1 mb-3">
              <span className="text-[21px] text-[#0a0a0a]">
                {project.vpc_subnet || "-"}
              </span>
            </div>

            {/* Other fields */}
            <div className="pt-3 border-t border-[#e3e8ee]">
              <div>
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Docker Subnet</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.docker_subnet || "-"}
                </code>
              </div>
            </div>
          </div>

          {/* SSH Configuration */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            {/* Header */}
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

            {/* SSH User */}
            <div className="flex items-baseline gap-1 mb-3">
              <span className="text-[21px] text-[#0a0a0a]">
                {project.ssh_user || "-"}
              </span>
            </div>

            {/* Other fields */}
            <div className="pt-3 border-t border-[#e3e8ee]">
              <div className="mb-2">
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Key Path</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.ssh_key_path || "-"}
                </code>
              </div>
              <div>
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Public Key Path</p>
                <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                  {project.ssh_public_key_path || "-"}
                </code>
              </div>
            </div>
          </div>

            </div>
          </div>

          {/* Virtual Machines Section */}
          {project.vms && Object.keys(project.vms).length > 0 && (
            <div>
              <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
                <Server className="w-4 h-4" />
                Virtual Machines
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(project.vms).map(([vmName, vmConfig]: [string, any]) => (
            <div key={vmName} className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] shrink-0">
                    <Server className="w-6 h-6 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1 capitalize">Virtual Machine ({vmName})</h3>
                  </div>
                </div>
              </div>

              {/* Count */}
              <div className="flex items-baseline gap-1 mb-3">
                <span className="text-[21px] text-[#0a0a0a]">
                  {vmConfig.count || 0}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">
                  {vmConfig.count === 1 ? 'instance' : 'instances'}
                </span>
              </div>

              {/* Other fields */}
              <div className="pt-3 border-t border-[#e3e8ee]">
                <div className="mb-2">
                  <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Machine Type</p>
                  <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                    {vmConfig.machine_type || "N/A"}
                  </code>
                </div>
                <div>
                  <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Disk Size</p>
                  <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                    {vmConfig.disk_size || "N/A"}
                  </code>
                </div>
              </div>
            </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
