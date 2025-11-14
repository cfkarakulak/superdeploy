"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight, ChevronLeft, Package, Settings, Shield, Rocket, CheckCircle2, ChevronDown } from "lucide-react";

interface ProjectConfig {
  // Step 1: Project Info
  project_name: string;
  gcp_project: string;
  gcp_region: string;
  
  // Step 2: Apps
  apps: Array<{
    name: string;
    repo: string; // GitHub repo (owner/repo format)
    port: number;
  }>;
  
  // Step 3: Addons (simplified - just track which are installed)
  addons: {
    databases: string[]; // ["postgres", "mysql"]
    queues: string[]; // ["rabbitmq"]
    proxy: string[]; // ["caddy"]
    caches: string[]; // ["redis"]
  };
  
  // Step 4: Secrets
  secrets: {
    docker_org: string;
    docker_username: string;
    docker_token: string;
    github_token: string;
    smtp_host: string;
    smtp_port: string;
    smtp_user: string;
    smtp_password: string;
  };
}

const INITIAL_CONFIG: ProjectConfig = {
  project_name: "",
  gcp_project: "",
  gcp_region: "us-central1",
  apps: [{ name: "api", repo: "", port: 8000 }],
  addons: {
    databases: [],
    queues: [],
    proxy: [],
    caches: [],
  },
  secrets: {
    docker_org: "",
    docker_username: "",
    docker_token: "",
    github_token: "",
    smtp_host: "",
    smtp_port: "587",
    smtp_user: "",
    smtp_password: "",
  },
};

interface GroupedRepos {
  [org: string]: Array<{ full_name: string; name: string; owner: string }>;
}

