"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { notFound } from "next/navigation";
import { 
  Loader2,
  Settings,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  Check,
  Database,
  Zap,
  Server,
  MessageSquare,
  Plus,
  X,
  Eye,
  Search
} from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import AppHeader from "@/components/AppHeader";
import { Button, Input } from "@/components";
import { getAddonLogo } from "@/lib/addonLogos";

interface Project {
  id: number;
  name: string;
  domain?: string;
  github_org?: string;
}

interface ProjectConfig {
  project_name: string;
  domain: string;
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
  };
}

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

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [projectNotFound, setProjectNotFound] = useState(false);
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState<ProjectConfig>({
    project_name: "",
    domain: "",
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
    },
  });
  const [githubRepos, setGithubRepos] = useState<GroupedRepos>({});
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);

  const totalSteps = 4;

  // Fetch project and populate config
  useEffect(() => {
    const fetchData = async () => {
      try {
        const projectRes = await fetch(`http://localhost:8401/api/projects/${projectName}`);
        
        if (projectRes.status === 404) {
          setProjectNotFound(true);
          setLoading(false);
          return;
        }

        if (!projectRes.ok) {
          throw new Error("Failed to fetch project");
        }

        const projectData = await projectRes.json();
        setProject(projectData);

        // Populate config with existing project data
        setConfig(prev => ({
          ...prev,
          project_name: projectData.name || "",
          domain: projectData.domain || "",
          // TODO: Load other fields from config.yml via API
        }));

      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    };

    if (projectName) {
      fetchData();
    }
  }, [projectName]);

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
      handleSave();
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // TODO: Implement save logic
      await new Promise(resolve => setTimeout(resolve, 1000));
      router.push(`/project/${projectName}/app/${config.apps[0]?.name || 'api'}`);
    } catch (error) {
      console.error("Failed to save:", error);
    } finally {
      setSaving(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1:
        return config.project_name && config.domain && config.gcp_project && config.gcp_region;
      case 2:
        return config.apps.length > 0 && config.apps.every(app => app.name && app.repo && app.port);
      case 3:
        return true;
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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-6 h-6 text-[#8b8b8b] animate-spin mx-auto mb-3" />
          <p className="text-[13px] text-[#8b8b8b] font-light tracking-[0.03em]">
            Loading project...
          </p>
        </div>
      </div>
    );
  }

  if (projectNotFound) {
    notFound();
  }

  if (saving) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-5 h-5 text-[#8b8b8b] animate-spin mx-auto mb-3" />
          <p className="text-[13px] text-[#8b8b8b] font-light tracking-[0.03em]">
            Saving changes...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <AppHeader />
      
      <div className="min-h-screen flex py-12">
        <div className="w-full max-w-4xl">
          {/* Header */}
          <div className="text-center mb-8">
            <Settings className="w-6 h-6 text-[#374046] mx-auto mb-4" strokeWidth={1.5} />
            <h3 className="text-[18px] text-[#222] mb-2">
              Project Configuration
            </h3>
            <p className="text-[13px] text-[#8b8b8b] leading-relaxed font-light tracking-[0.01em]">
              Configure {project?.name} project settings
            </p>
          </div>

          {/* Progress */}
          <div className="mb-8">
            <div className="flex items-center w-full gap-6">
              {[
                { num: 1, label: "Project\nInformation" },
                { num: 2, label: "Applications\n& Repositories" },
                { num: 3, label: "Add-ons\n& Services" },
                { num: 4, label: "Deployment\nCredentials" }
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
          <div className="bg-white rounded-[16px] p-8 shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
            {/* Step 1: Project Info */}
            {step === 1 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-[18px] text-[#0a0a0a] mb-1">Project Information</h2>
                </div>

                <Input
                  label={<>Project Name <span className="text-red-500">*</span></>}
                  type="text"
                  value={config.project_name}
                  onChange={(e) => updateConfig({ project_name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                  placeholder="myproject"
                  hint="Lowercase letters, numbers, and hyphens only"
                  disabled
                />

                <Input
                  label={<>Domain <span className="text-red-500">*</span></>}
                  type="text"
                  value={config.domain}
                  onChange={(e) => updateConfig({ domain: e.target.value })}
                  placeholder="example.com"
                  hint="Your application's domain name"
                />

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

            {/* Step 2-4: Same as wizard... */}
            {step === 2 && (
              <div className="text-center py-12">
                <p className="text-[13px] text-[#8b8b8b]">Applications configuration (TODO)</p>
              </div>
            )}

            {step === 3 && (
              <div className="text-center py-12">
                <p className="text-[13px] text-[#8b8b8b]">Add-ons configuration (TODO)</p>
              </div>
            )}

            {step === 4 && (
              <div className="text-center py-12">
                <p className="text-[13px] text-[#8b8b8b]">Secrets configuration (TODO)</p>
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
                {step === totalSteps ? "Save Changes" : "Continue"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
