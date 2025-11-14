"use client";

import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Github } from "lucide-react";
import { Avatar } from "./Avatar";

interface Project {
  id: number;
  name: string;
  domain?: string;
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
  const githubOwner = currentAppData?.owner || "cheapaio";
  const githubRepo = currentAppData?.repo || currentApp;

  if (apps.length === 0) {
    return (
      <div className="flex flex-col items-start justify-center px-2 py-1.5 rounded-[10px] min-h-[34px] bg-[#e6e9f0]" title={currentApp}>
        <span className="text-[14px] text-[#0a0a0a] leading-tight">{currentApp}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start justify-center">
      <span className="text-[11px] text-[#777] leading-tight tracking-[0.02em] mb-[6px] font-light">App:</span>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger className="outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer">
          <div className="flex items-center space-x-1 px-3.5 py-2 rounded-[10px] h-[34px] bg-[#e3e6ec] hover:bg-[#dbdfe6] transition-colors">

            <div className="flex items-center gap-1 w-full">
              <span className="text-[14px] text-[#0a0a0a] leading-tight">{currentApp}</span>
              <ChevronDown className="size-3.5 text-[#8b8b8b] transition-all duration-150 ml-auto" />
            </div>
          </div>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="start"
            className="min-w-[220px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8"
            sideOffset={5}
          >
            {apps.map((app) => (
              <DropdownMenu.Item key={app.name} asChild>
                <Link
                  href={`/project/${projectName}/app/${app.name}`}
                  className="flex flex-col items-start gap-0.5 px-3 py-2 rounded hover:bg-[#f7f7f7] outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer"
                >
                  <div className="flex items-center gap-2 w-full">
                    <span className="text-[14px] text-[#0a0a0a] leading-tight">{app.name}</span>
                    {app.name === currentApp && (
                      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Github className="size-3 text-[#8b8b8b]" />
                    <span className="text-[11px] text-[#8b8b8b] leading-tight">
                      {app.owner || "cheapaio"}/{app.repo || app.name}
                    </span>
                  </div>
                </Link>
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  );
}

export default function AppHeader() {
  const params = useParams();
  const pathname = usePathname();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const response = await fetch("http://localhost:8401/api/projects/");
        if (!response.ok) throw new Error("Failed to fetch");
        const data = await response.json();
        console.log("AppHeader Projects data:", data);
        const projectsList = Array.isArray(data) ? data : [];
        setProjects(projectsList);
        const current = projectsList.find((p: Project) => p.name === projectName);
        setCurrentProject(current || null);
      } catch (error) {
        console.error("Failed to fetch projects:", error);
        setProjects([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProjects();
  }, [projectName]);

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
    // Overview için tam eşleşme kontrolü
    if (href === `/project/${projectName}/app/${appName}`) {
      return pathname === href;
    }
    // Diğer sayfalar için startsWith
    return pathname?.startsWith(href);
  };

  return (
    <div>
      {/* Org Switcher + App Name */}
      <div className="flex items-center gap-2 mb-8">
        <div className="flex flex-col items-start justify-center">
          <span className="text-[11px] text-[#777] leading-tight tracking-[0.02em] mb-[6px] font-light">Project:</span>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger className="outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer">
              <div className="flex items-center space-x-1 px-3.5 py-2 rounded-[10px] h-[34px] bg-[#e3e6ec] hover:bg-[#dbdfe6] transition-colors">
                {!isLoading && (
                  <>
                    <div className="flex items-center gap-1.5">
                      <Avatar 
                        nameOrEmail={currentProject?.name || projectName || "SuperDeploy"}
                      />
                    </div>
                    <span className="text-[14px] text-[#0a0a0a]">
                      {currentProject?.domain || currentProject?.name || projectName}
                    </span>
                  </>
                )}
                <ChevronDown className="size-4 text-[#8b8b8b] transition-all duration-150" />
              </div>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="start"
                className="min-w-[200px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8"
                sideOffset={5}
              >
                {projects.map((project) => (
                  <DropdownMenu.Item key={project.id} asChild>
                      <Link
                        href={`/project/${project.name}`}
                        className="flex items-center gap-3 px-3 py-2 rounded hover:bg-[#f7f7f7] outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer"
                      >
                      <Avatar nameOrEmail={project.name} />
                      <span className="text-[14px] text-[#0a0a0a]">{project.name}</span>
                      {project.name === projectName && (
                        <div className="ml-auto w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                      )}
                    </Link>
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
            
        {/* App Switcher - Only show if we're in an app context */}
        {appName && (
          <>
            <div className="relative mt-5 w-4 h-4 before:absolute before:inset-y-0 before:left-0 before:right-0 before:z-10 before:bg-gradient-to-r before:from-[#f3f5f9] before:to-[rgba(247,248,251,0)]">
              <svg
                viewBox="0 0 16 16"
                className="w-4 h-4 text-black"
                aria-label="Separator"
              >
                <path
                  fill="currentColor"
                  fillRule="evenodd"
                  d="M2 9h7.5c.27 0 .5.227.5.506v.992c0 .555.35.73.784.392l2.932-2.28c.43-.335.433-.882 0-1.22l-2.932-2.28c-.43-.335-.784-.161-.784.392v.992A.506.506 0 019.5 7H2v2z"
                />
              </svg>
            </div>
            
            <AppSwitcher projectName={projectName} currentApp={appName} />
          </>
        )}
      </div>

      {/* Tab-style Menu - Below switchers */}
      {appName && (
        <div>
          <nav className="mb-1 flex space-x-1 -ml-1" aria-label="Tabs">
            {menuItems.map((item) => {
              const active = isActive(item.href);
              
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative whitespace-nowrap px-2 py-3 text-[14px] transition-colors no-underline ${
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

