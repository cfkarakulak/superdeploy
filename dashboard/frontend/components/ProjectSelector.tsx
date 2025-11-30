"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Github, Check, Loader2, Activity } from "lucide-react";
import { getCache, setCache } from "@/lib/cache";
import { GradientAvatar } from "./GradientAvatar";

interface Project {
  id: number;
  name: string;
  domain?: string;
}

interface App {
  name: string;
  repo: string;
  owner: string;
}

interface VM {
  name: string;
  role: string;
  ip: string;
}

interface Orchestrator {
  id: number;
  name: string;
  deployed: boolean;
  ip?: string;
  grafana_url?: string;
  prometheus_url?: string;
}

interface ProjectWithApps extends Project {
  apps: App[];
  vms: VM[];
  orchestratorIp: string | null;
}

interface ProjectSelectorProps {
  currentProjectName?: string;
  currentAppName?: string;
  variant?: "default" | "homepage";
}

export default function ProjectSelector({
  currentProjectName,
  currentAppName,
  variant = "default",
}: ProjectSelectorProps) {
  const router = useRouter();
  const [projectsWithApps, setProjectsWithApps] = useState<ProjectWithApps[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectWithApps | null>(null);
  const [orchestrator, setOrchestrator] = useState<Orchestrator | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProjects = async () => {
      // Always fetch orchestrator (not cached separately)
      try {
        const orchRes = await fetch("http://localhost:8401/api/projects/orchestrator");
        if (orchRes.ok) {
          const orchData = await orchRes.json();
          setOrchestrator(orchData);
        }
      } catch (err) {
        console.error("Failed to fetch orchestrator:", err);
      }

      // Check frontend cache first for projects
      const cachedData = getCache<ProjectWithApps[]>("projects_with_apps");
      if (cachedData && cachedData.length > 0) {
        setProjectsWithApps(cachedData);
        setLoading(false);

        // Auto-select current or first project
        if (currentProjectName) {
          const current = cachedData.find((p) => p.name === currentProjectName);
          setSelectedProject(current || cachedData[0]);
        } else if (cachedData.length > 0) {
          setSelectedProject(cachedData[0]);
        }
        return;
      }

      try {
        // Fetch projects (application type only)
        const response = await fetch("http://localhost:8401/api/projects/");
        if (!response.ok) throw new Error("Failed to fetch");
        const data = await response.json();

        // Fetch apps and VMs for each project
        const projectsData = await Promise.all(
          data.map(async (project: Project) => {
            try {
              const [appsRes, vmsRes] = await Promise.all([
                fetch(`http://localhost:8401/api/apps/${project.name}/list`),
                fetch(`http://localhost:8401/api/projects/${project.name}/vms`),
              ]);

              const appsData = appsRes.ok ? await appsRes.json() : { apps: [] };
              const vmsData = vmsRes.ok
                ? await vmsRes.json()
                : { vms: [], orchestrator_ip: null };

              return {
                ...project,
                apps: appsData.apps || [],
                vms: vmsData.vms || [],
                orchestratorIp: vmsData.orchestrator_ip || null,
              };
            } catch (err) {
              console.error(`Failed to fetch data for ${project.name}:`, err);
            }
            return { ...project, apps: [], vms: [], orchestratorIp: null };
          })
        );

        setProjectsWithApps(projectsData);

        // Cache the data
        setCache("projects_with_apps", projectsData);

        // Auto-select current or first project
        if (currentProjectName) {
          const current = projectsData.find((p) => p.name === currentProjectName);
          setSelectedProject(current || projectsData[0]);
        } else if (projectsData.length > 0) {
          setSelectedProject(projectsData[0]);
        }
      } catch (error) {
        console.error("Failed to fetch projects:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchProjects();
  }, [currentProjectName]);

  if (loading) {
    return (
      <div className="bg-[#dde1e4] p-[9px] rounded-[10px] min-w-[160px]">
        <div className="flex items-center gap-2 text-[11px] text-[#8b8b8b]">
          <Loader2 className="w-3 h-3 animate-spin" />
          Loading...
        </div>
      </div>
    );
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="bg-[#dde1e4] h-[36px] p-[9px] pt-[7px] rounded-[10px] outline-none min-w-[160px] focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer group">

        <div className="flex items-center gap-3">
          <GradientAvatar
            name={currentProjectName || selectedProject?.name || "SD"}
            size={18}
          />
          <div className="flex items-center gap-2 text-left flex-1">
            <span className="text-[14px] text-[#0a0a0a]">
              {currentProjectName || selectedProject?.name || "Select project..."}
            </span>
            {variant === "default" && currentAppName && (
              <>
                <span className="text-[14px] text-[#8b8b8b]">›</span>
                <span className="text-[14px] text-[#8b8b8b]">
                  {currentAppName}
                </span>
              </>
            )}
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-[#8b8b8b] group-hover:text-[#0a0a0a] group-data-[state=open]:rotate-180 transition-all ml-1" />
        </div>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          className="px-[16px] py-[12px] distance--8 data-[state=open]:animate-[slide-fade-in-vertical_150ms_ease-out_forwards] data-[state=closed]:animate-[slide-fade-out-vertical_150ms_ease-out_forwards] min-w-[660px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.08)] border-0 p-2"
          sideOffset={8}
        >
          <div className="relative flex min-h-[180px] gap-3">
            {/* Left: Projects + Orchestrator */}
            <div className="w-[30%]">
              {/* Orchestrator Section */}
              {orchestrator && (
                <>
                  <div className="px-2 py-1.5 mb-1">
                    <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">
                      Infrastructure
                    </span>
                  </div>
                  <DropdownMenu.Item
                    onClick={() => {
                      router.push("/infrastructure/orchestrator");
                    }}
                    className={`flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] hover:bg-[#f6f8fa] outline-none cursor-pointer transition-colors mb-3 ${
                      currentProjectName === "orchestrator" ? "bg-[#f6f8fa]" : ""
                    }`}
                  >
                    <Activity className="w-4 h-4 text-purple-600" />
                    <div className="flex-1">
                      <div className="text-[14px] text-[#0a0a0a]">
                        Orchestrator
                      </div>
                      <div className="text-[11px] tracking-[0.03em] font-light text-[#777]">
                        {orchestrator.deployed ? (
                          <span className="text-green-600">● Running</span>
                        ) : (
                          <span className="text-[#8b8b8b]">Not deployed</span>
                        )}
                      </div>
                    </div>
                    {currentProjectName === "orchestrator" && (
                      <Check
                        className="w-3.5 h-3.5 text-[#374046] ml-auto"
                        strokeWidth={2.5}
                      />
                    )}
                  </DropdownMenu.Item>
                </>
              )}

              {/* Projects Section */}
              <div className="px-2 py-1.5 mb-1">
                <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">
                  Projects
                </span>
              </div>
              {projectsWithApps.map((project) => (
                <DropdownMenu.Item
                  key={project.id}
                  onSelect={(e) => {
                    e.preventDefault();
                  }}
                  onMouseEnter={() => setSelectedProject(project)}
                  onClick={() => {
                    if (variant === "homepage") {
                      setSelectedProject(project);
                    } else {
                      router.push(`/project/${project.name}`);
                    }
                  }}
                  className={`flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] hover:bg-[#f6f8fa] outline-none cursor-pointer transition-colors ${
                    selectedProject?.id === project.id ? "bg-[#f6f8fa]" : ""
                  }`}
                >
                  <GradientAvatar name={project.name} size={18} />
                  <div className="flex-1">
                    <div className="text-[14px] text-[#0a0a0a] capitalize">
                      {project.name}
                    </div>
                    {project.domain && (
                      <div className="text-[11px] tracking-[0.03em] font-light text-[#777]">
                        {project.domain}
                      </div>
                    )}
                  </div>
                  {selectedProject?.id === project.id && (
                    <Check
                      className="w-3.5 h-3.5 text-[#374046] ml-auto"
                      strokeWidth={2.5}
                    />
                  )}
                </DropdownMenu.Item>
              ))}
            </div>

            {/* Middle: Applications */}
            <div className="w-[35%] relative before:content-[''] before:absolute before:left-0 before:top-[20px] before:bottom-[20px] before:w-px before:bg-[#eef2f5]">
              <div className="px-2 py-1.5 mb-1 ml-3">
                <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">
                  Applications
                </span>
              </div>
              <div className="ml-3">
                {selectedProject ? (
                  projectsWithApps.find((p) => p.id === selectedProject.id)?.apps.length ? (
                    projectsWithApps
                      .find((p) => p.id === selectedProject.id)
                      ?.apps.map((app) => (
                        <DropdownMenu.Item
                          key={app.name}
                          onClick={() =>
                            router.push(`/project/${selectedProject.name}/app/${app.name}`)
                          }
                          className={`flex items-center gap-2 px-2.5 py-1.5 mb-1 rounded-[10px] hover:bg-[#f6f8fa] outline-none cursor-pointer group transition-colors ${
                            currentAppName === app.name ? "bg-[#f6f8fa]" : ""
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
                          {currentAppName === app.name && (
                            <Check
                              className="w-3.5 h-3.5 text-[#374046]"
                              strokeWidth={2.5}
                            />
                          )}
                        </DropdownMenu.Item>
                      ))
                  ) : (
                    <div className="px-2.5 py-8 text-center">
                      <p className="text-[11px] text-[#8b8b8b] font-light">
                        No applications
                      </p>
                    </div>
                  )
                ) : (
                  <div className="px-2.5 py-8 text-center">
                    <p className="text-[11px] text-[#8b8b8b] font-light">Select a project</p>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Infrastructure */}
            <div className="w-[35%] relative before:content-[''] before:absolute before:left-0 before:top-[20px] before:bottom-[20px] before:w-px before:bg-[#eef2f5]">
              <div className="px-2 py-1.5 mb-1 ml-3">
                <span className="text-[11px] font-light text-[#777] tracking-[0.03em]">
                  Infrastructure
                </span>
              </div>
              <div className="px-2.5 py-2 ml-3">
                {selectedProject ? (
                  projectsWithApps.find((p) => p.id === selectedProject.id)?.orchestratorIp ||
                  projectsWithApps.find((p) => p.id === selectedProject.id)?.vms.length ? (
                    <div className="flex flex-col gap-1.5">
                      {projectsWithApps.find((p) => p.id === selectedProject.id)
                        ?.orchestratorIp && (
                        <div className="flex items-center gap-2 text-[11px] tracking-[0.03em] font-light">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#ef4444]" />
                          <span className="text-[#8b8b8b]">Orchestrator</span>
                          <span className="text-[#0969da] ml-auto">
                            {
                              projectsWithApps.find((p) => p.id === selectedProject.id)
                                ?.orchestratorIp
                            }
                          </span>
                        </div>
                      )}
                      {projectsWithApps
                        .find((p) => p.id === selectedProject.id)
                        ?.vms.map((vm) => (
                          <div
                            key={vm.name}
                            className="flex items-center gap-2 text-[11px] tracking-[0.03em] font-light"
                          >
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
                  )
                ) : (
                  <div className="text-[11px] text-[#8b8b8b] text-center py-4">
                    Select a project
                  </div>
                )}
              </div>
            </div>
          </div>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
