"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  ChevronRight, 
  Check, 
  Settings, 
  Code, 
  Package, 
  Key,
  Eye,
  Search,
  Database,
  Zap,
  Server,
  MessageSquare,
  Plus,
  X,
  Loader2
} from "lucide-react";

interface ProjectConfig {
  project_name: string;
  gcp_project: string;
  gcp_region: string;
  apps: Array<{
    name: string;
    repo: string;
    port: number;
  }>;
  addons: {
    databases: string[];
    queues: string[];
    proxy: string[];
    caches: string[];
  };
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
  apps: [],
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

const GCP_REGIONS = [
  "us-central1",
  "us-east1",
  "us-west1",
  "europe-west1",
  "europe-west2",
  "asia-east1",
  "asia-northeast1",
];

const AVAILABLE_ADDONS = {
  databases: [
    { id: "postgres", name: "PostgreSQL", icon: Database },
    { id: "mysql", name: "MySQL", icon: Database },
    { id: "mongodb", name: "MongoDB", icon: Database },
  ],
  caches: [
    { id: "redis", name: "Redis", icon: Zap },
  ],
  queues: [
    { id: "rabbitmq", name: "RabbitMQ", icon: MessageSquare },
  ],
  proxy: [
    { id: "caddy", name: "Caddy", icon: Server },
  ],
};

interface GroupedRepos {
  [org: string]: Array<{ full_name: string; name: string; owner: string }>;
}

export default function NewProjectSetup() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState<ProjectConfig>(INITIAL_CONFIG);
  const [deploying, setDeploying] = useState(false);
  const [deploymentLog, setDeploymentLog] = useState<string[]>([]);
  const [githubRepos, setGithubRepos] = useState<GroupedRepos>({});
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  const totalSteps = 4;

  // Fetch GitHub repos
  useEffect(() => {
    const fetchRepos = async () => {
      setLoadingRepos(true);
      try {
        const tokenResponse = await fetch("http://localhost:8401/api/settings/github-token");
        if (!tokenResponse.ok) {
          setLoadingRepos(false);
          return;
        }
        
        const { token, configured } = await tokenResponse.json();
        if (!configured || !token) {
          setLoadingRepos(false);
          return;
        }
        
        const response = await fetch("https://api.github.com/user/repos?per_page=100&sort=updated", {
          headers: { Authorization: `token ${token}` }
        });
        
        if (response.ok) {
          const repos = await response.json();
          const repoList = repos.map((r: any) => ({
            full_name: r.full_name,
            name: r.name,
            owner: r.owner.login,
            owner_type: r.owner.type
          }));
          
          // Group by organization
          const grouped: GroupedRepos = {};
          const orgNames = new Set<string>();
          
          repoList.forEach((repo: any) => {
            if (repo.owner_type === "Organization") {
              orgNames.add(repo.owner);
            }
          });
          
          const sortedOrgs = Array.from(orgNames).sort((a, b) => a.localeCompare(b));
          
          sortedOrgs.forEach(orgName => {
            grouped[orgName] = repoList
              .filter((r: any) => r.owner === orgName && r.owner_type === "Organization")
              .sort((a: any, b: any) => a.name.localeCompare(b.name));
          });
          
          const personal = repoList
            .filter((r: any) => r.owner_type === "User")
            .sort((a: any, b: any) => a.name.localeCompare(b.name));
          
          if (personal.length > 0) {
            grouped['Personal'] = personal;
          }
          
          setGithubRepos(grouped);
        }
      } catch (error) {
        console.error("Failed to fetch repos:", error);
      } finally {
        setLoadingRepos(false);
      }
    };
    
    fetchRepos();
  }, []);

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
      setDeploymentLog((prev) => [...prev, "💾 Saving configuration..."]);
      
      const github_org = config.apps.length > 0 && config.apps[0].repo 
        ? config.apps[0].repo.split('/')[0] 
        : "";
      
      const payload = {
        project_name: config.project_name,
        gcp_project: config.gcp_project,
        gcp_region: config.gcp_region,
        github_org,
        apps: config.apps,
        addons: config.addons,
        secrets: config.secrets
      };

      const createResponse = await fetch("http://localhost:8401/api/projects/wizard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!createResponse.ok) {
        const error = await createResponse.json();
        throw new Error(error.detail || "Failed to save configuration");
      }

      const project = await createResponse.json();
      setDeploymentLog((prev) => [...prev, `✓ Project "${project.name}" saved`]);
      setDeploymentLog((prev) => [...prev, "🚀 Starting deployment..."]);
      
