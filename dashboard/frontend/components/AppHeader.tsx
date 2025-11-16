"use client";

import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, ChevronRight, Github, Loader2, Check } from "lucide-react";
import { Avatar } from "./Avatar";
import { GradientAvatar } from "./GradientAvatar";

interface Project {
  id: number;
  name: string;
  domain?: string;
}

interface VM {
  name: string;
  ip: string;
  role: string;
}

interface App {
  name: string;
  type: string;
  domain: string | null;
  repo: string | null;
  owner: string | null;
}

// App Switcher Component
function AppSwitcher({ projectName, currentApp }: { projectName: string; currentApp: string }) {
  const [apps, setApps] = useState<App[]>([]);

  useEffect(() => {
    const fetchApps = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/apps/${projectName}/list`);
        if (!response.ok) throw new Error("Failed to fetch");
        const data = await response.json();
        setApps(data.apps || []);
      } catch (error) {
        console.error("Failed to fetch apps:", error);
        setApps([]);
      }
    };
    if (projectName) {
      fetchApps();
    }
  }, [projectName]);

  const currentAppData = apps.find((app) => app.name === currentApp);

  if (apps.length === 0) {
    return (
      <div className="flex items-center px-3 py-1 rounded-full bg-[#f6f8fa] border border-[#e3e8ee]">
        <span className="text-[12px] text-[#0a0a0a] font-semibold tracking-tight">{currentApp}</span>
      </div>
    );
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer group">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#f6f8fa] border border-[#e3e8ee] hover:border-[#8b8b8b] transition-all">
          <span className="text-[12px] text-[#0a0a0a] font-semibold tracking-tight">{currentApp}</span>
          <ChevronDown className="w-3 h-3 text-[#8b8b8b] group-hover:text-[#0a0a0a] transition-colors" />
        </div>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          className="min-w-[280px] bg-white rounded-xl shadow-[0_8px_24px_rgba(0,0,0,0.12)] border border-[#e3e8ee] p-2 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8"
          sideOffset={8}
        >
          <div className="px-3 py-2 mb-1">
            <span className="text-[10px] font-bold text-[#0a0a0a] tracking-wider uppercase">Switch Application</span>
          </div>
          {apps.map((app) => (
            <DropdownMenu.Item key={app.name} asChild>
              <Link
                href={`/project/${projectName}/app/${app.name}`}
                className="flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-[#f6f8fa] outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer group transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[13px] text-[#0a0a0a] font-semibold">{app.name}</span>
                    {app.name === currentApp && (
                      <div className="w-2 h-2 rounded-full bg-[#10b981]" />
                    )}
                  </div>
                  {(app.owner || app.repo) && (
                    <div className="flex items-center gap-1.5">
                      <Github className="w-3 h-3 text-[#8b8b8b]" />
                      <span className="text-[10px] text-[#8b8b8b] tracking-[0.03em] font-light">
                        {app.owner || "cheapaio"}/{app.repo || app.name}
                      </span>
                    </div>
                  )}
                </div>
              </Link>
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export default function AppHeader() {
  const params = useParams();
  const pathname = usePathname();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [vms, setVms] = useState<VM[]>([]);
  const [orchestratorIp, setOrchestratorIp] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingVms, setIsLoadingVms] = useState(true);
  const [apps, setApps] = useState<App[]>([]);
  const [addons, setAddons] = useState<any[]>([]);
  const [isLoadingAddons, setIsLoadingAddons] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch projects
        const projectsResponse = await fetch("http://localhost:8401/api/projects/");
        if (!projectsResponse.ok) throw new Error("Failed to fetch");
        const projectsData = await projectsResponse.json();
        const projectsList = Array.isArray(projectsData) ? projectsData : [];
        setProjects(projectsList);
        const current = projectsList.find((p: Project) => p.name === projectName);
        setCurrentProject(current || null);
        
        // Fetch VMs + Orchestrator IP for this project
        if (projectName) {
          setIsLoadingVms(true);
          try {
            const vmsResponse = await fetch(`http://localhost:8401/api/projects/${projectName}/vms`);
            if (vmsResponse.ok) {
              const vmsData = await vmsResponse.json();
              setVms(vmsData.vms || []);
              setOrchestratorIp(vmsData.orchestrator_ip || null);
            }
          } catch (error) {
            console.error("Failed to fetch VMs:", error);
          } finally {
            setIsLoadingVms(false);
          }
        }

        // Fetch apps
        if (projectName) {
          try {
            const appsResponse = await fetch(`http://localhost:8401/api/apps/${projectName}/list`);
            if (appsResponse.ok) {
              const appsData = await appsResponse.json();
              setApps(appsData.apps || []);
            }
          } catch (error) {
            console.error("Failed to fetch apps:", error);
          }

          // Fetch addons for current app
          if (appName) {
            setIsLoadingAddons(true);
            try {
              const addonsResponse = await fetch(`http://localhost:8401/api/resources/${projectName}/${appName}`);
              if (addonsResponse.ok) {
                const addonsData = await addonsResponse.json();
                setAddons(addonsData.addons || []);
              }
            } catch (error) {
              console.error("Failed to fetch addons:", error);
            } finally {
              setIsLoadingAddons(false);
            }
          }
        }
      } catch (error) {
        console.error("Failed to fetch projects:", error);
        setProjects([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [projectName, appName]);

  const menuItems = [
    { label: "Overview", href: `/project/${projectName}/app/${appName}` },
    { label: "Resources", href: `/project/${projectName}/app/${appName}/resources` },
    { label: "Deploy", href: `/project/${projectName}/app/${appName}/deploy` },
    { label: "Actions", href: `/project/${projectName}/app/${appName}/github` },
    { label: "Secrets", href: `/project/${projectName}/app/${appName}/secrets` },
    { label: "Logs", href: `/project/${projectName}/app/${appName}/logs` },
    { label: "Settings", href: `/project/${projectName}/app/${appName}/settings` },
  ];

  const isActive = (href: string) => {
    if (href === `/project/${projectName}/app/${appName}`) {
      return pathname === href;
    }
    
    if (href === `/project/${projectName}/app/${appName}/resources`) {
      return pathname?.startsWith(`/project/${projectName}/app/${appName}/addons/`) || pathname?.startsWith(href);
    }
    
    if (href === `/project/${projectName}/app/${appName}/secrets`) {
      return pathname?.startsWith(href);
    }
    
    if (href === `/project/${projectName}/app/${appName}/github`) {
      return pathname?.startsWith(href);
    }
    
    return pathname?.startsWith(href);
  };

  return (
    <div>
      {/* Top Bar */}
      <div className="mb-4">
        {/* Simple Layout */}
        <div className="flex items-center gap-4">
          {/* Project Selector */}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger className="bg-white p-[9px] rounded-[10px] outline-none min-w-[120px] focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer group">
              <div className="flex items-center gap-3">
                <GradientAvatar name={currentProject?.name || projectName || "SD"} size={18} />
                <div className="flex flex-col text-left">
                  <span className="text-[14px] text-[#0a0a0a] leading-tight">
                    {currentProject?.name || projectName}
                  </span>
                  <span className="text-[11px] text-[#8b8b8b] leading-tight tracking-[0.03em] font-light">
                    {isLoadingVms ? (
                      <Loader2 className="w-3 h-3 text-[#687b8c] animate-spin inline-block" />
                    ) : (
                      `${vms.length + 1} Virtual Machine${vms.length + 1 !== 1 ? "s" : ""}`
                    )}
                  </span>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-[#8b8b8b] group-hover:text-[#0a0a0a] group-data-[state=open]:rotate-180 transition-all ml-1" />
              </div>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="start"
                className="px-[16px] py-[12px] distance--8 data-[state=open]:animate-[slide-fade-in-vertical_150ms_ease-out_forwards] data-[state=closed]:animate-[slide-fade-out-vertical_150ms_ease-out_forwards] min-w-[520px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.08)] border-0 p-2"
                sideOffset={8}
              >
                <div className="relative flex min-h-[180px] gap-4">
                  {/* Left: Projects */}
                  <div className="flex-1">
                    <div className="px-2 py-1.5 mb-1">
                      <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">Projects</span>
                    </div>
                    {projects.map((project) => (
                      <DropdownMenu.Item key={project.id} asChild>
                        <Link
                          href={`/project/${project.name}`}
                          className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md hover:bg-[#f6f8fa] outline-none cursor-pointer transition-colors ${
                            project.name === projectName ? "bg-[#f6f8fa]" : ""
                          }`}
                        >
                          <GradientAvatar name={project.name} size={18} />
                          <div className="flex-1">
                            <div className="text-[14px] text-[#0a0a0a] capitalize">{project.name}</div>
                            {project.domain && (
                              <div className="text-[11px] tracking-[0.03em] font-light text-[#777]">{project.domain}</div>
                            )}
                          </div>
                          {project.name === projectName && (
                            <Check className="w-3.5 h-3.5 text-[#374046] ml-auto" strokeWidth={2.5} />
                          )}
                        </Link>
                      </DropdownMenu.Item>
                    ))}
                  </div>

                  {/* Right: Infrastructure */}
                  <div className="flex-1 relative before:content-[''] before:absolute before:left-0 before:top-[20px] before:bottom-[20px] before:w-[1px] before:bg-[#eef2f5]">
                    <div className="px-2 py-1.5 mb-1 ml-4">
                      <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">Infrastructure</span>
                    </div>
                    <div className="px-2.5 py-2 ml-4">
                      {isLoadingVms ? (
                        <div className="flex">
                          <Loader2 className="w-5 h-5 text-[#687b8c] animate-spin" />
                        </div>
                      ) : (orchestratorIp || vms.length > 0) ? (
                        <div className="flex flex-col gap-1.5">
                          {orchestratorIp && (
                            <div className="flex items-center gap-2 text-[11px] font-mono">
                              <div className="w-1.5 h-1.5 rounded-full bg-[#ef4444]" />
                              <span className="text-[#8b8b8b]">Orchestrator</span>
                              <span className="text-[#0969da] ml-auto">{orchestratorIp}</span>
                            </div>
                          )}
                          {vms.map((vm) => (
                            <div key={vm.name} className="flex items-center gap-2 text-[11px] font-mono">
                              <div className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                              <span className="text-[#8b8b8b] capitalize">{vm.role}</span>
                              <span className="text-[#0969da] ml-auto">{vm.ip}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-[11px] text-[#8b8b8b] text-center py-4">
                          No infrastructure found
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>

          {/* Arrow Separator */}
          {appName && (
            <div className="relative w-4 h-4 before:absolute before:inset-y-0 before:left-0 before:right-0 before:z-10 before:bg-gradient-to-r before:from-[#eef2f5] before:to-[rgba(238,242,245,0)]">
              <svg viewBox="0 0 16 16" className="w-4 h-4 text-[#111]" aria-label="Switch Project">
                <title>Switch Project</title>
                <path
                  fill="currentColor"
                  fillRule="evenodd"
                  d="M2 9h7.5c.27 0 .5.227.5.506v.992c0 .555.35.73.784.392l2.932-2.28c.43-.335.433-.882 0-1.22l-2.932-2.28c-.43-.335-.784-.161-.784.392v.992A.506.506 0 019.5 7H2v2z"
                />
              </svg>
            </div>
          )}

          {/* App Selector */}
          {appName && (
            <DropdownMenu.Root>
              <DropdownMenu.Trigger className="bg-white p-[9px] rounded-[10px] outline-none min-w-[120px] focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer group">
                <div className="flex items-center gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#0969da]" />
                  <div className="flex flex-col text-left">
                    <span className="text-[13px] text-[#0a0a0a] leading-tight">{appName}</span>
                    <span className="text-[11px] text-[#8b8b8b] leading-tight tracking-[0.03em] font-light">
                      {isLoadingAddons ? (
                        <Loader2 className="w-3 h-3 text-[#687b8c] animate-spin inline-block" />
                      ) : (
                        `${addons.length} addon${addons.length !== 1 ? "s" : ""}`
                      )}
                    </span>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-[#8b8b8b] group-hover:text-[#0a0a0a] group-data-[state=open]:rotate-180 transition-all ml-1" />
                </div>
              </DropdownMenu.Trigger>

              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="start"
                  className="px-[16px] py-[12px] distance--8 data-[state=open]:animate-[slide-fade-in-vertical_150ms_ease-out_forwards] data-[state=closed]:animate-[slide-fade-out-vertical_150ms_ease-out_forwards] min-w-[520px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.08)] border-0 p-2"
                  sideOffset={8}
                >
                  <div className="relative flex min-h-[180px] gap-4">
                    {/* Left: Applications */}
                    <div className="flex-1">
                      <div className="px-2 py-1.5 mb-1">
                        <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">Applications</span>
                      </div>
                      {apps.map((app) => (
                        <DropdownMenu.Item key={app.name} asChild>
                          <Link
                            href={`/project/${projectName}/app/${app.name}`}
                            className={`flex items-center gap-2 px-2.5 py-1.5 mb-1 rounded-md hover:bg-[#f6f8fa] outline-none cursor-pointer group transition-colors ${
                              app.name === appName ? "bg-[#f6f8fa]" : ""
                            }`}
                          >
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-[14px] text-[#0a0a0a]">{app.name}</span>
                              </div>
                              {(app.owner || app.repo) && (
                                <div className="flex items-center gap-1">
                                  <Github className="w-3 h-3 text-[#8b8b8b]" />
                                  <span className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">
                                    {app.owner || "cheapaio"}/{app.repo || app.name}
                                  </span>
                                </div>
                              )}
                            </div>
                            {app.name === appName && (
                              <Check className="w-3.5 h-3.5 text-[#374046]" strokeWidth={2.5} />
                            )}
                          </Link>
                        </DropdownMenu.Item>
                      ))}
                    </div>

                    {/* Right: Add-ons */}
                    <div className="flex-1 relative before:content-[''] before:absolute before:left-0 before:top-[20px] before:bottom-[20px] before:w-[1px] before:bg-[#eef2f5]">
                      <div className="px-2 py-1.5 mb-1 ml-4">
                        <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">Add-ons</span>
                      </div>
                      <div className="px-2.5 py-2 ml-4">
                        {isLoadingAddons ? (
                          <div className="flex">
                            <Loader2 className="w-5 h-5 text-[#687b8c] animate-spin" />
                          </div>
                        ) : addons.length > 0 ? (
                          <div className="flex flex-col gap-1.5">
                            {addons.map((addon) => (
                              <div key={addon.reference} className="flex items-center gap-2 text-[11px] font-mono">
                                <div className="w-1.5 h-1.5 rounded-full bg-[#8b8b8b]" />
                                <span className="text-[#0a0a0a]">{addon.reference}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-[11px] text-[#8b8b8b] text-center py-4">
                            No add-ons found
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          )}
        </div>
      </div>

      {/* Navigation Menu */}
      {appName && (
        <div>
          <nav className="mb-3 flex space-x-1 -ml-1" aria-label="Tabs">
            {menuItems.map((item) => {
              const active = isActive(item.href);
              
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative whitespace-nowrap px-2 py-3 text-[14px] font-normal transition-colors no-underline ${
                    active 
                      ? "text-black" 
                      : "text-gray-500 hover:text-black"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      )}
    </div>
  );
}

