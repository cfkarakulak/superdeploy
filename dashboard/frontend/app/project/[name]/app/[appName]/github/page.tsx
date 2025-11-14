"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
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
}

interface AppInfo {
  repo: string;
  owner: string;
}

// Breadcrumb Skeleton
const BreadcrumbSkeleton = () => (
  <div className="flex items-center gap-3 mb-6">
    <div className="w-5 h-5 bg-[#e3e8ee] rounded skeleton-animated" />
    <div className="flex items-center gap-2">
      <div className="w-[80px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[100px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[100px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[80px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Header Skeleton
const GitHubHeaderSkeleton = () => (
  <div className="mb-6">
    <div className="w-[220px] h-[28px] bg-[#e3e8ee] rounded-md mb-2 skeleton-animated" />
    <div className="w-[250px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
  </div>
);

// Workflow Run Card Skeleton
const WorkflowRunCardSkeleton = () => (
  <div className="bg-white rounded-lg p-5 shadow-sm">
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-3 flex-1">
        <div className="w-6 h-6 bg-[#e3e8ee] rounded-full skeleton-animated" />
        <div className="flex-1">
          <div className="w-[200px] h-[20px] bg-[#e3e8ee] rounded-md mb-2 skeleton-animated" />
          <div className="w-[150px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
        </div>
      </div>
      <div className="w-[70px] h-[24px] bg-[#e3e8ee] rounded-full skeleton-animated" />
    </div>
    <div className="flex items-center gap-4 text-sm">
      <div className="w-[120px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[140px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Full Page Skeleton
const GitHubPageSkeleton = () => (
  <div>
    <BreadcrumbSkeleton />
    <GitHubHeaderSkeleton />
    <div className="space-y-4">
      {Array.from({ length: 4 }, (_, i) => (
        <WorkflowRunCardSkeleton key={`workflow-skeleton-${i}`} />
      ))}
    </div>
  </div>
);

export default function AppGitHubPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      fetchWorkflows();
      const interval = setInterval(fetchWorkflows, 30000);
      return () => clearInterval(interval);
    }
  }, [projectName, appName]);

  return (
    <div>
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumb={{
            label: "Actions",
            href: `/project/${projectName}/app/${appName}`
          }}
          title="Workflow Runs"
        />

        {loading ? (
          <div className="space-y-3 mt-6">
            {Array.from({ length: 4 }, (_, i) => (
              <WorkflowRunCardSkeleton key={`workflow-skeleton-${i}`} />
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">Failed to load workflows: {error}</p>
            <p className="text-[13px] mt-2">Make sure REPOSITORY_TOKEN is set in secrets.</p>
          </div>
        ) : workflows.length === 0 ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">No workflow runs found</p>
            <p className="text-[13px] mt-2">Workflows will appear here once you push to GitHub</p>
          </div>
        ) : (
          <div className="space-y-2 mt-6">
            {workflows.map((run) => (
              <div
                key={run.id}
                onClick={() => router.push(`/project/${projectName}/app/${appName}/github/${run.id}`)}
                className="group bg-white rounded-lg p-4 border border-[#e3e8ee] hover:border-[#0969da] hover:shadow-md cursor-pointer transition-all"
              >
                <div className="flex items-start gap-4">
                  {/* Status Icon */}
                  <div className="flex-shrink-0 mt-1">
                    {run.conclusion === "success" ? (
                      <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 16 16">
                          <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
                        </svg>
                      </div>
                    ) : run.conclusion === "failure" ? (
                      <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 16 16">
                          <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z" />
                        </svg>
                      </div>
                    ) : run.status === "in_progress" ? (
                      <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center animate-pulse">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 16 16">
                          <path d="M8 0a8 8 0 100 16A8 8 0 008 0z" />
                        </svg>
                      </div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-gray-400 flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 16 16">
                          <path d="M8 0a8 8 0 100 16A8 8 0 008 0z" />
                        </svg>
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    {/* Workflow Name */}
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-[14px] font-semibold text-[#0a0a0a] group-hover:text-[#0969da] transition-colors">
                        {run.name}
                      </h3>
                    </div>

                    {/* Metadata */}
                    <div className="flex items-center gap-2 text-[12px] text-[#656d76] mb-2">
                      <span className="font-mono">#{run.run_number}</span>
                      <span>•</span>
                      <span className={`px-1.5 py-0.5 rounded text-[11px] font-medium ${
                        run.conclusion === "success"
                          ? "text-green-700"
                          : run.conclusion === "failure"
                          ? "text-red-700"
                          : run.status === "in_progress"
                          ? "text-amber-700"
                          : "text-gray-700"
                      }`}>
                        {run.conclusion || run.status}
                      </span>
                    </div>

                    {/* Branch and Commit */}
                    <div className="flex items-center gap-3 text-[12px] text-[#656d76]">
                      <div className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
                          <path fillRule="evenodd" d="M11.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122V6A2.5 2.5 0 0110 8.5H6a1 1 0 00-1 1v1.128a2.251 2.251 0 11-1.5 0V5.372a2.25 2.25 0 111.5 0v1.836A2.492 2.492 0 016 7h4a1 1 0 001-1v-.628A2.25 2.25 0 019.5 3.25zM4.25 12a.75.75 0 100 1.5.75.75 0 000-1.5zM3.5 3.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0z" />
                        </svg>
                        <span className="font-medium">{run.head_branch}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
                          <path fillRule="evenodd" d="M10.5 7.75a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0zm1.43.75a4.002 4.002 0 01-7.86 0H.75a.75.75 0 110-1.5h3.32a4.002 4.002 0 017.86 0h3.32a.75.75 0 110 1.5h-3.32z" />
                        </svg>
                        <code className="font-mono text-[11px]">{run.head_sha.substring(0, 7)}</code>
                      </div>
                      <span>•</span>
                      <span>{new Date(run.created_at).toLocaleString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}</span>
                    </div>
                  </div>

                  {/* External Link */}
                  <a
                    href={run.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex-shrink-0 p-2 text-[#656d76] hover:text-[#0969da] transition-colors"
                    title="View on GitHub"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

