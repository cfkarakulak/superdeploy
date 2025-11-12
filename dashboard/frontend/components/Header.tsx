"use client";

import { useState, useEffect } from "react";
import { useParams, usePathname } from "next/navigation";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Github } from "lucide-react";

interface Project {
  id: number;
  name: string;
}

interface AppInfo {
  name: string;
  repo: string;
  owner: string;
}

export function Header() {
  const params = useParams();
  const pathname = usePathname();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [projects, setProjects] = useState<Project[]>([]);
  const [currentApp, setCurrentApp] = useState<AppInfo | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const response = await fetch("http://localhost:8401/api/projects/");
        const data = await response.json();
        setProjects(data);
      } catch (err) {
        console.error("Failed to fetch projects:", err);
      }
    };

    fetchProjects();
  }, []);

  useEffect(() => {
    if (projectName && appName) {
      const fetchAppInfo = async () => {
        try {
          const response = await fetch(
            `http://localhost:8401/api/github/${projectName}/repos/${appName}/info`
          );
          if (response.ok) {
            const data = await response.json();
            setCurrentApp({
              name: appName,
              repo: data.repo || appName,
              owner: data.owner || "cheapa-io",
            });
          } else {
            setCurrentApp({
              name: appName,
              repo: appName,
              owner: "cheapa-io",
            });
          }
        } catch {
          setCurrentApp({
            name: appName,
            repo: appName,
            owner: "cheapa-io",
          });
        }
      };

      fetchAppInfo();
    } else {
      setCurrentApp(null);
    }
  }, [projectName, appName]);

  const currentProject = projects.find((p) => p.name === projectName);

  return (
    <header className="h-14 border-b border-gray-200 bg-white">
      <div className="max-w-[960px] mx-auto px-6 h-full flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Logo */}
          <a href="/" className="font-bold text-xl text-gray-900 hover:text-gray-700 transition-colors">
            SD
          </a>

          {/* Project Switcher */}
          <DropdownMenu.Root open={dropdownOpen} onOpenChange={setDropdownOpen}>
          <DropdownMenu.Trigger asChild>
            <button className="flex items-center gap-2 px-2 py-2 rounded-md h-7.5 bg-secondary hover:bg-secondary/80 transition-all duration-150 outline-none">
              <div className="w-4 h-4 rounded bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center text-white font-bold text-[10px]">
                {currentProject?.name?.[0]?.toUpperCase() || "S"}
              </div>
              <ChevronDown
                className={`w-4 h-4 text-muted-foreground transition-all duration-150 ${
                  dropdownOpen ? "rotate-180" : ""
                }`}
              />
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              className="min-w-[280px] bg-white rounded-md shadow-[0_4px_11px_0_#00000014] border border-[#0000001f] p-1 z-50 distance--8 data-[state=open]:animate-[slide-fade-in-vertical_150ms_ease-out_forwards] data-[state=closed]:animate-[slide-fade-out-vertical_150ms_ease-out_forwards]"
              sideOffset={8}
              align="start"
            >
              <div className="p-3 border-b border-gray-200">
                <p className="text-xs font-medium text-gray-500">Projects</p>
              </div>

              {projects.map((project) => (
                <DropdownMenu.Item
                  key={project.id}
                  className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-gray-100 cursor-pointer outline-none"
                  onSelect={() => {
                    window.location.href = `/project/${project.name}`;
                  }}
                >
                  <div className="w-6 h-6 rounded bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center text-white font-bold text-xs">
                    {project.name[0].toUpperCase()}
                  </div>
                  <span className="flex-1 text-sm font-medium text-gray-900">
                    {project.name}
                  </span>
                  {project.name === projectName && (
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                  )}
                </DropdownMenu.Item>
              ))}

              {projects.length === 0 && (
                <div className="px-3 py-6 text-center text-sm text-gray-500">
                  No projects found
                </div>
              )}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        {/* App Info (if on app page) */}
        {currentApp && (
          <>
            <svg
              viewBox="0 0 16 16"
              className="w-4 h-4 text-gray-400"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M2 9h7.5c.27 0 .5.227.5.506v.992c0 .555.35.73.784.392l2.932-2.28c.43-.335.433-.882 0-1.22l-2.932-2.28c-.43-.335-.784-.161-.784.392v.992A.506.506 0 019.5 7H2v2z"
              />
            </svg>

            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-md">
              <span className="font-semibold text-gray-900">{currentApp.name}</span>
              <span className="text-gray-400">·</span>
              <a
                href={`https://github.com/${currentApp.owner}/${currentApp.repo}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
              >
                <Github className="w-4 h-4" />
                <span>
                  {currentApp.owner}/{currentApp.repo}
                </span>
              </a>
            </div>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-500">SuperDeploy Dashboard</span>
        </div>
      </div>
    </header>
  );
}

