"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";
import { Plus } from "lucide-react";

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

  return (
    <div>
      <AppHeader />
      
      <PageHeader
        title="Projects"
        description={projects.length === 0 && !loading ? "Get started by creating your first project" : "Select a project from the dropdown above to get started"}
      />
      
      {loading ? (
        <div className="text-center py-20">
          <p className="text-[15px] text-[#69707e]">Loading projects...</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-20">
          <div className="mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#eef2f5] mb-4">
              <Plus className="w-8 h-8 text-[#8b8b8b]" />
            </div>
            <h3 className="text-[17px] font-semibold text-[#0a0a0a] mb-2">No projects yet</h3>
            <p className="text-[14px] text-[#69707e] mb-6 max-w-md mx-auto">
              Create your first project to deploy applications with infrastructure, GitHub Actions, and automatic deployments.
            </p>
          </div>
          <button
            onClick={() => router.push("/setup/new")}
            className="inline-flex items-center gap-2 px-6 py-3 bg-[#0a0a0a] text-white rounded-[10px] font-medium hover:bg-[#2a2a2a] transition-colors"
          >
            <Plus className="w-5 h-5" />
            Create New Project
          </button>
        </div>
      ) : (
        <div className="text-center py-20">
          <p className="text-[15px] text-[#69707e]">No project selected</p>
        </div>
      )}
    </div>
  );
}