export default function NewProjectWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState<ProjectConfig>(INITIAL_CONFIG);
  const [deploying, setDeploying] = useState(false);
  const [deploymentLog, setDeploymentLog] = useState<string[]>([]);
  const [githubRepos, setGithubRepos] = useState<Array<{ full_name: string; name: string; owner: string }>>([]);
  const [groupedRepos, setGroupedRepos] = useState<GroupedRepos>({});
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoSearchTerms, setRepoSearchTerms] = useState<Record<number, string>>({});
  const [repoDropdownOpen, setRepoDropdownOpen] = useState<Record<number, boolean>>({});

  const totalSteps = 5;

  // Fetch GitHub repos on mount (using stored token)
  useEffect(() => {
    const fetchGithubRepos = async () => {
      setLoadingRepos(true);
      try {
        // Get token from backend
        const tokenResponse = await fetch("http://localhost:8401/api/settings/github-token");
        if (!tokenResponse.ok) {
          console.error("No GitHub token configured");
          setLoadingRepos(false);
          return;
        }
        
        const { token, configured } = await tokenResponse.json();
        if (!configured || !token) {
          console.error("GitHub token not configured");
          setLoadingRepos(false);
          return;
        }
        
        // Fetch repos from GitHub
        const response = await fetch("https://api.github.com/user/repos?per_page=100&sort=updated", {
          headers: { Authorization: `token ${token}` }
        });
        
        if (response.ok) {
          const repos = await response.json();
          const repoList = repos.map((r: any) => ({
            full_name: r.full_name,
            name: r.name,
            owner: r.owner.login,
            owner_type: r.owner.type // "User" or "Organization"
          }));
          
          setGithubRepos(repoList);
          
          // Group repos by organization
          const grouped: GroupedRepos = {};
          const orgNames = new Set<string>();
          
          // First pass: identify all organizations
          repoList.forEach((repo: any) => {
            if (repo.owner_type === "Organization") {
              orgNames.add(repo.owner);
            }
          });
          
          // Sort org names alphabetically
          const sortedOrgNames = Array.from(orgNames).sort((a, b) => a.localeCompare(b));
          
          // Second pass: group repos by org
          sortedOrgNames.forEach(orgName => {
            grouped[orgName] = repoList
              .filter((r: any) => r.owner === orgName && r.owner_type === "Organization")
              .sort((a: any, b: any) => a.name.localeCompare(b.name));
          });
          
          // Personal repos (User type) - alphabetically sorted, at the end
          const personal = repoList
            .filter((r: any) => r.owner_type === "User")
            .sort((a: any, b: any) => a.name.localeCompare(b.name));
          
          if (personal.length > 0) {
            grouped['Personal'] = personal;
          }
          
          setGroupedRepos(grouped);
        }
      } catch (error) {
        console.error("Failed to fetch GitHub repos:", error);
      } finally {
        setLoadingRepos(false);
      }
    };
    
    fetchGithubRepos();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const openDropdowns = Object.keys(repoDropdownOpen).filter(key => repoDropdownOpen[Number(key)]);
      if (openDropdowns.length > 0) {
        const target = event.target as HTMLElement;
        if (!target.closest('.repo-dropdown-container')) {
          setRepoDropdownOpen({});
          setRepoSearchTerms({});
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [repoDropdownOpen]);

  const updateConfig = (updates: Partial<ProjectConfig>) => {
    setConfig({ ...config, ...updates });
  };

  const handleNext = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      handleDeploy();
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleDeploy = async () => {
    setDeploying(true);
    setDeploymentLog([]);

    try {
      // Step 1: Save project configuration to database
      setDeploymentLog((prev) => [...prev, "💾 Saving project configuration to database..."]);
      
      // Extract github_org from first app's repo
      const github_org = config.apps.length > 0 && config.apps[0].repo 
        ? config.apps[0].repo.split('/')[0] 
        : "";
      
      const wizardPayload = {
        project_name: config.project_name,
        gcp_project: config.gcp_project,
        gcp_region: config.gcp_region,
        github_org: github_org,
        apps: config.apps.map(app => ({
          name: app.name,
          repo: app.repo,
          port: app.port
        })),
        addons: config.addons,
        secrets: config.secrets
      };

      const createResponse = await fetch("http://localhost:8401/api/projects/wizard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(wizardPayload),
      });

      if (!createResponse.ok) {
        const error = await createResponse.json();
        throw new Error(error.detail || "Failed to save project configuration");
      }

      const project = await createResponse.json();
      setDeploymentLog((prev) => [...prev, `✓ Project "${project.name}" saved to database`]);

      // Step 2: Deploy from database
      setDeploymentLog((prev) => [...prev, "🚀 Starting deployment (this may take 10-15 minutes)..."]);
      
      const deployResponse = await fetch(`http://localhost:8401/api/projects/${config.project_name}/deploy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!deployResponse.ok) {
        throw new Error("Failed to start deployment");
      }

      // Read streaming deployment logs
      const reader = deployResponse.body?.getReader();
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const text = new TextDecoder().decode(value);
          const lines = text.split("\n").filter(l => l.trim());
          
          for (const line of lines) {
            try {
              const msg = JSON.parse(line);
              setDeploymentLog((prev) => [...prev, msg.message]);
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }

      setDeploymentLog((prev) => [...prev, "✅ Deployment complete!"]);

      // Redirect to project page after 2 seconds
      setTimeout(() => {
        router.push(`/project/${config.project_name}`);
      }, 2000);

    } catch (error) {
      setDeploymentLog((prev) => [...prev, `❌ Error: ${error}`]);
      setDeploying(false);
    }
  };

  const addApp = () => {
    updateConfig({
      apps: [...config.apps, { name: "", repo: "", port: 8000 }],
    });
  };

  const removeApp = (index: number) => {
    updateConfig({
      apps: config.apps.filter((_, i) => i !== index),
    });
  };

  const updateApp = (index: number, field: keyof ProjectConfig["apps"][0], value: any) => {
    const newApps = [...config.apps];
    newApps[index] = { ...newApps[index], [field]: value };
    updateConfig({ apps: newApps });
  };

  const stepNames = ["Project", "Apps", "Add-ons", "Secrets", "Deploy"];

  const renderStepIndicator = () => (
    <div className="flex items-center justify-center gap-4 mb-10">
      {[1, 2, 3, 4, 5].map((s) => (
        <div
          key={s}
          className={`flex flex-col items-center ${s !== 5 ? "gap-3" : ""}`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-medium ${
                s === step
                  ? "bg-[#0a0a0a] text-white"
                  : s < step
                  ? "bg-[#0a0a0a] text-white"
                  : "bg-[#e6e9f0] text-[#8b8b8b]"
              }`}
            >
              {s < step ? <CheckCircle2 className="w-4 h-4" /> : s}
            </div>
            {s !== 5 && (
              <div
                className={`w-16 h-0.5 ${
                  s < step ? "bg-[#0a0a0a]" : "bg-[#e6e9f0]"
                }`}
              />
            )}
          </div>
          <span className={`text-[11px] font-light tracking-[0.03em] ${
            s === step ? "text-[#0a0a0a]" : "text-[#8b8b8b]"
          }`}>
            {stepNames[s - 1]}
          </span>
        </div>
      ))}
    </div>
  );

  // Filter repos based on search (for specific app index)
  const getFilteredGroupedRepos = (appIndex: number) => {
    const searchTerm = repoSearchTerms[appIndex] || "";
    return Object.entries(groupedRepos).reduce((acc, [org, repos]) => {
      const filtered = repos.filter(repo => 
        repo.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        repo.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      if (filtered.length > 0) {
        acc[org] = filtered;
      }
      return acc;
    }, {} as GroupedRepos);
  };

  const renderStep1 = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-[#f7f7f7] flex items-center justify-center">
          <Settings className="w-5 h-5 text-[#8b8b8b]" />
        </div>
        <div>
          <h2 className="text-[19px] font-semibold text-[#0a0a0a]">Project Information</h2>
          <p className="text-[13px] text-[#69707e]">Basic project configuration</p>
        </div>
      </div>

      <div>
        <label className="block text-[13px] font-medium text-[#0a0a0a] mb-2">
          Project Name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={config.project_name}
          onChange={(e) => updateConfig({ project_name: e.target.value })}
          placeholder="myproject"
          className="w-full px-4 py-2.5 border border-[#e6e9f0] rounded-[10px] text-[14px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a] focus:border-transparent"
        />
        <p className="text-[11px] text-[#8b8b8b] mt-1">Lowercase, no spaces (e.g., myproject, webapp, api-backend)</p>
      </div>

      <div>
        <label className="block text-[13px] font-medium text-[#0a0a0a] mb-2">
          GCP Project ID <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={config.gcp_project}
          onChange={(e) => updateConfig({ gcp_project: e.target.value })}
          placeholder="my-gcp-project-123"
          className="w-full px-4 py-2.5 border border-[#e6e9f0] rounded-[10px] text-[14px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a] focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-[13px] font-medium text-[#0a0a0a] mb-2">
          GCP Region <span className="text-red-500">*</span>
        </label>
        <select
          value={config.gcp_region}
          onChange={(e) => updateConfig({ gcp_region: e.target.value })}
          className="w-full px-4 py-2.5 border border-[#e6e9f0] rounded-[10px] text-[14px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a] focus:border-transparent"
        >
          <option value="us-central1">us-central1 (Iowa)</option>
          <option value="us-east1">us-east1 (South Carolina)</option>
          <option value="us-west1">us-west1 (Oregon)</option>
          <option value="europe-west1">europe-west1 (Belgium)</option>
          <option value="asia-east1">asia-east1 (Taiwan)</option>
        </select>
      </div>

    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-[#f7f7f7] flex items-center justify-center">
          <Package className="w-5 h-5 text-[#8b8b8b]" />
        </div>
        <div>
          <h2 className="text-[19px] font-semibold text-[#0a0a0a]">Applications</h2>
          <p className="text-[13px] text-[#69707e]">Define your applications to deploy</p>
        </div>
      </div>

      {config.apps.map((app, index) => (
        <div key={index} className="p-4 border border-[#e6e9f0] rounded-[10px] space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-[13px] font-medium text-[#0a0a0a]">Application {index + 1}</span>
            {config.apps.length > 1 && (
              <button
                onClick={() => removeApp(index)}
                className="text-[11px] text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            )}
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">
              App Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={app.name}
              onChange={(e) => updateApp(index, "name", e.target.value)}
              placeholder="api"
              className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a] focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">
              GitHub Repository <span className="text-red-500">*</span>
            </label>
            {loadingRepos ? (
              <div className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] text-[#8b8b8b] bg-[#f7f7f7]">
                Loading repositories...
              </div>
            ) : githubRepos.length > 0 ? (
              <div className="relative repo-dropdown-container">
                <button
                  type="button"
                  onClick={() => setRepoDropdownOpen({ ...repoDropdownOpen, [index]: !repoDropdownOpen[index] })}
                  className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a] focus:border-transparent text-left flex items-center justify-between"
                >
                  <span className={app.repo ? "text-[#0a0a0a]" : "text-[#8b8b8b]"}>
                    {app.repo || "Select a repository..."}
                  </span>
                  <ChevronDown className={`w-4 h-4 text-[#8b8b8b] transition-transform ${repoDropdownOpen[index] ? "rotate-180" : ""}`} />
                </button>
                
                {repoDropdownOpen[index] && (
                  <div className="absolute z-50 w-full mt-2 bg-white border border-[#e6e9f0] rounded-[8px] shadow-lg max-h-[400px] overflow-hidden">
                    {/* Search */}
                    <div className="p-2 border-b border-[#e6e9f0]">
                      <input
                        type="text"
                        value={repoSearchTerms[index] || ""}
                        onChange={(e) => setRepoSearchTerms({ ...repoSearchTerms, [index]: e.target.value })}
                        placeholder="Search repositories..."
                        className="w-full px-2 py-1.5 border border-[#e6e9f0] rounded-md text-[12px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                    
                    {/* Grouped Repos */}
                    <div className="overflow-y-auto max-h-[320px]">
                      {Object.entries(getFilteredGroupedRepos(index)).map(([org, repos]) => (
                        <div key={org} className="border-b border-[#e6e9f0] last:border-0">
                          <div className="px-3 py-1.5 bg-[#f7f7f7] text-[10px] font-semibold text-[#8b8b8b] uppercase tracking-wide">
                            {org} ({repos.length})
                          </div>
                          {repos.map((repo) => (
                            <button
                              key={repo.full_name}
                              type="button"
                              onClick={() => {
                                updateApp(index, "repo", repo.full_name);
                                setRepoDropdownOpen({ ...repoDropdownOpen, [index]: false });
                                setRepoSearchTerms({ ...repoSearchTerms, [index]: "" });
                              }}
                              className={`w-full px-3 py-2 text-left hover:bg-[#f7f7f7] transition-colors ${
                                app.repo === repo.full_name ? "bg-[#f0f0f0]" : ""
                              }`}
                            >
                              <div className="text-[12px] text-[#0a0a0a] font-medium">{repo.name}</div>
                              <div className="text-[10px] text-[#8b8b8b]">{repo.full_name}</div>
                            </button>
                          ))}
                        </div>
                      ))}
                      
                      {Object.keys(getFilteredGroupedRepos(index)).length === 0 && (
                        <div className="px-3 py-6 text-center text-[12px] text-[#8b8b8b]">
                          No repositories found
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] text-red-500 bg-[#fff5f5]">
                No repositories found. Configure GitHub token in settings.
              </div>
            )}
            <p className="text-[10px] text-[#8b8b8b] mt-1">
              {githubRepos.length > 0 ? `${githubRepos.length} repositories available` : ""}
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">
              Port <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              value={app.port}
              onChange={(e) => updateApp(index, "port", parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a] focus:border-transparent"
            />
          </div>
        </div>
      ))}

      <button
        onClick={addApp}
        className="w-full py-2.5 border-2 border-dashed border-[#e6e9f0] rounded-[10px] text-[13px] text-[#0a0a0a] font-medium hover:border-[#0a0a0a] transition-colors"
      >
        + Add Another App
      </button>
    </div>
  );

  const availableAddons = {
    databases: [
      { id: "postgres", name: "PostgreSQL", description: "Powerful open-source relational database", version: "15-alpine" },
      { id: "mysql", name: "MySQL", description: "Popular open-source relational database", version: "8-alpine" },
      { id: "mongodb", name: "MongoDB", description: "Document-oriented NoSQL database", version: "7" },
    ],
    queues: [
      { id: "rabbitmq", name: "RabbitMQ", description: "Open-source message broker", version: "3.12" },
    ],
    proxy: [
      { id: "caddy", name: "Caddy", description: "Automatic HTTPS reverse proxy", version: "2-alpine" },
      { id: "nginx", name: "Nginx", description: "High-performance web server", version: "alpine" },
    ],
    caches: [
      { id: "redis", name: "Redis", description: "In-memory data structure store", version: "7-alpine" },
      { id: "memcached", name: "Memcached", description: "High-performance distributed memory cache", version: "alpine" },
    ],
  };

  const toggleAddon = (category: 'databases' | 'queues' | 'proxy' | 'caches', addonId: string) => {
    const currentAddons = config.addons[category];
    const isInstalled = currentAddons.includes(addonId);
    
    updateConfig({
      addons: {
        ...config.addons,
        [category]: isInstalled 
          ? currentAddons.filter(id => id !== addonId)
          : [...currentAddons, addonId]
      }
    });
  };

  const renderAddonCard = (
    addon: { id: string; name: string; description: string; version: string },
    category: 'databases' | 'queues' | 'proxy' | 'caches'
  ) => {
    const isInstalled = config.addons[category].includes(addon.id);
    
    return (
      <div 
        key={addon.id}
        className={`p-4 border rounded-[10px] transition-all ${
          isInstalled 
            ? "border-[#0a0a0a] bg-[#f7f7f7]" 
            : "border-[#e6e9f0] hover:border-[#d0d0d0]"
        }`}
      >
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            <h4 className="text-[14px] font-semibold text-[#0a0a0a] mb-1">{addon.name}</h4>
            <p className="text-[11px] text-[#69707e] mb-2">{addon.description}</p>
            <span className="text-[10px] text-[#8b8b8b] font-mono">v{addon.version}</span>
          </div>
          <button
            onClick={() => toggleAddon(category, addon.id)}
            className={`ml-3 px-3 py-1.5 rounded-md text-[11px] font-medium transition-colors ${
              isInstalled
                ? "bg-[#0a0a0a] text-white hover:bg-[#2a2a2a]"
                : "border border-[#e6e9f0] text-[#0a0a0a] hover:bg-[#f7f7f7]"
            }`}
          >
            {isInstalled ? "Installed" : "Install"}
          </button>
        </div>
      </div>
    );
  };

  const renderStep3 = () => (
    <div className="space-y-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-[#f7f7f7] flex items-center justify-center">
          <Settings className="w-5 h-5 text-[#8b8b8b]" />
        </div>
        <div>
          <h2 className="text-[19px] font-semibold text-[#0a0a0a]">Infrastructure Add-ons</h2>
          <p className="text-[13px] text-[#69707e]">Click to install or uninstall add-ons</p>
        </div>
      </div>

      {/* Databases */}
      <div>
        <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3">Databases</h3>
        <div className="grid grid-cols-1 gap-3">
          {availableAddons.databases.map(addon => renderAddonCard(addon, "databases"))}
        </div>
      </div>

      {/* Message Queues */}
      <div>
        <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3">Message Queues</h3>
        <div className="grid grid-cols-1 gap-3">
          {availableAddons.queues.map(addon => renderAddonCard(addon, "queues"))}
        </div>
      </div>

      {/* Reverse Proxy */}
      <div>
        <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3">Reverse Proxy</h3>
        <div className="grid grid-cols-1 gap-3">
          {availableAddons.proxy.map(addon => renderAddonCard(addon, "proxy"))}
        </div>
      </div>

      {/* Cache */}
      <div>
        <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3">Cache</h3>
        <div className="grid grid-cols-1 gap-3">
          {availableAddons.caches.map(addon => renderAddonCard(addon, "caches"))}
        </div>
      </div>
    </div>
  );

  const renderStep4 = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-[#f7f7f7] flex items-center justify-center">
          <Shield className="w-5 h-5 text-[#8b8b8b]" />
        </div>
        <div>
          <h2 className="text-[19px] font-semibold text-[#0a0a0a]">Secrets & Credentials</h2>
          <p className="text-[13px] text-[#69707e]">Required for deployment</p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="p-4 border border-[#e6e9f0] rounded-[10px]">
          <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3">Docker Hub Credentials <span className="text-red-500">*</span></h3>
          
          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">
                Organization <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={config.secrets.docker_org}
                onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_org: e.target.value } })}
                placeholder="myorg"
                className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">
                Username <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={config.secrets.docker_username}
                onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_username: e.target.value } })}
                placeholder="username"
                className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">
                Access Token <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                value={config.secrets.docker_token}
                onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_token: e.target.value } })}
                placeholder="dckr_pat_xxx..."
                className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
              />
            </div>
          </div>
        </div>

        <div className="p-4 border border-[#e6e9f0] rounded-[10px]">
          <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3">GitHub Token <span className="text-red-500">*</span></h3>
          
          <div>
            <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">
              Personal Access Token <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              value={config.secrets.github_token}
              onChange={(e) => updateConfig({ secrets: { ...config.secrets, github_token: e.target.value } })}
              placeholder="ghp_xxx..."
              className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
            />
            <p className="text-[10px] text-[#8b8b8b] mt-1">
              Requires <code className="px-1 py-0.5 bg-white rounded">admin:org</code> scope
            </p>
          </div>
        </div>

        <div className="p-4 border border-[#e6e9f0] rounded-[10px]">
          <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3 flex items-center gap-2">
            <span>SMTP</span>
            <span className="text-[10px] text-[#8b8b8b] font-normal">(Optional)</span>
          </h3>
          
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">Host</label>
                <input
                  type="text"
                  value={config.secrets.smtp_host}
                  onChange={(e) => updateConfig({ secrets: { ...config.secrets, smtp_host: e.target.value } })}
                  placeholder="smtp.gmail.com"
                  className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">Port</label>
                <input
                  type="text"
                  value={config.secrets.smtp_port}
                  onChange={(e) => updateConfig({ secrets: { ...config.secrets, smtp_port: e.target.value } })}
                  placeholder="587"
                  className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">Username</label>
              <input
                type="text"
                value={config.secrets.smtp_user}
                onChange={(e) => updateConfig({ secrets: { ...config.secrets, smtp_user: e.target.value } })}
                placeholder="user@example.com"
                className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#0a0a0a] mb-1">Password</label>
              <input
                type="password"
                value={config.secrets.smtp_password}
                onChange={(e) => updateConfig({ secrets: { ...config.secrets, smtp_password: e.target.value } })}
                placeholder="••••••••"
                className="w-full px-3 py-2 border border-[#e6e9f0] rounded-[8px] text-[13px] focus:outline-none focus:ring-2 focus:ring-[#0a0a0a]"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderStep5 = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-[#f7f7f7] flex items-center justify-center">
          <Rocket className="w-5 h-5 text-[#8b8b8b]" />
        </div>
        <div>
          <h2 className="text-[19px] font-semibold text-[#0a0a0a]">Review & Deploy</h2>
          <p className="text-[13px] text-[#69707e]">Infrastructure deployment will take 10-15 minutes</p>
        </div>
      </div>

      {!deploying && !deploymentLog.length ? (
        <div className="space-y-4">
          <div className="p-4 bg-[#f7f7f7] rounded-[10px]">
            <div className="flex justify-between items-center mb-2">
              <span className="text-[13px] font-medium text-[#0a0a0a]">Project</span>
              <span className="text-[13px] text-[#69707e]">{config.project_name}</span>
            </div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-[13px] font-medium text-[#0a0a0a]">GCP Project</span>
              <span className="text-[13px] text-[#69707e]">{config.gcp_project}</span>
            </div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-[13px] font-medium text-[#0a0a0a]">Region</span>
              <span className="text-[13px] text-[#69707e]">{config.gcp_region}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[13px] font-medium text-[#0a0a0a]">Applications</span>
              <span className="text-[13px] text-[#69707e]">{config.apps.length} app(s)</span>
            </div>
          </div>

          <div className="p-4 border border-[#e6e9f0] rounded-[10px] bg-[#f7f7f7]">
            <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-2">What happens next:</h3>
            <ul className="text-[12px] text-[#69707e] space-y-1 ml-4 list-disc">
              <li>Create project configuration files</li>
              <li>Deploy GCP infrastructure (VMs, networking)</li>
              <li>Install Docker, Node.js, and GitHub runners</li>
              <li>Deploy infrastructure add-ons</li>
              <li>Sync secrets to GitHub</li>
              <li>Generate deployment workflows</li>
            </ul>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-[#0a0a0a] rounded-[10px] font-mono text-[12px] text-green-400 h-96 overflow-y-auto">
          {deploymentLog.map((log, i) => (
            <div key={i} className="mb-1">{log}</div>
          ))}
          {deploying && <div className="animate-pulse">█</div>}
        </div>
      )}
    </div>
  );

  const canProceed = () => {
    switch (step) {
      case 1:
        return config.project_name && config.gcp_project;
      case 2:
        return config.apps.length > 0 && config.apps.every(app => app.name && app.repo && app.port);
      case 3:
        return true; // Addons are optional
      case 4:
        return config.secrets.docker_org && config.secrets.docker_username && 
               config.secrets.docker_token && config.secrets.github_token;
      case 5:
        return true;
      default:
        return false;
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-3xl mx-auto px-8 py-12">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-[24px] font-bold text-[#0a0a0a] mb-2">Create New Project</h1>
          <p className="text-[14px] text-[#69707e]">
            Set up infrastructure, GitHub Actions, and automated deployments
          </p>
        </div>

        {/* Step Indicator */}
        {renderStepIndicator()}

        {/* Step Content */}
        <div className="bg-white rounded-[16px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)] p-8 mb-6">
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4()}
          {step === 5 && renderStep5()}
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <button
            onClick={handleBack}
            disabled={step === 1 || deploying}
            className="flex items-center gap-2 px-4 py-2.5 text-[#69707e] hover:text-[#0a0a0a] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </button>

          {step < totalSteps ? (
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className="flex items-center gap-2 px-6 py-2.5 bg-[#0a0a0a] text-white rounded-[10px] font-medium hover:bg-[#2a2a2a] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleDeploy}
              disabled={!canProceed() || deploying || deploymentLog.length > 0}
              className="flex items-center gap-2 px-6 py-2.5 bg-[#0a0a0a] text-white rounded-[10px] font-medium hover:bg-[#2a2a2a] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Rocket className="w-4 h-4" />
              {deploying ? "Deploying..." : deploymentLog.length > 0 ? "Completed" : "Deploy Infrastructure"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

