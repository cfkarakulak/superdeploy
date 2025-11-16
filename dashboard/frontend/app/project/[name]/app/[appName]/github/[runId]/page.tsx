"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";
import { CheckCircle2, XCircle, Clock, Play, ChevronRight, ChevronDown, ExternalLink, GitBranch, GitCommit, Calendar } from "lucide-react";

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

interface WorkflowJob {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  started_at: string;
  completed_at: string | null;
  steps: WorkflowStep[];
}

interface WorkflowStep {
  name: string;
  status: string;
  conclusion: string | null;
  number: number;
  started_at: string;
  completed_at: string | null;
}

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

export default function WorkflowDetailPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  const runId = params?.runId as string;
  const [workflowRun, setWorkflowRun] = useState<WorkflowRun | null>(null);
  const [jobs, setJobs] = useState<WorkflowJob[]>([]);
  const [expandedJobs, setExpandedJobs] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>(projectName);

  // Fetch project domain
  useEffect(() => {
    const fetchProjectInfo = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/projects/${projectName}`);
        if (response.ok) {
          const data = await response.json();
          setAppDomain(data.domain || projectName);
        }
      } catch (err) {
        setAppDomain(projectName);
      }
    };
    if (projectName) fetchProjectInfo();
  }, [projectName]);

  useEffect(() => {
    const fetchWorkflowDetail = async () => {
      try {
        const runResponse = await fetch(`http://localhost:8401/api/github/${projectName}/repos/${appName}/runs/${runId}`);
        if (!runResponse.ok) throw new Error("Failed to fetch workflow run");
        const runData = await runResponse.json();
        setWorkflowRun(runData);
        const jobsResponse = await fetch(`http://localhost:8401/api/github/${projectName}/repos/${appName}/runs/${runId}/jobs`);
        if (!jobsResponse.ok) throw new Error("Failed to fetch jobs");
        const jobsData = await jobsResponse.json();
        setJobs(jobsData.jobs || []);
        if (jobsData.jobs && jobsData.jobs.length > 0) setExpandedJobs(new Set([jobsData.jobs[0].id]));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    if (projectName && appName && runId) fetchWorkflowDetail();
  }, [projectName, appName, runId]);

  const toggleJob = (jobId: number) => {
    setExpandedJobs((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const getStatusIcon = (status: string, conclusion: string | null) => {
    if (conclusion === "success") return <CheckCircle2 className="w-5 h-5 text-green-600" />;
    if (conclusion === "failure") return <XCircle className="w-5 h-5 text-red-600" />;
    if (status === "in_progress") return <Play className="w-5 h-5 text-blue-600 animate-pulse" />;
    return <Clock className="w-5 h-5 text-gray-500" />;
  };

  const formatDuration = (start: string, end: string | null) => {
    if (!end) return "Running...";
    const diff = new Date(end).getTime() - new Date(start).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  if (loading) {
    return (
      <div>
        <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          {/* Breadcrumb skeleton */}
          <div className="mb-10">
            <div className="flex items-center gap-2">
              <div className="h-[13px] w-[80px] skeleton-shimmer rounded"></div>
              <span className="text-[#6a6d77]">›</span>
              <div className="h-[13px] w-[50px] skeleton-shimmer rounded"></div>
              <span className="text-[#6a6d77]">›</span>
              <div className="h-[13px] w-[80px] skeleton-shimmer rounded"></div>
            </div>
            {/* Title skeleton */}
            <div className="h-[32px] w-[280px] skeleton-shimmer rounded"></div>
          </div>

          {/* Summary Cards skeleton */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="h-[110px] rounded-lg skeleton-shimmer"></div>
            ))}
          </div>

          {/* Jobs title skeleton */}
          <div className="mb-4">
            <div className="h-[14px] w-[80px] skeleton-shimmer rounded"></div>
          </div>

          {/* Jobs skeleton */}
          <div className="space-y-3">
            {Array.from({ length: 2 }, (_, i) => (
              <div key={i} className="h-[80px] rounded-lg skeleton-shimmer"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !workflowRun) {
    return (
      <div>
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">Failed to load workflow</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
      <AppHeader />
      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader 
          breadcrumbs={[
            { label: appDomain || projectName, href: `/project/${projectName}` },
            { label: appName, href: `/project/${projectName}/app/${appName}` },
            { label: "Workflows", href: `/project/${projectName}/app/${appName}/github` }
          ]} 
          title={`${workflowRun.name} #${workflowRun.run_number}`} 
        />

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Status */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                {workflowRun.conclusion === "success" ? (
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                ) : workflowRun.conclusion === "failure" ? (
                  <div className="w-2 h-2 rounded-full bg-red-500"></div>
                ) : (
                  <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></div>
                )}
              </div>
              <div className="flex-1">
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Status</p>
                <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                  workflowRun.conclusion === "success"
                    ? "bg-green-500 text-white"
                    : workflowRun.conclusion === "failure"
                    ? "bg-red-500 text-white"
                    : "bg-amber-500 text-white"
                }`}>
                  {workflowRun.conclusion || workflowRun.status}
                </span>
              </div>
            </div>
          </div>

          {/* Branch & Commit */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            <div className="space-y-3">
              <div>
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Branch</p>
                <div className="flex items-center gap-1.5">
                  <GitBranch className="w-3 h-3 text-[#8b8b8b]" />
                  <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light truncate">{workflowRun.head_branch}</span>
                </div>
              </div>
              <div className="pt-2 border-t border-[#e3e8ee]">
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Commit</p>
                <div className="flex items-center gap-1.5">
                  <GitCommit className="w-3 h-3 text-[#8b8b8b]" />
                  <code className="text-[11px] font-mono text-[#0a0a0a] tracking-[0.03em] font-light">{workflowRun.head_sha.substring(0, 7)}</code>
                </div>
              </div>
            </div>
          </div>

          {/* Time & Link */}
          <div className="p-5 border border-[#e3e8ee] hover:border-[#b9c1c6] rounded-lg">
            <div className="space-y-3">
              <div>
                <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Started</p>
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3 h-3 text-[#8b8b8b]" />
                  <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">
                    {new Date(workflowRun.created_at).toLocaleString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </span>
                </div>
              </div>
              <div className="pt-2 border-t border-[#e3e8ee]">
                <a 
                  href={workflowRun.html_url} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="inline-flex items-center gap-1.5 text-[11px] text-[#0a0a0a] hover:text-[#0969da] tracking-[0.03em] font-light transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  View on GitHub
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Jobs Section */}
        <div className="mb-4">
          <h2 className="text-[11px] text-[#777] leading-tight tracking-[0.03em] font-light">
            Jobs ({jobs.length})
          </h2>
        </div>

        <div className="space-y-3">
          {jobs.map((job) => (
            <div key={job.id} className="border border-[#e3e8ee] rounded-lg overflow-hidden transition-all">
              <div 
                onClick={() => toggleJob(job.id)} 
                className="flex items-center justify-between p-4 cursor-pointer bg-white transition-colors"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {/* Status Icon */}
                  <div className="flex-shrink-0">
                    {job.conclusion === "success" ? (
                      <div className="w-2 h-2 rounded-full bg-green-500"></div>
                    ) : job.conclusion === "failure" ? (
                      <div className="w-2 h-2 rounded-full bg-red-500"></div>
                    ) : job.status === "in_progress" ? (
                      <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></div>
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                    )}
                  </div>
                  
                  {/* Job Info */}
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] text-[#0a0a0a] mb-1 truncate">{job.name}</div>
                    <div className="flex items-center gap-3 text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatDuration(job.started_at, job.completed_at)}</span>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                        job.conclusion === "success" ? "bg-green-500 text-white" :
                        job.conclusion === "failure" ? "bg-red-500 text-white" :
                        "bg-amber-500 text-white"
                      }`}>
                        {job.conclusion || job.status}
                      </span>
                    </div>
                  </div>
                </div>
                
                {/* Expand Icon */}
                <div className="flex-shrink-0 ml-3">
                  {expandedJobs.has(job.id) ? (
                    <ChevronDown className="w-4 h-4 text-[#8b8b8b]" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-[#8b8b8b]" />
                  )}
                </div>
              </div>
              
              {/* Steps */}
              {expandedJobs.has(job.id) && job.steps && job.steps.length > 0 && (
                <div className="border-t border-[#e3e8ee]">
                  <div className="px-4 py-2 bg-[#f6f8fa]">
                    <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                      Steps ({job.steps.length})
                    </span>
                  </div>
                  <div className="px-4 py-2">
                    {job.steps.map((step, index) => (
                      <div 
                        key={step.number} 
                        className={`flex items-center gap-2 py-2 ${
                          index !== job.steps.length - 1 ? 'border-b border-[#f0f0f0]' : ''
                        }`}
                      >
                        {/* Status Icon */}
                        <div className="flex-shrink-0">
                          {step.conclusion === "success" ? (
                            <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
                          ) : step.conclusion === "failure" ? (
                            <div className="w-1.5 h-1.5 rounded-full bg-red-500"></div>
                          ) : step.status === "in_progress" ? (
                            <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></div>
                          ) : (
                            <div className="w-1.5 h-1.5 rounded-full bg-gray-400"></div>
                          )}
                        </div>
                        
                        {/* Step Info */}
                        <div className="flex-1 min-w-0 flex items-center justify-between">
                          <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light truncate">{step.name}</span>
                          <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light ml-3 flex-shrink-0">
                            {formatDuration(step.started_at, step.completed_at)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
        
        {jobs.length === 0 && (
          <div className="text-center py-12 text-[#8b8b8b] border border-[#e3e8ee] rounded-lg">
            <p className="text-[13px] tracking-[0.03em] font-light">No jobs found</p>
          </div>
        )}
      </div>
    </div>
  );
}
