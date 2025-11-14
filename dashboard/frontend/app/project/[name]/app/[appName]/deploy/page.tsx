"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";
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

interface Release {
  version: string;
  git_sha: string;
  deployed_by: string;
  deployed_at: string;
  branch: string;
  commit_message: string;
  status: string;
}

// Skeleton Components
const ReleasesTableSkeleton = () => (
  <div className="space-y-3">
    {Array.from({ length: 3 }, (_, i) => (
      <div key={i} className="bg-[#f7f7f7] rounded-lg p-4 space-y-3 skeleton-animated">
        <div className="flex items-center justify-between">
          <div className="w-[120px] h-[20px] bg-[#e3e8ee] rounded skeleton-animated" />
          <div className="w-[80px] h-[20px] bg-[#e3e8ee] rounded skeleton-animated" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="w-full h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
          <div className="w-full h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
          <div className="w-full h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
          <div className="w-full h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
        </div>
      </div>
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

  const fetchReleases = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `http://localhost:8000/api/apps/${projectName}/${appName}/releases`
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

  const handleSwitch = async (gitSha: string) => {
    if (!confirm(`Switch to version ${gitSha.substring(0, 7)}?\n\nThis will:\n- Pull Docker image with this Git SHA\n- Deploy with zero-downtime\n- Auto-rollback if health check fails`)) {
      return;
    }

    setSwitching(gitSha);
    try {
      const response = await fetch(
        `http://localhost:8000/api/apps/${projectName}/${appName}/switch`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ git_sha: gitSha }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to switch version");
      }

      alert("✅ Successfully switched to version " + gitSha.substring(0, 7));
      // Refresh releases list
      await fetchReleases();
    } catch (err) {
      alert("❌ " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setSwitching(null);
    }
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
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <div className="mb-6">
          <PageHeader
            breadcrumb={{
              label: "Deploy",
              href: `/project/${projectName}/app/${appName}`
            }}
            title="Deployment History"
          />
          <p className="text-[13px] text-[#8b8b8b] mt-2">
            View all deployments and rollback to any previous version with zero downtime
          </p>
        </div>

        {loading ? (
          <ReleasesTableSkeleton />
        ) : error ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">Failed to load releases: {error}</p>
          </div>
        ) : releases.length === 0 ? (
          <div className="text-center py-12 text-[#8b8b8b]">
            <p className="text-[15px]">No deployment history found</p>
            <p className="text-[13px] mt-2">Deploy the app first: <code className="bg-[#f7f7f7] px-2 py-1 rounded">git push origin production</code></p>
          </div>
        ) : (
          <div className="space-y-0">
            {releases.map((release, index) => {
              const isLatest = index === 0;
              const hasTimeline = index < releases.length - 1;
              
              return (
                <div key={index} className="relative">
                  {/* Timeline connector */}
                  {hasTimeline && (
                    <div className="absolute left-[15px] top-[48px] bottom-[-24px] w-[2px] bg-[#e3e8ee]" />
                  )}
                  
                  <div className="relative flex gap-4 pb-6">
                    {/* Timeline dot with status */}
                    <div className="relative z-10 flex-shrink-0">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        isLatest 
                          ? 'bg-green-500 ring-4 ring-green-100' 
                          : 'bg-white border-2 border-[#e3e8ee]'
                      }`}>
                        {isLatest ? (
                          <Activity className="w-4 h-4 text-white" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 text-green-500" />
                        )}
                      </div>
                    </div>

                    {/* Card */}
                    <div className="flex-1 min-w-0">
                      <div className={`bg-white rounded-lg border ${
                        isLatest ? 'border-green-200 shadow-sm' : 'border-[#e3e8ee]'
                      } hover:shadow-md transition-all overflow-hidden`}>
                        
                        {/* Header */}
                        <div className="px-4 py-3 border-b border-[#e3e8ee] flex items-center justify-between gap-4">
                          <div className="flex items-center gap-3 min-w-0 flex-1">
                            {/* Status Badge */}
                            {isLatest && (
                              <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium bg-green-50 text-green-700 border border-green-200 flex-shrink-0">
                                <Activity className="w-3 h-3" />
                                Current
                              </span>
                            )}
                            
                            {/* Version */}
                            <div className="flex items-center gap-2 min-w-0">
                              <Tag className="w-3.5 h-3.5 text-[#8b8b8b] flex-shrink-0" />
                              <code className="text-[13px] font-mono font-medium text-[#0a0a0a]">
                                v{release.version}
                              </code>
                            </div>

                            {/* Relative Time */}
                            <span className="text-[12px] text-[#8b8b8b] flex-shrink-0">
                              {getRelativeTime(release.deployed_at)}
                            </span>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {!isLatest && (
                              <button
                                onClick={() => handleSwitch(release.git_sha)}
                                disabled={switching !== null}
                                className="flex items-center gap-1.5 text-[12px] px-3 py-1.5 rounded-md bg-[#0a0a0a] text-white hover:bg-[#2a2a2a] transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                                title="Rollback to this version"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                {switching === release.git_sha ? "Switching..." : "Rollback"}
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Body */}
                        <div className="px-4 py-4 space-y-4">
                          {/* Commit Message */}
                          {release.commit_message && release.commit_message !== "-" && (
                            <div>
                              <div className="flex items-center gap-2 mb-2">
                                <GitCommit className="w-3.5 h-3.5 text-[#8b8b8b]" />
                                <span className="text-[11px] font-medium text-[#8b8b8b] uppercase tracking-wider">Commit</span>
                              </div>
                              <p className="text-[14px] text-[#0a0a0a] pl-5">
                                {release.commit_message}
                              </p>
                            </div>
                          )}

                          {/* Metadata Grid */}
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-3 border-t border-[#f0f0f0]">
                            {/* Git SHA */}
                            <div>
                              <div className="text-[11px] font-medium text-[#8b8b8b] uppercase tracking-wider mb-1.5">
                                Commit SHA
                              </div>
                              <div className="flex items-center gap-1.5">
                                <code className="text-[12px] font-mono text-[#0a0a0a] bg-[#f7f7f7] px-2 py-1 rounded">
                                  {release.git_sha.substring(0, 7)}
                                </code>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(release.git_sha);
                                    alert('✓ Copied!');
                                  }}
                                  className="text-[11px] text-[#8b8b8b] hover:text-[#0a0a0a] transition-colors"
                                  title="Copy full SHA"
                                >
                                  Copy
                                </button>
                              </div>
                            </div>

                            {/* Branch */}
                            <div>
                              <div className="text-[11px] font-medium text-[#8b8b8b] uppercase tracking-wider mb-1.5">
                                Branch
                              </div>
                              <div className="flex items-center gap-1.5">
                                <GitBranch className="w-3 h-3 text-[#8b8b8b]" />
                                <span className="text-[13px] text-[#0a0a0a] font-medium">
                                  {release.branch}
                                </span>
                              </div>
                            </div>

                            {/* Deployed By */}
                            <div>
                              <div className="text-[11px] font-medium text-[#8b8b8b] uppercase tracking-wider mb-1.5">
                                Deployed By
                              </div>
                              <div className="flex items-center gap-1.5">
                                <User className="w-3 h-3 text-[#8b8b8b]" />
                                <span className="text-[13px] text-[#0a0a0a]">
                                  {release.deployed_by}
                                </span>
                              </div>
                            </div>

                            {/* Timestamp */}
                            <div>
                              <div className="text-[11px] font-medium text-[#8b8b8b] uppercase tracking-wider mb-1.5">
                                Deployed
                              </div>
                              <div className="flex items-center gap-1.5">
                                <Clock className="w-3 h-3 text-[#8b8b8b]" />
                                <span className="text-[13px] text-[#0a0a0a]" title={formatDate(release.deployed_at)}>
                                  {getRelativeTime(release.deployed_at)}
                                </span>
                              </div>
                            </div>
                          </div>
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
    </div>
  );
}