      const deployResponse = await fetch(`http://localhost:8401/api/projects/${config.project_name}/deploy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!deployResponse.ok) {
        throw new Error("Failed to start deployment");
      }

      const reader = deployResponse.body?.getReader();
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const text = new TextDecoder().decode(value);
          const lines = text.split('\n').filter(line => line.trim());
          
          lines.forEach(line => {
            if (line.startsWith('data: ')) {
              const message = line.substring(6);
              setDeploymentLog((prev) => [...prev, message]);
            }
          });
        }
      }

      setDeploymentLog((prev) => [...prev, "✓ Deployment complete!"]);
      
      setTimeout(() => {
        router.push(`/project/${config.project_name}`);
      }, 2000);

    } catch (error) {
      setDeploymentLog((prev) => [...prev, `❌ Error: ${error instanceof Error ? error.message : "Unknown error"}`]);
      setDeploying(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1:
        return config.project_name && config.gcp_project && config.gcp_region;
      case 2:
        return config.apps.length > 0 && config.apps.every(app => app.name && app.repo && app.port);
      case 3:
        return true; // Optional
      case 4:
        return config.secrets.docker_org && config.secrets.docker_username && config.secrets.docker_token;
      default:
        return false;
    }
  };

  const filteredRepos = Object.entries(githubRepos).reduce((acc, [org, repos]) => {
    if (!repoSearch) {
      acc[org] = repos;
    } else {
      const filtered = repos.filter(repo => 
        repo.full_name.toLowerCase().includes(repoSearch.toLowerCase())
      );
      if (filtered.length > 0) {
        acc[org] = filtered;
      }
    }
    return acc;
  }, {} as GroupedRepos);

  const addApp = () => {
    setConfig({
      ...config,
      apps: [...config.apps, { name: "", repo: "", port: 8000 }]
    });
  };

  const removeApp = (index: number) => {
    setConfig({
      ...config,
      apps: config.apps.filter((_, i) => i !== index)
    });
  };

  const updateApp = (index: number, updates: Partial<typeof config.apps[0]>) => {
    const newApps = [...config.apps];
    newApps[index] = { ...newApps[index], ...updates };
    setConfig({ ...config, apps: newApps });
  };

  const toggleAddon = (category: keyof typeof config.addons, addonId: string) => {
    const currentAddons = config.addons[category];
    const newAddons = currentAddons.includes(addonId)
      ? currentAddons.filter(id => id !== addonId)
      : [...currentAddons, addonId];
    
    setConfig({
      ...config,
      addons: { ...config.addons, [category]: newAddons }
    });
  };

  // Deploying screen
  if (deploying) {
    return (
      <div className="min-h-screen bg-[#f6f8fa] flex items-center justify-center p-8">
        <div className="w-full max-w-2xl">
          <div className="bg-white rounded-lg border border-[#e3e8ee] p-8">
            <div className="flex items-center gap-3 mb-6">
              <Loader2 className="w-6 h-6 text-[#0a0a0a] animate-spin" />
              <h2 className="text-[20px] font-semibold text-[#0a0a0a]">
                Deploying {config.project_name}
              </h2>
            </div>
            
            <div className="bg-[#0a0a0a] rounded-lg p-4 font-mono text-[12px] text-green-400 max-h-[400px] overflow-y-auto">
              {deploymentLog.map((log, i) => (
                <div key={i} className="mb-1">{log}</div>
              ))}
              <div className="animate-pulse">▊</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f6f8fa]">
      {/* Header */}
      <div className="border-b border-[#e3e8ee] bg-white">
        <div className="max-w-4xl mx-auto px-8 py-6">
          <h1 className="text-[24px] font-semibold text-[#0a0a0a] mb-2">Create New Project</h1>
          <p className="text-[14px] text-[#8b8b8b]">Deploy your applications to GCP with a few clicks</p>
        </div>
      </div>

      {/* Progress */}
      <div className="border-b border-[#e3e8ee] bg-white">
        <div className="max-w-4xl mx-auto px-8 py-4">
          <div className="flex items-center justify-between">
            {[
              { num: 1, name: "Project", icon: Settings },
              { num: 2, name: "Apps", icon: Code },
              { num: 3, name: "Add-ons", icon: Package },
              { num: 4, name: "Secrets", icon: Key }
            ].map((s, i) => (
              <div key={s.num} className="flex items-center flex-1">
                <div className="flex items-center gap-2">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors ${
                    step > s.num ? "bg-[#0a0a0a] border-[#0a0a0a]" :
                    step === s.num ? "border-[#0a0a0a] bg-white" :
                    "border-[#e3e8ee] bg-white"
                  }`}>
                    {step > s.num ? (
                      <Check className="w-4 h-4 text-white" />
                    ) : (
                      <s.icon className={`w-4 h-4 ${step === s.num ? "text-[#0a0a0a]" : "text-[#8b8b8b]"}`} />
                    )}
                  </div>
                  <span className={`text-[13px] font-medium ${step === s.num ? "text-[#0a0a0a]" : "text-[#8b8b8b]"}`}>
                    {s.name}
                  </span>
                </div>
                {i < 3 && (
                  <div className={`flex-1 h-[2px] mx-4 ${step > s.num ? "bg-[#0a0a0a]" : "bg-[#e3e8ee]"}`}></div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-8 py-8">
        <div className="bg-white rounded-lg border border-[#e3e8ee] p-8">
          {/* Step 1: Project Info */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-[18px] font-semibold text-[#0a0a0a] mb-1">Project Information</h2>
                <p className="text-[13px] text-[#8b8b8b]">Basic configuration for your deployment</p>
              </div>

              <div>
                <label className="block text-[13px] font-medium text-[#0a0a0a] mb-2">
                  Project Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={config.project_name}
                  onChange={(e) => updateConfig({ project_name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                  placeholder="myproject"
                  className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[14px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                />
                <p className="text-[11px] text-[#8b8b8b] mt-1.5">Lowercase letters, numbers, and hyphens only</p>
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
                  className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[14px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                />
              </div>

              <div>
                <label className="block text-[13px] font-medium text-[#0a0a0a] mb-2">
                  GCP Region <span className="text-red-500">*</span>
                </label>
                <select
                  value={config.gcp_region}
                  onChange={(e) => updateConfig({ gcp_region: e.target.value })}
                  className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[14px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                >
                  {GCP_REGIONS.map(region => (
                    <option key={region} value={region}>{region}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Step 2: Apps */}
          {step === 2 && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-[18px] font-semibold text-[#0a0a0a] mb-1">Applications</h2>
                  <p className="text-[13px] text-[#8b8b8b]">Add your GitHub repositories to deploy</p>
                </div>
                <button
                  onClick={addApp}
                  className="px-3 py-1.5 text-[13px] font-medium text-[#0a0a0a] border border-[#e3e8ee] rounded hover:bg-[#f6f8fa] transition-colors flex items-center gap-1.5"
                >
                  <Plus className="w-4 h-4" />
                  Add App
                </button>
              </div>

              {config.apps.length === 0 ? (
                <div className="border border-[#e3e8ee] rounded-lg p-12 text-center">
                  <Code className="w-8 h-8 text-[#8b8b8b] mx-auto mb-3" />
                  <p className="text-[14px] font-medium text-[#0a0a0a] mb-2">No applications added</p>
                  <p className="text-[13px] text-[#8b8b8b] mb-4">Add at least one application to deploy</p>
                  <button
                    onClick={addApp}
                    className="px-4 py-2 text-[13px] font-medium text-white bg-[#0a0a0a] rounded hover:bg-[#2d2d2d] transition-colors"
                  >
                    Add Your First App
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {config.apps.map((app, index) => (
                    <div key={index} className="border border-[#e3e8ee] rounded-lg p-4">
                      <div className="flex items-start justify-between mb-4">
                        <h3 className="text-[14px] font-medium text-[#0a0a0a]">Application {index + 1}</h3>
                        <button
                          onClick={() => removeApp(index)}
                          className="text-[#8b8b8b] hover:text-red-600 transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="space-y-3">
                        <div>
                          <label className="block text-[12px] font-medium text-[#8b8b8b] mb-1.5">
                            App Name
                          </label>
                          <input
                            type="text"
                            value={app.name}
                            onChange={(e) => updateApp(index, { name: e.target.value })}
                            placeholder="api"
                            className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[13px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                          />
                        </div>

                        <div>
                          <label className="block text-[12px] font-medium text-[#8b8b8b] mb-1.5">
                            GitHub Repository
                          </label>
                          {loadingRepos ? (
                            <div className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[13px] text-[#8b8b8b]">
                              Loading repositories...
                            </div>
                          ) : (
                            <>
                              <div className="relative mb-2">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b8b8b]" />
                                <input
                                  type="text"
                                  value={repoSearch}
                                  onChange={(e) => setRepoSearch(e.target.value)}
                                  placeholder="Search repositories..."
                                  className="w-full pl-9 pr-3 py-2 border border-[#e3e8ee] rounded text-[13px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                                />
                              </div>
                              <div className="max-h-[200px] overflow-y-auto border border-[#e3e8ee] rounded">
                                {Object.entries(filteredRepos).map(([org, repos]) => (
                                  <div key={org}>
                                    <div className="px-3 py-1.5 bg-[#f6f8fa] text-[11px] font-medium text-[#8b8b8b] uppercase sticky top-0">
                                      {org}
                                    </div>
                                    {repos.map(repo => (
                                      <button
                                        key={repo.full_name}
                                        onClick={() => updateApp(index, { repo: repo.full_name })}
                                        className={`w-full text-left px-3 py-2 text-[13px] hover:bg-[#f6f8fa] transition-colors ${
                                          app.repo === repo.full_name ? "bg-blue-50 text-blue-600 font-medium" : "text-[#0a0a0a]"
                                        }`}
                                      >
                                        {repo.name}
                                      </button>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            </>
                          )}
                          {app.repo && (
                            <p className="text-[11px] text-[#8b8b8b] mt-1.5">Selected: {app.repo}</p>
                          )}
                        </div>

                        <div>
                          <label className="block text-[12px] font-medium text-[#8b8b8b] mb-1.5">
                            Port
                          </label>
                          <input
                            type="number"
                            value={app.port}
                            onChange={(e) => updateApp(index, { port: parseInt(e.target.value) || 8000 })}
                            className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[13px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 3: Add-ons */}
          {step === 3 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-[18px] font-semibold text-[#0a0a0a] mb-1">Add-ons</h2>
                <p className="text-[13px] text-[#8b8b8b]">Extend your app with databases and services (optional)</p>
              </div>

              {Object.entries(AVAILABLE_ADDONS).map(([category, addons]) => (
                <div key={category}>
                  <h3 className="text-[13px] font-semibold text-[#0a0a0a] mb-3 capitalize">{category}</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {addons.map(addon => {
                      const Icon = addon.icon;
                      const isSelected = config.addons[category as keyof typeof config.addons].includes(addon.id);
                      
                      return (
                        <button
                          key={addon.id}
                          onClick={() => toggleAddon(category as keyof typeof config.addons, addon.id)}
                          className={`p-4 border-2 rounded-lg transition-all ${
                            isSelected 
                              ? "border-[#0a0a0a] bg-[#f6f8fa]" 
                              : "border-[#e3e8ee] hover:border-[#8b8b8b]"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded ${isSelected ? "bg-[#0a0a0a]" : "bg-[#f6f8fa]"}`}>
                              <Icon className={`w-4 h-4 ${isSelected ? "text-white" : "text-[#8b8b8b]"}`} />
                            </div>
                            <span className={`text-[14px] font-medium ${isSelected ? "text-[#0a0a0a]" : "text-[#8b8b8b]"}`}>
                              {addon.name}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Step 4: Secrets */}
          {step === 4 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-[18px] font-semibold text-[#0a0a0a] mb-1">Secrets</h2>
                <p className="text-[13px] text-[#8b8b8b]">Configure credentials for deployment</p>
              </div>

              <div>
                <h3 className="text-[14px] font-semibold text-[#0a0a0a] mb-3">Docker Registry</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-[12px] font-medium text-[#8b8b8b] mb-1.5">
                      Organization <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={config.secrets.docker_org}
                      onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_org: e.target.value } })}
                      className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[13px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-medium text-[#8b8b8b] mb-1.5">
                      Username <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={config.secrets.docker_username}
                      onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_username: e.target.value } })}
                      className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[13px] focus:outline-none focus:border-[#0a0a0a] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-medium text-[#8b8b8b] mb-1.5">
                      Access Token <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showSecrets.docker ? "text" : "password"}
                        value={config.secrets.docker_token}
                        onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_token: e.target.value } })}
                        className="w-full px-3 py-2 pr-10 border border-[#e3e8ee] rounded text-[13px] focus:outline-none focus:border-[#0a0a0a] transition-colors font-mono"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSecrets({ ...showSecrets, docker: !showSecrets.docker })}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-[#8b8b8b] hover:text-[#0a0a0a]"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-[#e3e8ee]">
                <h3 className="text-[14px] font-semibold text-[#0a0a0a] mb-3">GitHub (Optional)</h3>
                <div>
                  <label className="block text-[12px] font-medium text-[#8b8b8b] mb-1.5">
                    Personal Access Token
                  </label>
                  <div className="relative">
                    <input
                      type={showSecrets.github ? "text" : "password"}
                      value={config.secrets.github_token}
                      onChange={(e) => updateConfig({ secrets: { ...config.secrets, github_token: e.target.value } })}
                      className="w-full px-3 py-2 pr-10 border border-[#e3e8ee] rounded text-[13px] focus:outline-none focus:border-[#0a0a0a] transition-colors font-mono"
                      placeholder="ghp_..."
                    />
                    <button
                      type="button"
                      onClick={() => setShowSecrets({ ...showSecrets, github: !showSecrets.github })}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[#8b8b8b] hover:text-[#0a0a0a]"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-6 mt-6 border-t border-[#e3e8ee]">
            <button
              onClick={handleBack}
              disabled={step === 1}
              className="px-4 py-2 text-[13px] font-medium text-[#8b8b8b] hover:text-[#0a0a0a] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Back
            </button>
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className="px-6 py-2 text-[13px] font-medium text-white bg-[#0a0a0a] rounded hover:bg-[#2d2d2d] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {step === totalSteps ? "Deploy Project" : "Continue"}
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
