"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader, Button, Dialog as DialogComponent, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components";
import { 
  GitBranch, 
  GitCommit, 
  Calendar, 
  User, 
  CheckCircle2, 
  RotateCcw,
  Clock,
  Tag,
  Activity
} from "lucide-react";
import { parseAnsi, segmentToStyle } from "@/lib/ansiParser";

interface Release {
  version: string;
  git_sha: string;
  deployed_by: string;
  deployed_at: string;
  branch: string;
  commit_message: string;
  status: string;
  author?: {
    login: string;
    avatar_url: string;
  };
  duration_seconds?: number;
  changed_files?: number;
  additions?: number;
  deletions?: number;
  environment?: string;
}

// Skeleton Components  
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

const ReleasesTableSkeleton = () => (
  <div className="space-y-4">
    {Array.from({ length: 3 }, (_, i) => (
      <div key={i} className="h-[180px] rounded-lg skeleton-shimmer"></div>
    ))}
  </div>
);

export default function DeployPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  
  const [releases, setReleases] = useState<Release[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [switching, setSwitching] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>("");
  const [rollbackDialogOpen, setRollbackDialogOpen] = useState(false);
  const [rollbackLogs, setRollbackLogs] = useState<string>("");
  const [selectedVersion, setSelectedVersion] = useState<Release | null>(null);
  const rollbackLogsEndRef = useRef<HTMLDivElement>(null);

  // Fetch app domain
  useEffect(() => {
    const fetchAppInfo = async () => {
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
    if (projectName && appName) fetchAppInfo();
  }, [projectName, appName]);

  const fetchReleases = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `http://localhost:8401/api/apps/${projectName}/${appName}/releases`
      );
      if (!response.ok) throw new Error("Failed to fetch releases");
      const data = await response.json();
      setReleases(data.releases || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectName && appName) {
      fetchReleases();
    }
  }, [projectName, appName]);

  const handleSwitch = async (release: Release) => {
    setSelectedVersion(release);
    setSwitching(release.git_sha);
    setRollbackLogs("");
    setRollbackDialogOpen(true);

    try {
      const response = await fetch(
        `http://localhost:8401/api/apps/${projectName}/${appName}/switch`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ git_sha: release.git_sha }),
        }
      );

      if (!response.ok) {
        const error = await response.text();
        setRollbackLogs(prev => prev + `\n❌ Error: ${error}`);
        return;
      }

      // Stream the logs (keep ANSI codes for color rendering)
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          setRollbackLogs(prev => prev + chunk);
        }
      }

      // Refresh releases list after successful switch
      await fetchReleases();
    } catch (err) {
      setRollbackLogs(prev => prev + `\n❌ Error: ${err instanceof Error ? err.message : "Failed to switch version"}`);
    } finally {
      setSwitching(null);
    }
  };

  // Auto-scroll to bottom when new logs appear
  useEffect(() => {
    if (rollbackLogsEndRef.current) {
      rollbackLogsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [rollbackLogs]);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const formatDate = (dateString: string) => {
    if (dateString === "-") return "-";
    try {
      const date = new Date(dateString);
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateString;
    }
  };

  const getRelativeTime = (dateString: string) => {
    if (dateString === "-") return "-";
    try {
      const date = new Date(dateString);
      const now = new Date();
      const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
      
      if (seconds < 60) return "just now";
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}h ago`;
      const days = Math.floor(hours / 24);
      if (days < 30) return `${days}d ago`;
      const months = Math.floor(days / 30);
      if (months < 12) return `${months}mo ago`;
      const years = Math.floor(months / 12);
      return `${years}y ago`;
    } catch {
      return dateString;
    }
  };

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
            menuLabel="Deploy"
            title="Deployment History"
          />

        {loading ? (
          <ReleasesTableSkeleton />
        ) : error ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[13px] tracking-[0.03em] font-light">Failed to load releases: {error}</p>
          </div>
        ) : releases.length === 0 ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[13px] tracking-[0.03em] font-light">No deployment history found</p>
            <p className="text-[11px] tracking-[0.03em] font-light mt-2">Deploy the app first: <code className="bg-[#f6f8fa] px-2 py-1 rounded border border-[#e3e8ee]">git push origin production</code></p>
          </div>
        ) : (
          <div className="space-y-4">
            {releases.map((release, index) => {
              const isLatest = index === 0;
              
              return (
                <div key={index} className="border border-[#e3e8ee] rounded-lg transition-all overflow-hidden">
                    {/* Header */}
                  <div className="px-5 py-4 border-b border-[#e3e8ee] flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      {/* Status Dot */}
                      <div className="shrink-0">
                        {isLatest ? (
                          <div className="w-2 h-2 rounded-full bg-green-500"></div>
                        ) : (
                          <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                        )}
                      </div>
                      
                      {/* Version */}
                      <div className="flex items-center gap-1.5 min-w-0">
                        <Tag className="w-3 h-3 text-[#8b8b8b] shrink-0" />
                        <code className="text-[11px] font-mono text-[#0a0a0a] tracking-[0.03em] font-light">
                          v{release.version}
                        </code>
                      </div>

                      {/* Relative Time */}
                      <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light shrink-0">
                        {getRelativeTime(release.deployed_at)}
                      </span>
                    </div>

                    {/* Current Badge or Rollback Button */}
                    <div className="flex items-center gap-2 shrink-0">
                      {isLatest ? (
                        <span className="inline-flex items-center justify-center gap-1.5 rounded-[10px] text-[11px] px-3 py-1.5 font-medium tracking-[0.03em] bg-green-500 text-white shrink-0">
                          Current
                        </span>
                      ) : (
                        <Button
                          onClick={() => handleSwitch(release)}
                          disabled={switching !== null}
                          size="sm"
                          variant="primary"
                          icon={<RotateCcw className="w-3 h-3" />}
                        >
                          {switching === release.git_sha ? "Switching..." : "Rollback"}
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Body */}
                  <div className="px-5 py-4 space-y-4">
                    {/* Commit Message */}
                    {release.commit_message && release.commit_message !== "-" && (
                      <div>
                        <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Commit</p>
                        <p className="text-[12px] text-[#0a0a0a] tracking-[0.03em] font-light">
                          {release.commit_message}
                        </p>
                      </div>
                    )}

                    {/* Stats Row (if available) */}
                    {(release.duration_seconds || release.changed_files || release.additions !== undefined) && (
                      <div className="flex items-center gap-4 text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light pb-3 border-b border-[#e3e8ee]">
                        {release.duration_seconds && (
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3 h-3" />
                            <span>{formatDuration(release.duration_seconds)}</span>
                          </div>
                        )}
                        {release.changed_files !== undefined && release.changed_files > 0 && (
                          <div className="flex items-center gap-1.5">
                            <span>{release.changed_files} {release.changed_files === 1 ? 'file' : 'files'}</span>
                          </div>
                        )}
                        {release.additions !== undefined && release.deletions !== undefined && (
                          <div className="flex items-center gap-2">
                            <span className="text-green-600">+{release.additions}</span>
                            <span className="text-red-600">-{release.deletions}</span>
                          </div>
                        )}
                        {release.environment && (
                          <div className="ml-auto">
                            <span className="px-2 py-0.5 rounded bg-[#f6f8fa] border border-[#e3e8ee] text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">
                              {release.environment}
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {/* Author / Deployed By */}
                      <div>
                        <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">
                          {release.author ? 'Author' : 'Deployed By'}
                        </p>
                        <div className="flex items-center gap-1.5">
                          {release.author ? (
                            <>
                              <img 
                                src={release.author.avatar_url} 
                                alt={release.author.login}
                                className="w-4 h-4 rounded-full"
                              />
                              <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">
                                {release.author.login}
                              </span>
                            </>
                          ) : (
                            <>
                              <User className="w-3 h-3 text-[#8b8b8b]" />
                              <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">
                                {release.deployed_by}
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Branch */}
                      <div>
                        <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">
                          Branch
                        </p>
                        <div className="flex items-center gap-1.5">
                          <GitBranch className="w-3 h-3 text-[#8b8b8b]" />
                          <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light">
                            {release.branch}
                          </span>
                        </div>
                      </div>

                      {/* Commit SHA */}
                      <div>
                        <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">
                          Commit SHA
                        </p>
                        <code className="text-[11px] font-mono text-[#0a0a0a] bg-white px-2 py-1 rounded border border-[#e3e8ee] tracking-[0.03em] font-light">
                          {release.git_sha.substring(0, 7)}
                        </code>
                      </div>

                      {/* Timestamp */}
                      <div>
                        <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">
                          Deployed
                        </p>
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3 h-3 text-[#8b8b8b]" />
                          <span className="text-[11px] text-[#0a0a0a] tracking-[0.03em] font-light" title={formatDate(release.deployed_at)}>
                            {getRelativeTime(release.deployed_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Rollback Dialog */}
      <DialogComponent open={rollbackDialogOpen} onOpenChange={setRollbackDialogOpen}>
        <DialogContent className="max-w-[800px] sm:max-w-[800px] w-[800px]">
          <DialogHeader>
            <DialogTitle>Rollback to v{selectedVersion?.version}</DialogTitle>
          </DialogHeader>

          {/* Terminal Output */}
          <div className="py-4">
            <div className="terminal-container scrollbar-custom rounded-lg p-4 text-[13px] leading-relaxed overflow-y-auto h-[500px] max-h-[500px]">
              {rollbackLogs ? (
                <div className="space-y-0.5">
                  {rollbackLogs.split('\n').map((line, index) => {
                    const segments = parseAnsi(line);
                    return (
                      <div
                        key={index}
                        className="px-2 py-0.5 rounded whitespace-pre-wrap break-all"
                      >
                        {segments.map((segment, segIndex) => (
                          <span key={segIndex} style={segmentToStyle(segment)}>
                            {segment.text}
                          </span>
                        ))}
                      </div>
                    );
                  })}
                  <div ref={rollbackLogsEndRef} />
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-[#8b8b8b]">
                  <div className="text-center">
                    <p>Initializing rollback...</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setRollbackDialogOpen(false)}
              disabled={switching !== null}
            >
              {switching ? "Rolling back..." : "Close"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </DialogComponent>
    </div>
  );
}
