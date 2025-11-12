"use client";

import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown } from "lucide-react";
import { Avatar } from "./Avatar";

interface Project {
  id: number;
  name: string;
}

interface App {
  name: string;
  type: string;
  domain: string | null;
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

  if (apps.length === 0) {
    return <span className="text-[14px] text-[#0a0a0a]">{currentApp}</span>;
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="flex items-center gap-1 outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer">
        <span className="text-[14px] text-[#0a0a0a]">
          {currentApp}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-[#333] mt-1" />
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          className="min-w-[200px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8"
          sideOffset={5}
        >
          {apps.map((app) => (
            <DropdownMenu.Item key={app.name} asChild>
              <Link
                href={`/project/${projectName}/app/${app.name}`}
                className="flex items-center gap-3 px-3 py-2 rounded hover:bg-[#f7f7f7] outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer"
              >
                <span className="text-[14px] text-[#0a0a0a]">{app.name}</span>
                {app.name === currentApp && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                )}
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
      }
    };
    fetchProjects();
  }, [projectName]);

  const menuItems = [
    { label: "Resources", href: `/project/${projectName}/app/${appName}/resources` },
    { label: "Deploy", href: `/project/${projectName}/app/${appName}/deploy` },
    { label: "Metrics", href: `/project/${projectName}/app/${appName}/metrics` },
    { label: "Actions", href: `/project/${projectName}/app/${appName}/github` },
    { label: "Secrets", href: `/project/${projectName}/app/${appName}/secrets` },
    { label: "Settings", href: `/project/${projectName}/app/${appName}/settings` },
  ];

  const isActive = (href: string) => pathname === href;
  const isOverview = pathname === `/project/${projectName}/app/${appName}`;

  return (
    <div className="mb-15">
      {/* Org Switcher + App Name */}
      <div className="flex items-center gap-2 mb-[10px]">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger className="flex items-center gap-1 outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer">
            <Avatar nameOrEmail={currentProject?.name || projectName || "SuperDeploy"} />
            <span className="text-[14px] text-[#0a0a0a]">
              {currentProject?.name || projectName}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-[#333] mt-1" />
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

        <span className="text-[#bcbcbc]">/</span>
        
        <AppSwitcher projectName={projectName} currentApp={appName} />
      </div>

      {/* Horizontal Menu */}
      <nav className="flex items-center gap-4">
        <Link
          href={`/project/${projectName}/app/${appName}`}
          className={`text-[14px] no-underline transition-colors ${
            isOverview ? "text-[#0a0a0a]" : "text-[#8b8b8b]"
          }`}
        >
          Overview
        </Link>
        {menuItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`text-[14px] no-underline transition-colors ${
              isActive(item.href) ? "text-[#0a0a0a]" : "text-[#8b8b8b]"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

