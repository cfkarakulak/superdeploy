"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";
import { CheckCircle2, XCircle, Clock, Play, ChevronRight, ChevronDown, ExternalLink } from "lucide-react";

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
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-[#e3e8ee] rounded w-1/3"></div>
            <div className="h-4 bg-[#e3e8ee] rounded w-1/2"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !workflowRun) {
    return (
      <div>
        <AppHeader />
        <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">Failed to load workflow</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <AppHeader />
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader 
          breadcrumbs={[
            { label: "Overview", href: `/project/${projectName}/app/${appName}` },
            { label: "Actions", href: `/project/${projectName}/app/${appName}/github` }
          ]} 
          title={`${workflowRun.name} #${workflowRun.run_number}`} 
        />
        <div className="bg-[#f6f8fa] rounded-lg p-4 mb-6 border border-[#d0d7de]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {getStatusIcon(workflowRun.status, workflowRun.conclusion)}
              <div>
                <span className={`px-2.5 py-1 rounded-full text-[11px] font-medium uppercase ${workflowRun.conclusion === "success" ? "bg-green-100 text-green-700" : workflowRun.conclusion === "failure" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-700"}`}>
                  {workflowRun.conclusion || workflowRun.status}
                </span>
                <div className="text-[12px] text-[#656d76] mt-1">
                  {workflowRun.head_branch} • {workflowRun.head_sha.substring(0, 7)}
                </div>
              </div>
            </div>
            <a href={workflowRun.html_url} target="_blank" rel="noopener noreferrer" className="text-[#656d76] hover:text-[#0969da]">
              <ExternalLink className="w-5 h-5" />
            </a>
          </div>
        </div>
        <div className="space-y-2">
          {jobs.map((job) => (
            <div key={job.id} className="border border-[#d0d7de] rounded-lg overflow-hidden">
              <div onClick={() => toggleJob(job.id)} className="flex items-center justify-between p-4 bg-[#f6f8fa] cursor-pointer hover:bg-[#eaeef2] transition-colors">
                <div className="flex items-center gap-3 flex-1">
                  {getStatusIcon(job.status, job.conclusion)}
                  <div className="flex-1">
                    <div className="text-[14px] font-semibold text-[#0a0a0a]">{job.name}</div>
                    <div className="text-[12px] text-[#656d76]">{formatDuration(job.started_at, job.completed_at)}</div>
                  </div>
                </div>
                {expandedJobs.has(job.id) ? <ChevronDown className="w-5 h-5 text-[#656d76]" /> : <ChevronRight className="w-5 h-5 text-[#656d76]" />}
              </div>
              {expandedJobs.has(job.id) && job.steps && job.steps.length > 0 && (
                <div className="bg-white">
                  {job.steps.map((step) => (
                    <div key={step.number} className="flex items-center gap-3 px-4 py-3 border-t border-[#d0d7de]">
                      {getStatusIcon(step.status, step.conclusion)}
                      <div className="flex-1">
                        <div className="text-[13px] text-[#0a0a0a]">{step.name}</div>
                        <div className="text-[11px] text-[#656d76]">{formatDuration(step.started_at, step.completed_at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        {jobs.length === 0 && (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">No jobs found</p>
          </div>
        )}
      </div>
    </div>
  );
}
