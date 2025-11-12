"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

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
  <div className="max-w-[960px] mx-auto py-8 px-6">
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
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
      fetchWorkflows();
      const interval = setInterval(fetchWorkflows, 30000);
      return () => clearInterval(interval);
    }
  }, [projectName, appName]);

  if (loading) {
    return <GitHubPageSkeleton />;
  }

  return (
    <div className="max-w-[960px] mx-auto py-8 px-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-6">
        <Link href={`/project/${projectName}/app/${appName}`} className="text-gray-500 hover:text-gray-900">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-900">
            Projects
          </Link>
          <span>/</span>
          <Link href={`/project/${projectName}`} className="hover:text-gray-900">
            {projectName}
          </Link>
          <span>/</span>
          <Link
            href={`/project/${projectName}/app/${appName}`}
            className="hover:text-gray-900"
          >
            {appName}
          </Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">GitHub</span>
        </div>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-2">GitHub Actions</h1>
        <p className="text-gray-600">
          Deployment history and workflow runs for {appName}
        </p>
      </div>

      {/* Repository Link */}
      <div className="bg-white shadow-sm rounded-lg p-4 mb-6">
        <a
          href={`https://github.com/cheapa-io/${appName}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline"
        >
          github.com/cheapa-io/{appName}
        </a>
      </div>

      {/* Workflow Runs */}
      {error ? (
        <div className="bg-red-50 rounded-lg p-4 shadow-sm">
          <p className="text-red-800">{error}</p>
        </div>
      ) : workflows.length === 0 ? (
        <div className="bg-white shadow-sm rounded-lg p-8 text-center text-gray-600">
          No workflow runs found
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((run) => (
            <a
              key={run.id}
              href={run.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block bg-white shadow-sm rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${
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
                    <div className="font-medium">{run.name}</div>
                    <div className="text-sm text-gray-600">
                      #{run.run_number} • {run.head_branch} •{" "}
                      {run.head_sha.substring(0, 7)}
                    </div>
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  {new Date(run.created_at).toLocaleString()}
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
