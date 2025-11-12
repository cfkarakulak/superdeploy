"use client";

import { useEffect, useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { Avatar } from "./Avatar";

interface Project {
  id: number;
  name: string;
}

export default function SimpleHeader() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const response = await fetch("http://localhost:8401/api/projects/");
        if (!response.ok) throw new Error("Failed to fetch");
        const data = await response.json();
        console.log("Projects data:", data);
        setProjects(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error("Failed to fetch projects:", error);
        setProjects([]);
      } finally {
        setLoading(false);
      }
    };
    fetchProjects();
  }, []);

  const currentProject = projects[0] || { name: "SuperDeploy" };

  return (
    <div className="mb-8">
      {/* Org Switcher */}
      <div className="flex items-center gap-2">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger className="flex items-center gap-1 outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer">
            <Avatar nameOrEmail={currentProject.name} />
            <span className="text-[14px] text-[#0a0a0a]">
              {currentProject.name}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-[#333] mt-1" />
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="start"
              className="min-w-[200px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8"
              sideOffset={5}
            >
              {loading ? (
                <div className="px-3 py-2 text-[14px] text-[#8b8b8b]">Loading...</div>
              ) : projects.length === 0 ? (
                <div className="px-3 py-2 text-[14px] text-[#8b8b8b]">No projects</div>
              ) : (
                projects.map((project) => (
                  <DropdownMenu.Item key={project.id} asChild>
                      <Link
                        href={`/project/${project.name}`}
                        className="flex items-center gap-3 px-3 py-2 rounded hover:bg-[#f7f7f7] outline-none focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 cursor-pointer"
                      >
                      <Avatar nameOrEmail={project.name} />
                      <span className="text-[14px] text-[#0a0a0a]">{project.name}</span>
                    </Link>
                  </DropdownMenu.Item>
                ))
              )}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </div>
  );
}

