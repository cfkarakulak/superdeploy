"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { GitBranch, GitCommit, User, Clock } from "lucide-react";
import { AppHeader, PageHeader } from "@/components";

interface WorkflowRun {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  created_at: string;
  updated_at: string;
  head_branch: string;
  head_sha: string;
  run_number: number;
  html_url: string;
  actor?: {
    login: string;
    avatar_url: string;
  };
}

interface AppInfo {
  repo: string;
  owner: string;
}

export default function AppGitHubPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>("");

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

  useEffect(() => {
    const fetchAppInfo = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/apps/${projectName}/list`);
        const data = await response.json();
        const app = data.apps.find((a: any) => a.name === appName);
        if (app) {
          setAppInfo({ repo: app.repo || app.name, owner: app.owner || 'cheapaio' });
        }
      } catch (err) {
        console.error("Failed to fetch app info:", err);
      }
    };

    const fetchProjectInfo = async () => {
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

    const fetchWorkflows = async () => {
      try {
        const response = await fetch(
          `http://localhost:8401/api/github/${projectName}/repos/${appName}/workflows`
        );
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          const errorMsg = errorData?.detail || `HTTP ${response.status}: ${response.statusText}`;
          throw new Error(errorMsg);
        }
        
        const data = await response.json();
        setWorkflows(data.workflow_runs || []);
      } catch (err) {
        console.error("GitHub workflows fetch error:", err);
        setError(err instanceof Error ? err.message : "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    };

    if (projectName && appName) {
      fetchAppInfo();
      fetchProjectInfo();
      fetchWorkflows();
      const interval = setInterval(fetchWorkflows, 30000);
      return () => clearInterval(interval);
    }
  }, [projectName, appName]);

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
              menuLabel="Actions"
              title="Workflows"
            />

            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                {Array.from({ length: 6 }, (_, i) => (
                  <div key={i} className="h-[185px] rounded-lg skeleton-shimmer"></div>
                ))}
              </div>
        ) : error ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">Failed to load workflows: {error}</p>
            <p className="text-[13px] mt-2">Make sure REPOSITORY_TOKEN is set in secrets.</p>
          </div>
        ) : workflows.length === 0 ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[11px] tracking-[0.03em] font-light">No workflow runs found</p>
            <p className="text-[13px] mt-2">Workflows will appear here once you push to GitHub</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            {workflows.slice(0, 6).map((run) => (
              <div
                key={run.id}
                onClick={() => router.push(`/project/${projectName}/app/${appName}/github/${run.id}`)}
                className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg cursor-pointer"
              >
                {/* Header: Status + Title */}
                <div className="flex items-start gap-3 mb-4">
                  {/* Status Icon */}
                  <div className="flex-shrink-0 mt-2">
                    {run.conclusion === "success" ? (
                      <div className="w-2 h-2 rounded-full bg-green-500"></div>
                    ) : run.conclusion === "failure" ? (
                      <div className="w-2 h-2 rounded-full bg-red-500"></div>
                    ) : run.status === "in_progress" ? (
                      <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></div>
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                    )}
                  </div>

                  {/* Title & Badge */}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-[14px] text-[#0a0a0a] mb-1 truncate">
                      {run.name}
                    </h3>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                        run.conclusion === "success"
                          ? "bg-green-500 text-white"
                          : run.conclusion === "failure"
                          ? "bg-red-500 text-white"
                          : run.status === "in_progress"
                          ? "bg-amber-500 text-white"
                          : "bg-gray-400 text-white"
                      }`}>
                        {run.conclusion || run.status}
                      </span>
                      <span className="text-[11px] font-mono text-[#8b8b8b] tracking-[0.03em] font-light">
                        #{run.run_number}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Divider */}
                <div className="border-t border-[#e3e8ee] mb-3"></div>

                {/* Details Grid */}
                <div className="space-y-2">
                  {run.actor && (
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">Actor</span>
                      <div className="flex items-center gap-1.5">
                        <User className="w-3 h-3 text-[#8b8b8b]" />
                        <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">{run.actor.login}</span>
                      </div>
                    </div>
                  )}
                  
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">Branch</span>
                    <div className="flex items-center gap-1.5">
                      <GitBranch className="w-3 h-3 text-[#8b8b8b]" />
                      <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light truncate max-w-[150px]">{run.head_branch}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">Commit</span>
                    <div className="flex items-center gap-1.5">
                      <GitCommit className="w-3 h-3 text-[#8b8b8b]" />
                      <code className="text-[11px] font-mono text-[#0a0a0a] tracking-[0.03em] font-light">{run.head_sha.substring(0, 7)}</code>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">Time</span>
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3 h-3 text-[#8b8b8b]" />
                      <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">
                        {new Date(run.created_at).toLocaleString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
