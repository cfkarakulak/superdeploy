"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, ProjectSelector } from "@/components";
import { Plus, Loader2, Folder } from "lucide-react";

interface Project {
  id: number;
  name: string;
  domain?: string;
}

export default function HomePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const response = await fetch("http://localhost:8401/api/projects/");
        if (!response.ok) throw new Error("Failed to fetch");
        const data = await response.json();
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

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-6 h-6 text-[#8b8b8b] animate-spin mx-auto mb-3" />
          <p className="text-[13px] text-[#8b8b8b] font-light tracking-[0.03em]">
            Loading projects...
          </p>
        </div>
      </div>
    );
  }

  // Empty state
  if (projects.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <Folder className="w-6 h-6 text-[#374046] mx-auto mb-4" strokeWidth={1.5} />

          <h3 className="text-[18px] text-[#222] mb-2">No Projects Yet</h3>

          <p className="text-[13px] text-[#8b8b8b] leading-relaxed font-light tracking-[0.01em] mb-6">
            Get started by creating your first project to deploy
            <br />
            your applications and infrastructure.
          </p>

          <Button onClick={() => router.push("/setup/new")} icon={<Plus className="w-4 h-4" />}>
            Create New Project
          </Button>
        </div>
      </div>
    );
  }

  // Project exists - show selector
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center max-w-md px-6">
        <Folder className="w-6 h-6 text-[#374046] mx-auto mb-4" strokeWidth={1.5} />

        <h3 className="text-[18px] text-[#222] mb-2">Welcome to SuperDeploy</h3>

        <p className="text-[13px] text-[#8b8b8b] leading-relaxed font-light tracking-[0.01em] mb-6">
          Select a project to get started or create a new one to deploy
          <br />
          your applications and infrastructure.
        </p>

        <div className="flex items-center gap-3 justify-center">
          <ProjectSelector variant="homepage" />
          
          <Button
            onClick={() => router.push("/setup/new")}
            icon={<Plus className="w-4 h-4" />}
          >
            Create New Project
          </Button>
        </div>
      </div>
    </div>
  );
}
