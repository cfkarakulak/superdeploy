"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ProjectHeader, PageHeader } from "@/components";
import { Rocket, Package, Clock, GitBranch } from "lucide-react";

interface DeploymentStats {
  total_apps: number;
  deployed_apps: number;
  last_deployment: string | null;
}

interface Deployment {
  app_name: string;
  version: string;
  git_sha: string;
  branch: string;
  deployed_at: string | null;
  deployed_by: string;
  status: string;
  duration: number | null;
}

export default function ProjectDeploymentPage() {
  const params = useParams();
  const projectName = params?.name as string;
  
  const [stats, setStats] = useState<DeploymentStats | null>(null);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDeploymentHistory = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/projects/${projectName}/deployment-history`);
        if (response.ok) {
          const data = await response.json();
          setStats(data.stats);
          setDeployments(data.deployments || []);
        }
      } catch (err) {
        console.error("Failed to fetch deployment history:", err);
      } finally {
        setLoading(false);
      }
    };

    if (projectName) {
      fetchDeploymentHistory();
    }
  }, [projectName]);

  return (
    <div>
      <ProjectHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Projects", href: "/" },
            { label: projectName, href: `/project/${projectName}` },
          ]}
          menuLabel="Deployment"
          title="Deployment Management"
        />

        {/* Deployment Overview */}
        <div className="mb-8">
          <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
            <Rocket className="w-4 h-4" />
            Deployment Overview
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Total Apps */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-50 rounded-lg">
                    <Package className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Total Apps</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
                  {loading ? "-" : stats?.total_apps || 0}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">apps</span>
              </div>
            </div>

            {/* Deployed Apps */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-50 rounded-lg">
                    <Rocket className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Deployed Apps</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">
                  {loading ? "-" : stats?.deployed_apps || 0}
                </span>
                <span className="text-[16px] text-[#8b8b8b]">running</span>
              </div>
            </div>

            {/* Last Deployment */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-50 rounded-lg">
                    <Clock className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Last Deployment</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[16px] text-[#8b8b8b]">
                  {loading ? "-" : stats?.last_deployment ? new Date(stats.last_deployment).toLocaleString() : "Never"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Deployment History */}
        <div className="mb-8">
          <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
            <Clock className="w-4 h-4" />
            Recent Deployments ({deployments.length})
          </h2>
          {loading ? (
            <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
              <p className="text-[13px] text-[#8b8b8b]">Loading...</p>
            </div>
          ) : deployments.length === 0 ? (
            <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
              <div className="w-16 h-16 bg-[#f6f8fa] rounded-full flex items-center justify-center mx-auto mb-4">
                <Clock className="w-6 h-6 text-[#8b8b8b]" />
              </div>
              <p className="text-[14px] text-[#0a0a0a] mb-2">No deployment history</p>
              <p className="text-[13px] text-[#8b8b8b]">
                Deploy individual apps from their respective pages
              </p>
            </div>
          ) : (
            <div className="border border-[#e3e8ee] rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-[#f6f8fa] border-b border-[#e3e8ee]">
                  <tr>
                    <th className="text-left px-4 py-3 text-[11px] font-normal text-[#8b8b8b] tracking-[0.03em]">App</th>
                    <th className="text-left px-4 py-3 text-[11px] font-normal text-[#8b8b8b] tracking-[0.03em]">Version</th>
                    <th className="text-left px-4 py-3 text-[11px] font-normal text-[#8b8b8b] tracking-[0.03em]">Commit</th>
                    <th className="text-left px-4 py-3 text-[11px] font-normal text-[#8b8b8b] tracking-[0.03em]">Branch</th>
                    <th className="text-left px-4 py-3 text-[11px] font-normal text-[#8b8b8b] tracking-[0.03em]">Deployed By</th>
                    <th className="text-left px-4 py-3 text-[11px] font-normal text-[#8b8b8b] tracking-[0.03em]">When</th>
                    <th className="text-left px-4 py-3 text-[11px] font-normal text-[#8b8b8b] tracking-[0.03em]">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {deployments.map((deployment, idx) => (
                    <tr key={idx} className="border-b border-[#e3e8ee] last:border-0 hover:bg-[#f6f8fa]">
                      <td className="px-4 py-3 text-[13px] text-[#0a0a0a]">{deployment.app_name}</td>
                      <td className="px-4 py-3 text-[11px] text-[#8b8b8b] font-mono">{deployment.version}</td>
                      <td className="px-4 py-3">
                        <code className="text-[11px] text-[#0a0a0a] font-mono">{deployment.git_sha}</code>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 text-[11px] text-[#8b8b8b]">
                          <GitBranch className="w-3 h-3" />
                          {deployment.branch}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[11px] text-[#8b8b8b]">{deployment.deployed_by}</td>
                      <td className="px-4 py-3 text-[11px] text-[#8b8b8b]">
                        {deployment.deployed_at ? new Date(deployment.deployed_at).toLocaleString() : "-"}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-1 rounded text-[10px] font-medium tracking-[0.03em] ${
                          deployment.status === 'success' 
                            ? 'bg-green-50 text-green-700' 
                            : deployment.status === 'failed'
                            ? 'bg-red-50 text-red-700'
                            : 'bg-yellow-50 text-yellow-700'
                        }`}>
                          {deployment.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

