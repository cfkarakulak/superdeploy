"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";
import { GitBranch, GitCommit, Calendar, User, CheckCircle2, RotateCcw } from "lucide-react";

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

  const handleSwitch = async (gitSha: string) => {
    if (!confirm(`Switch to version ${gitSha.substring(0, 7)}?\n\nThis will:\n- Pull Docker image with this Git SHA\n- Deploy with zero-downtime\n- Auto-rollback if health check fails`)) {
      return;
    }

    setSwitching(gitSha);
    try {
      const response = await fetch(
        `http://localhost:8401/api/apps/${projectName}/${appName}/switch`,
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

  return (
    <div>
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumb={{
            label: "Deploy",
            href: `/project/${projectName}/app/${appName}`
          }}
          title="Deployment History"
        />

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
          <div className="space-y-3">
            {releases.map((release, index) => (
              <div
                key={index}
                className="bg-[#f7f7f7] rounded-lg p-5 border border-[#e3e8ee] hover:border-[#cbd5e1] transition-all"
              >
                {/* Header Row */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span className="text-[14px] font-semibold text-green-600">
                      {release.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <code className="text-[13px] bg-[#e3e8ee] px-3 py-1 rounded font-mono text-[#0a0a0a]">
                      v{release.version}
                    </code>
                    {index > 0 && (
                      <button
                        onClick={() => handleSwitch(release.git_sha)}
                        disabled={switching !== null}
                        className="flex items-center gap-1 text-[11px] px-3 py-1 rounded bg-blue-500 text-white hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Switch to this version"
                      >
                        <RotateCcw className="w-3 h-3" />
                        {switching === release.git_sha ? "Switching..." : "Switch"}
                      </button>
                    )}
                  </div>
                </div>

                {/* Details Grid */}
                <div className="space-y-3">
                  {/* Commit Message */}
                  {release.commit_message && release.commit_message !== "-" && (
                    <div className="bg-white p-3 rounded border border-[#e3e8ee]">
                      <p className="text-[13px] text-[#0a0a0a] line-clamp-2">
                        {release.commit_message}
                      </p>
                    </div>
                  )}

                  {/* Git SHA - Full version with copy */}
                  <div className="flex items-start gap-2">
                    <GitCommit className="w-4 h-4 text-[#8b8b8b] mt-1" />
                    <div className="flex-1">
                      <span className="text-[11px] text-[#8b8b8b] block mb-1">Git SHA</span>
                      <div className="flex items-center gap-2">
                        <code className="text-[13px] font-mono text-[#0a0a0a] bg-white px-2 py-1 rounded border border-[#e3e8ee]">
                          {release.git_sha}
                        </code>
                        <button
                          onClick={() => navigator.clipboard.writeText(release.git_sha)}
                          className="text-[11px] text-[#8b8b8b] hover:text-[#0a0a0a] transition-colors px-2 py-1 rounded hover:bg-[#f7f7f7]"
                          title="Copy SHA"
                        >
                          Copy
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Branch */}
                    <div className="flex items-center gap-2">
                      <GitBranch className="w-4 h-4 text-[#8b8b8b]" />
                      <div className="flex flex-col">
                        <span className="text-[11px] text-[#8b8b8b]">Branch</span>
                        <span className="text-[13px] text-[#0a0a0a] font-medium">{release.branch}</span>
                      </div>
                    </div>

                    {/* Deployed By */}
                    <div className="flex items-center gap-2">
                      <User className="w-4 h-4 text-[#8b8b8b]" />
                      <div className="flex flex-col">
                        <span className="text-[11px] text-[#8b8b8b]">Deployed By</span>
                        <span className="text-[13px] text-[#0a0a0a]">{release.deployed_by}</span>
                      </div>
                    </div>

                    {/* Deployed At */}
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-[#8b8b8b]" />
                      <div className="flex flex-col">
                        <span className="text-[11px] text-[#8b8b8b]">Deployed At</span>
                        <span className="text-[13px] text-[#0a0a0a]">{formatDate(release.deployed_at)}</span>
                      </div>
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
