"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  ChevronRight,
  ChevronLeft,
  ChevronDown,
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
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Button, Input } from "@/components";
import { getAddonLogo } from "@/lib/addonLogos";

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
          console.log("Fetched repos:", repos.length, repos.slice(0, 2));
          
          const repoList = repos.map((r: any) => ({
            full_name: r.full_name,
            name: r.name,
            owner: r.owner.login,
            owner_type: r.owner.type
          }));
          
          console.log("Mapped repos:", repoList.length, repoList.slice(0, 2));
          
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
          
          console.log("Grouped repos:", Object.keys(grouped), grouped);
          setGithubRepos(grouped);
        } else {
          console.error("GitHub API error:", response.status, await response.text());
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
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="w-full max-w-2xl">
          <div className="rounded-lg border border-[#e3e8ee] p-8">
            <div className="flex items-center gap-3 mb-6">
              <Loader2 className="w-5 h-5 text-[#8b8b8b] animate-spin" />
              <h2 className="text-[18px] text-[#222]">
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
    <div className="min-h-screen flex py-12">
      <div className="w-full max-w-4xl">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center w-full gap-6">
            {[
              { num: 1, label: "Configure project\nand infrastructure" },
              { num: 2, label: "Add GitHub\nrepositories" },
              { num: 3, label: "Select optional\nadd-ons" },
              { num: 4, label: "Configure deployment\ncredentials" }
            ].map((s, index) => (
              <React.Fragment key={s.num}>
                <div 
                  className="flex-1 flex items-start gap-3 cursor-pointer"
                  onClick={() => setStep(s.num)}
                >
                  <span className={`text-[21px] font-normal ${step >= s.num ? "text-[#0a0a0a]" : "text-[#c1c1c1]"}`}>
                    {s.num}
                  </span>
                  <p className={`text-[11px] font-light tracking-[0.03em] leading-relaxed whitespace-pre-line ${step >= s.num ? "text-[#0a0a0a]" : "text-[#c1c1c1]"}`}>
                    {s.label}
                  </p>
                </div>
                {index < 3 && (
                  <ChevronRight className="w-4 h-4 text-[#c1c1c1] flex-shrink-0 mt-1" />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Content */}
        <div>
        <div className="bg-white rounded-[16px] p-8 shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          {/* Step 1: Project Info */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-[18px] text-[#0a0a0a] mb-1">Project Information</h2>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Input
                    label={<>Project Name <span className="text-red-500">*</span></>}
                    type="text"
                    value={config.project_name}
                    onChange={(e) => updateConfig({ project_name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                    placeholder="myproject"
                    hint="Lowercase letters, numbers, and hyphens only"
                  />
                </div>
                <div>
                  <Input
                    label={<>Domain <span className="text-red-500">*</span></>}
                    type="text"
                    value={config.domain}
                    onChange={(e) => updateConfig({ domain: e.target.value })}
                    placeholder="example.com"
                    hint="Your application's domain name"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Input
                    label={<>GCP Project ID <span className="text-red-500">*</span></>}
                    type="text"
                    value={config.gcp_project}
                    onChange={(e) => updateConfig({ gcp_project: e.target.value })}
                    placeholder="my-gcp-project-123"
                    hint="Your Google Cloud project identifier"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-[#111] font-light tracking-[0.03em] mb-2">
                    GCP Region <span className="text-red-500">*</span>
                  </label>
                  <DropdownMenu.Root>
                    <DropdownMenu.Trigger className="bg-white user-select-none border border-[#0000001f] shadow-x1 relative flex h-8 w-full items-center justify-between px-2 pr-[22px] py-2 rounded-[10px] cursor-pointer outline-none group">
                      <span className="text-[11px] tracking-[0.03em] font-light text-[#141414] user-select-none">{config.gcp_region}</span>
                      <ChevronRight className="top-[10px] right-[9px] absolute w-3 h-3 text-black transition-transform duration-200 group-data-[state=open]:rotate-90" />
                    </DropdownMenu.Trigger>

                    <DropdownMenu.Portal>
                      <DropdownMenu.Content
                        align="start"
                        className="min-w-[200px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_150ms_ease-out_forwards] distance--8 data-[state=closed]:animate-[slide-fade-out-vertical_150ms_ease-out_forwards]"
                        sideOffset={5}
                      >
                        {GCP_REGIONS.map(region => (
                          <DropdownMenu.Item
                            key={region}
                            onClick={() => updateConfig({ gcp_region: region })}
                            className="flex items-center justify-between px-3 py-2 rounded hover:bg-[#f6f8fa] outline-none cursor-pointer"
                          >
                            <span className="text-[11px] text-[#111] font-light tracking-[0.03em]">{region}</span>
                            {config.gcp_region === region && (
                              <Check className="w-3.5 h-3.5 text-[#374046]" strokeWidth={2.5} />
                            )}
                          </DropdownMenu.Item>
                        ))}
                      </DropdownMenu.Content>
                    </DropdownMenu.Portal>
                  </DropdownMenu.Root>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Apps */}
          {step === 2 && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-[18px] text-[#0a0a0a] mb-1">Applications</h2>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={addApp}
                  icon={<Plus className="w-4 h-4" />}
                >
                  Add App
                </Button>
              </div>

              {config.apps.length === 0 ? (
                <div className="border border-[#e3e8ee] rounded-lg p-12 text-center">
                  <Code className="w-5 h-5 text-[#8b8b8b] mx-auto mb-1" />
                  <p className="text-[11px] tracking-[0.03em] font-light text-[#8b8b8b] mb-3">No applications added</p>
                  <Button
                    variant="primary"
                    onClick={addApp}
                  >
                    Add Your First App
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {config.apps.map((app, index) => (
                    <div key={index} className="border border-[#e3e8ee] rounded-lg p-4">
                      <div className="flex items-start justify-between mb-4">
                        <h3 className="text-[14px] text-[#0a0a0a]">Application {index + 1}</h3>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeApp(index)}
                          icon={<X className="w-4 h-4" />}
                        />
                      </div>

                      <div className="space-y-3">
                        <div>
                          <label className="block text-[11px] text-[#111] font-light tracking-[0.03em] mb-2">
                            GitHub Repository
                          </label>
                          {loadingRepos ? (
                            <div className="w-full px-3 py-2 border border-[#e3e8ee] rounded text-[11px] text-[#8b8b8b] font-light tracking-[0.03em]">
                              Loading repositories...
                            </div>
                          ) : (
                            <DropdownMenu.Root>
                              <DropdownMenu.Trigger className="bg-white w-full border border-[#e3e8ee] rounded-lg px-3 py-2.5 pr-10 text-left text-[14px] text-[#0a0a0a] outline-none focus:border-[#8b8b8b] transition-colors cursor-pointer hover:border-[#8b8b8b] relative group">
                                <span>{app.repo || "Select repository..."}</span>
                                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b8b8b] transition-transform duration-200 group-data-[state=open]:rotate-180" />
                              </DropdownMenu.Trigger>

                              <DropdownMenu.Portal>
                                <DropdownMenu.Content
                                  align="start"
                                  className="w-[400px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-2 animate-[slide-fade-in-vertical_150ms_ease-out_forwards] distance--8 data-[state=closed]:animate-[slide-fade-out-vertical_150ms_ease-out_forwards] z-50"
                                  sideOffset={5}
                                >
                                  <div className="mb-2 px-2">
                                    <div className="relative">
                                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b8b8b]" />
                                      <input
                                        type="text"
                                        value={repoSearch}
                                        onChange={(e) => setRepoSearch(e.target.value)}
                                        placeholder="Search repositories..."
                                        className="w-full pl-9 pr-3 py-2 bg-white border border-[#e3e8ee] rounded-lg text-[11px] outline-none focus:border-[#8b8b8b]"
                                      />
                                    </div>
                                  </div>
                                  <div className="max-h-[300px] overflow-y-auto scrollbar-thin">
                                    {Object.keys(filteredRepos).length === 0 ? (
                                      <div className="px-3 py-4 text-[11px] text-[#8b8b8b] font-light tracking-[0.03em] text-center">
                                        No repositories found
                                      </div>
                                    ) : (
                                      Object.entries(filteredRepos).map(([org, repos]) => (
                                        <div key={org}>
                                          <div className="px-3 py-1.5 text-[11px] font-light text-[#8b8b8b] uppercase tracking-[0.03em]">
                                            {org}
                                          </div>
                                          {repos.map(repo => (
                                            <DropdownMenu.Item
                                              key={repo.full_name}
                                              onClick={() => updateApp(index, { repo: repo.full_name })}
                                              className="flex items-center justify-between px-3 py-2 rounded hover:bg-[#f6f8fa] outline-none cursor-pointer"
                                            >
                                              <span className="text-[11px] text-[#111] font-light tracking-[0.03em]">{repo.name}</span>
                                              {app.repo === repo.full_name && (
                                                <Check className="w-3.5 h-3.5 text-[#374046]" strokeWidth={2.5} />
                                              )}
                                            </DropdownMenu.Item>
                                          ))}
                                        </div>
                                      ))
                                    )}
                                  </div>
                                </DropdownMenu.Content>
                              </DropdownMenu.Portal>
                            </DropdownMenu.Root>
                          )}
                        </div>

                        <div className="grid grid-cols-3 gap-3">
                          <div className="col-span-2">
                            <Input
                              label="App Name"
                              type="text"
                              value={app.name}
                              onChange={(e) => updateApp(index, { name: e.target.value })}
                              placeholder="api"
                              hint="Unique identifier for this application"
                            />
                          </div>
                          <div>
                            <Input
                              label="Port"
                              type="number"
                              value={app.port}
                              onChange={(e) => updateApp(index, { port: parseInt(e.target.value) || 8000 })}
                              placeholder="8000"
                              hint="Application port"
                            />
                          </div>
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
                <h2 className="text-[18px] text-[#0a0a0a] mb-1">Add-ons</h2>
              </div>

              {Object.entries(AVAILABLE_ADDONS).map(([category, addons]) => (
                <div key={category}>
                  <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light capitalize">
                    <Database className="w-4 h-4" />
                    {category}
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {addons.map(addon => {
                      const isSelected = config.addons[category as keyof typeof config.addons].includes(addon.id);
                      const logo = getAddonLogo(addon.id);
                      
                      return (
                        <div
                          key={addon.id}
                          onClick={() => toggleAddon(category as keyof typeof config.addons, addon.id)}
                          className={`p-5 border rounded-lg cursor-pointer ${
                            isSelected 
                              ? "border-[#0a0a0a] bg-[#f6f8fa]" 
                              : "border-[#e3e8ee] hover:border-[#b9c1c6]"
                          }`}
                        >
                          {/* Header */}
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              {logo ? (
                                <div className="w-10 h-10 flex items-center p-2 justify-center bg-white rounded-lg border border-[#e3e8ee] flex-shrink-0">
                                  {logo}
                                </div>
                              ) : (
                                <div className="w-10 h-10 flex items-center justify-center bg-gray-50 rounded-lg border border-[#e3e8ee] flex-shrink-0">
                                  <Package className="w-6 h-6 text-gray-600" />
                                </div>
                              )}
                              <div>
                                <h3 className="text-[13px] text-[#8b8b8b] font-light mb-1">{addon.name}</h3>
                                <div className="flex items-center gap-1.5">
                                  <div className={`w-2 h-2 rounded-full ${isSelected ? 'bg-green-500' : 'bg-gray-300'} flex-shrink-0`}></div>
                                  <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                                    {isSelected ? 'Selected' : 'Available'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Type */}
                          <div className="flex items-baseline gap-1 mb-3">
                            <span className="text-[21px] text-[#0a0a0a] capitalize">
                              {addon.id}
                            </span>
                          </div>

                          {/* Version - Full Width */}
                          <div className="pt-3 border-t border-[#e3e8ee] mb-3">
                            <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Version</p>
                            <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                              {addon.id === 'postgres' && 'latest'}
                              {addon.id === 'redis' && 'latest'}
                              {addon.id === 'rabbitmq' && 'latest'}
                              {addon.id === 'mongodb' && 'latest'}
                              {addon.id === 'elasticsearch' && 'latest'}
                              {addon.id === 'mysql' && 'latest'}
                            </code>
                          </div>

                          {/* Env Prefix - Full Width */}
                          <div>
                            <p className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light mb-1">Environment Prefix</p>
                            <code className="block text-[11px] text-[#0a0a0a] font-mono tracking-[0.03em] font-light">
                              {addon.id.toUpperCase()}_*
                            </code>
                          </div>
                        </div>
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
                <h2 className="text-[18px] text-[#0a0a0a] mb-1">Secrets</h2>
              </div>

              <div>
                <h3 className="text-[14px] text-[#0a0a0a] mb-3">Docker Registry</h3>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Input
                        label={<>Organization <span className="text-red-500">*</span></>}
                        type="text"
                        value={config.secrets.docker_org}
                        onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_org: e.target.value } })}
                        placeholder="myorg"
                        hint="Docker Hub organization or username"
                      />
                    </div>
                    <div>
                      <Input
                        label={<>Username <span className="text-red-500">*</span></>}
                        type="text"
                        value={config.secrets.docker_username}
                        onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_username: e.target.value } })}
                        placeholder="username"
                        hint="Docker Hub username"
                      />
                    </div>
                  </div>
                  <div>
                    <Input
                      label={<>Access Token <span className="text-red-500">*</span></>}
                      type={showSecrets.docker ? "text" : "password"}
                      value={config.secrets.docker_token}
                      onChange={(e) => updateConfig({ secrets: { ...config.secrets, docker_token: e.target.value } })}
                      placeholder="dckr_pat_..."
                      hint="Personal access token for Docker Hub"
                      rightIcon={
                        <button
                          type="button"
                          onClick={() => setShowSecrets({ ...showSecrets, docker: !showSecrets.docker })}
                          className="text-[#8b8b8b] hover:text-[#0a0a0a] transition-colors"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      }
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-[#e3e8ee]">
                <h3 className="text-[14px] text-[#0a0a0a] mb-3">GitHub (Optional)</h3>
                <div>
                  <Input
                    label="Personal Access Token"
                    type={showSecrets.github ? "text" : "password"}
                    value={config.secrets.github_token}
                    onChange={(e) => updateConfig({ secrets: { ...config.secrets, github_token: e.target.value } })}
                    placeholder="ghp_..."
                    hint="Personal access token with repo access"
                    rightIcon={
                      <button
                        type="button"
                        onClick={() => setShowSecrets({ ...showSecrets, github: !showSecrets.github })}
                        className="text-[#8b8b8b] hover:text-[#0a0a0a] transition-colors"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    }
                  />
                </div>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-6 mt-6">
            <Button
              className="-ml-4"
              variant="ghost"
              onClick={handleBack}
              disabled={step === 1}
              icon={<ChevronLeft className="w-4 h-4" />}
            >
              Back
            </Button>
            <Button
              variant="primary"
              onClick={handleNext}
              disabled={!canProceed()}
              icon={<ChevronRight className="w-4 h-4" />}
            >
              {step === totalSteps ? "Deploy Project" : "Continue"}
            </Button>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
