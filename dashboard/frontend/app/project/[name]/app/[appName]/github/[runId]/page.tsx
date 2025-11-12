"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink, Check, X, Clock } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components";

interface WorkflowRun {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  created_at: string;
  updated_at: string;
  head_branch: string;
  head_sha: string;
  head_commit: {
    message: string;
    author: {
      name: string;
      email: string;
    };
  };
  run_number: number;
  html_url: string;
  run_started_at: string;
}

interface Job {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  started_at: string;
  completed_at: string | null;
  html_url: string;
  steps: Step[];
}

interface Step {
  name: string;
  status: string;
  conclusion: string | null;
  number: number;
  started_at: string;
  completed_at: string | null;
}

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  const runId = params?.runId as string;

  const [workflowRun, setWorkflowRun] = useState<WorkflowRun | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchWorkflowDetails = async () => {
      try {
        const [runResponse, jobsResponse] = await Promise.all([
          fetch(`http://localhost:8401/api/github/${projectName}/repos/${appName}/runs/${runId}`),
          fetch(`http://localhost:8401/api/github/${projectName}/repos/${appName}/runs/${runId}/jobs`)
        ]);

        if (!runResponse.ok || !jobsResponse.ok) {
          throw new Error("Failed to fetch workflow details");
        }

        const runData = await runResponse.json();
        const jobsData = await jobsResponse.json();

        setWorkflowRun(runData);
        setJobs(jobsData.jobs || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    };

    if (projectName && appName && runId) {
      fetchWorkflowDetails();
    }
  }, [projectName, appName, runId]);

  const getStatusIcon = (status: string, conclusion: string | null) => {
    if (conclusion === "success") return <Check className="w-4 h-4 text-green-600" />;
    if (conclusion === "failure") return <X className="w-4 h-4 text-red-600" />;
    if (status === "in_progress") return <Clock className="w-4 h-4 text-blue-600" />;
    return <Clock className="w-4 h-4 text-gray-600" />;
  };

  const getStatusColor = (status: string, conclusion: string | null) => {
    if (conclusion === "success") return "bg-green-100 text-green-800";
    if (conclusion === "failure") return "bg-red-100 text-red-800";
    if (status === "in_progress") return "bg-blue-100 text-blue-800";
    return "bg-gray-100 text-gray-800";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-[15px] text-[#8b8b8b]">Loading...</div>
      </div>
    );
  }

  if (error || !workflowRun) {
    return (
      <div className="bg-red-50 rounded-lg p-4 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
        <p className="text-[15px] text-red-800">{error || "Workflow not found"}</p>
      </div>
    );
  }

  return (
    <div>
      <AppHeader />
      
      {/* Back Button */}
      <Button
        onClick={() => router.back()}
        variant="ghost"
        className="mb-6 -ml-3"
        size="sm"
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to workflows
      </Button>

      <PageHeader
        breadcrumbs={[
          { label: "Projects", href: "/" },
          { label: projectName, href: `/project/${projectName}` },
          { label: "Apps", href: `/project/${projectName}` },
          { label: appName, href: `/project/${projectName}/app/${appName}` },
          { label: "GitHub", href: `/project/${projectName}/app/${appName}/github` },
          { label: `Run #${workflowRun.run_number}`, href: `/project/${projectName}/app/${appName}/github/${runId}` }
        ]}
        title={workflowRun.name}
        description={`Workflow run #${workflowRun.run_number} on ${workflowRun.head_branch} branch (${workflowRun.head_sha.substring(0, 7)})`}
      />

      <div className="mb-6 flex items-center gap-3">
        <span className={`px-2.5 py-1 rounded-full text-[11px] uppercase ${getStatusColor(workflowRun.status, workflowRun.conclusion)}`}>
          {workflowRun.conclusion || workflowRun.status}
        </span>
        <a
          href={workflowRun.html_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#8b8b8b] hover:text-[#0a0a0a]"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>

      {/* Commit Info */}
      <div className="bg-white rounded-lg p-5 mb-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
        <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-3">Commit</h2>
        <p className="text-[15px] text-[#0a0a0a] mb-2">{workflowRun.head_commit?.message}</p>
        <p className="text-[13px] text-[#8b8b8b]">
          by {workflowRun.head_commit?.author?.name} • {new Date(workflowRun.created_at).toLocaleString()}
        </p>
      </div>

      {/* Jobs */}
      <div className="space-y-4">
        <h2 className="text-[17px] font-semibold text-[#0a0a0a]">Jobs</h2>
        {jobs.map((job) => (
          <div key={job.id} className="bg-white rounded-lg p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {getStatusIcon(job.status, job.conclusion)}
                <div>
                  <h3 className="text-[15px]  text-[#0a0a0a]">{job.name}</h3>
                  <p className="text-[13px] text-[#8b8b8b]">
                    {job.started_at && new Date(job.started_at).toLocaleString()}
                    {job.completed_at && ` - ${new Date(job.completed_at).toLocaleString()}`}
                  </p>
                </div>
              </div>
              <a
                href={job.html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#8b8b8b] hover:text-[#0a0a0a]"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>

            {/* Steps */}
            {job.steps && job.steps.length > 0 && (
              <div className="space-y-2 mt-4 pt-4 border-t border-[#e3e3e3]">
                {job.steps.map((step, idx) => (
                  <div key={idx} className="flex items-center gap-3 text-[13px]">
                    {getStatusIcon(step.status, step.conclusion)}
                    <span className={step.conclusion === "failure" ? "text-red-600" : "text-[#525252]"}>
                      {step.name}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

