"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";

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
        
        if (!response.ok) throw new Error("Failed to fetch workflows");
        
        const data = await response.json();
        setWorkflows(data.workflow_runs || []);
      } catch (err) {
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
      
      {loading ? (
        <GitHubPageSkeleton />
      ) : (
        <>
          <PageHeader
            breadcrumb={{
              label: "GitHub",
              href: `/project/${projectName}/app/${appName}/github`
            }}
            title="Workflow Runs"
            description={`Automated CI/CD pipelines and GitHub Actions for ${appName}`}
          />

      {/* Workflow Runs */}
      {error ? (
        <div className="alert alert-error">
          <p><strong>Error:</strong> {error}</p>
          <p className="text-[13px] mt-2">Make sure GITHUB_TOKEN is set in secrets and the repository exists.</p>
        </div>
      ) : workflows.length === 0 ? (
        <div className="bg-white rounded-[16px] p-[20px] text-center text-[#525252] shadow-[0_0_0_1px_rgba(11,26,38,0.06),0_4px_12px_rgba(0,0,0,0.03),0_1px_3px_rgba(0,0,0,0.04)]">
          No workflow runs found
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((run) => (
            <div
              key={run.id}
              onClick={() => router.push(`/project/${projectName}/app/${appName}/github/${run.id}`)}
              className="block bg-white rounded-[16px] p-[20px] shadow-[0_0_0_1px_rgba(11,26,38,0.06),0_4px_12px_rgba(0,0,0,0.03),0_1px_3px_rgba(0,0,0,0.04)] hover:shadow-[0_2px_6px_rgba(0,0,0,0.08)] cursor-pointer transition-all"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2.5 py-1 rounded-full text-[11px]  uppercase ${
                      run.conclusion === "success"
                        ? "bg-green-100 text-green-800"
                        : run.conclusion === "failure"
                        ? "bg-red-100 text-red-800"
                        : run.status === "in_progress"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {run.conclusion || run.status}
                  </span>
                  <div>
                    <div className="text-[15px]  text-[#0a0a0a]">{run.name}</div>
                    <div className="text-[13px] text-[#8b8b8b] mt-0.5">
                      #{run.run_number} • {run.head_branch} • {run.head_sha.substring(0, 7)}
                    </div>
                  </div>
                </div>
                <a
                  href={run.html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-[#8b8b8b] hover:text-[#0a0a0a]"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
              <div className="text-[13px] text-[#8b8b8b]">
                {new Date(run.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
        </>
      )}
    </div>
  );
}

