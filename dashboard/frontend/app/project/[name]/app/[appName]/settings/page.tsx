"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";

export default function SettingsPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [githubToken, setGithubToken] = useState("");
  const [isConfigured, setIsConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetchGithubToken();
  }, []);

  const fetchGithubToken = async () => {
    try {
      const response = await fetch("http://localhost:8401/api/settings/github-token");
      const data = await response.json();
      if (data.configured && data.token) {
        setGithubToken(data.token);
        setIsConfigured(true);
      }
    } catch (err) {
      console.error("Failed to fetch GitHub token:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!githubToken.trim()) {
      setMessage({ type: "error", text: "Please enter a GitHub token" });
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch("http://localhost:8401/api/settings/github-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: githubToken }),
      });

      if (response.ok) {
        setMessage({ type: "success", text: "GitHub token saved successfully!" });
        setIsConfigured(true);
      } else {
        const error = await response.json();
        setMessage({ type: "error", text: error.detail || "Failed to save token" });
      }
    } catch (err) {
      setMessage({ type: "error", text: "Network error. Please try again." });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete the GitHub token?")) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch("http://localhost:8401/api/settings/github-token", {
        method: "DELETE",
      });

      if (response.ok) {
        setGithubToken("");
        setIsConfigured(false);
        setMessage({ type: "success", text: "GitHub token deleted successfully!" });
      } else {
        const error = await response.json();
        setMessage({ type: "error", text: error.detail || "Failed to delete token" });
      }
    } catch (err) {
      setMessage({ type: "error", text: "Network error. Please try again." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[20px] pt-[25px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumb={{
            label: "Settings",
            href: `/project/${projectName}/app/${appName}/settings`
          }}
          title="Application Settings"
          description="Configure GitHub integration and other application settings"
        />

        {loading ? (
          <div className="py-8">
            <div className="w-full h-[40px] bg-[#e3e8ee] rounded skeleton-animated mb-4" />
            <div className="w-[200px] h-[40px] bg-[#e3e8ee] rounded skeleton-animated" />
          </div>
        ) : (
          <div className="space-y-6 mt-6">
            {/* GitHub Token Section */}
            <div className="border border-[#e3e8ee] rounded-lg p-6">
              <h3 className="text-[18px] font-semibold text-[#0a0a0a] mb-2">GitHub Personal Access Token</h3>
              <p className="text-[14px] text-[#8b8b8b] mb-4">
                Required for GitHub Actions integration. Create a token with <code className="bg-[#f5f5f5] px-1 py-0.5 rounded text-[13px]">repo</code> and <code className="bg-[#f5f5f5] px-1 py-0.5 rounded text-[13px]">actions:read</code> permissions.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-[14px] font-medium text-[#0a0a0a] mb-2">
                    Token
                  </label>
                  <input
                    type="password"
                    value={githubToken}
                    onChange={(e) => setGithubToken(e.target.value)}
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                    className="w-full px-4 py-2 border border-[#e3e8ee] rounded-lg text-[14px] focus:outline-none focus:ring-2 focus:ring-[#0ea5e9] focus:border-transparent"
                    disabled={saving}
                  />
                </div>

                {message && (
                  <div className={`p-3 rounded-lg text-[14px] ${message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                    {message.text}
                  </div>
                )}

                <div className="flex gap-3">
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="px-4 py-2 bg-[#0ea5e9] text-white text-[14px] font-medium rounded-lg hover:bg-[#0284c7] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {saving ? "Saving..." : isConfigured ? "Update Token" : "Save Token"}
                  </button>

                  {isConfigured && (
                    <button
                      onClick={handleDelete}
                      disabled={saving}
                      className="px-4 py-2 bg-red-500 text-white text-[14px] font-medium rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Delete Token
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Future Settings Sections */}
            <div className="border border-[#e3e8ee] rounded-lg p-6 bg-[#fafafa]">
              <h3 className="text-[18px] font-semibold text-[#0a0a0a] mb-2">Additional Settings</h3>
              <p className="text-[14px] text-[#8b8b8b]">
                More configuration options coming soon...
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
