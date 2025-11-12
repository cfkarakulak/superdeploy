"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components";

interface Container {
  id: string;
  name: string;
  image: string;
  state: string;
  status: string;
  cpu_percent?: number;
  memory_usage?: string;
  memory_percent?: number;
}

// Breadcrumb Skeleton
const BreadcrumbSkeleton = () => (
  <div className="flex items-center gap-3 mb-6">
    <div className="w-5 h-5 bg-[#e3e8ee] rounded skeleton-animated" />
    <div className="flex items-center gap-2">
      <div className="w-[80px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[100px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[100px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[110px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Header Skeleton
const MonitoringHeaderSkeleton = () => (
  <div className="mb-6">
    <div className="w-[140px] h-[28px] bg-[#e3e8ee] rounded-md mb-2 skeleton-animated" />
    <div className="w-[220px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
  </div>
);

// Container Card Skeleton
const ContainerCardSkeleton = () => (
  <div className="bg-white rounded-lg p-5 shadow-sm">
    <div className="flex items-center justify-between mb-4">
      <div className="flex-1">
        <div className="w-[220px] h-[20px] bg-[#e3e8ee] rounded-md mb-2 skeleton-animated" />
        <div className="w-[180px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      </div>
      <div className="w-[70px] h-[24px] bg-[#e3e8ee] rounded-full skeleton-animated" />
    </div>
    <div className="grid grid-cols-3 gap-4 mb-4">
      <div>
        <div className="w-[50px] h-[16px] bg-[#e3e8ee] rounded mb-1 skeleton-animated" />
        <div className="w-[80px] h-[18px] bg-[#e3e8ee] rounded skeleton-animated" />
      </div>
      <div>
        <div className="w-[60px] h-[16px] bg-[#e3e8ee] rounded mb-1 skeleton-animated" />
        <div className="w-[90px] h-[18px] bg-[#e3e8ee] rounded skeleton-animated" />
      </div>
      <div>
        <div className="w-[70px] h-[16px] bg-[#e3e8ee] rounded mb-1 skeleton-animated" />
        <div className="w-[100px] h-[18px] bg-[#e3e8ee] rounded skeleton-animated" />
      </div>
    </div>
    <div className="flex gap-2">
      <div className="w-[80px] h-[32px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[80px] h-[32px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Full Page Skeleton
const MonitoringPageSkeleton = () => (
  <div>
    <BreadcrumbSkeleton />
    <MonitoringHeaderSkeleton />
    <div className="space-y-4">
      {Array.from({ length: 3 }, (_, i) => (
        <ContainerCardSkeleton key={`container-skeleton-${i}`} />
      ))}
    </div>
  </div>
);

export default function AppMonitoringPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [containers, setContainers] = useState<Container[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchContainers = async () => {
    try {
      const response = await fetch(
        `http://localhost:8401/api/containers/${projectName}/list`
      );
      const data = await response.json();
      const appContainers = (data.containers || []).filter((c: Container) =>
        c.name.includes(`${projectName}_${appName}_`)
      );
      setContainers(appContainers);
    } catch (err) {
      console.error("Failed to fetch containers:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectName && appName) {
      fetchContainers();
      const interval = setInterval(fetchContainers, 10000);
      return () => clearInterval(interval);
    }
  }, [projectName, appName]);

  const handleRestart = async (containerName: string) => {
    if (!confirm(`Restart ${containerName}?`)) return;

    try {
      const response = await fetch(
        `http://localhost:8401/api/containers/${projectName}/containers/${containerName}/restart`,
        { method: "POST" }
      );

      if (!response.ok) throw new Error("Failed to restart");

      alert("Container restarted");
      await fetchContainers();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to restart");
    }
  };

  if (loading) {
    return <MonitoringPageSkeleton />;
  }

  return (
    <div>
      <AppHeader />
      
      <PageHeader
        breadcrumbs={[
          { label: "Projects", href: "/" },
          { label: projectName, href: `/project/${projectName}` },
          { label: "Apps", href: `/project/${projectName}` },
          { label: appName, href: `/project/${projectName}/app/${appName}` },
          { label: "Monitoring", href: `/project/${projectName}/app/${appName}/monitoring` }
        ]}
        title="Container Monitoring"
        description={`Real-time container metrics, resource usage, and logs for ${appName}`}
      />

      {containers.length === 0 ? (
        <div className="bg-white shadow-sm rounded-lg p-8 text-center text-gray-600">
          No containers running
        </div>
      ) : (
        <div className="grid gap-4">
          {containers.map((container) => (
            <div
              key={container.id}
              className="bg-white rounded-lg p-6 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-bold mb-1">{container.name}</h3>
                  <p className="text-sm text-gray-600">Image: {container.image}</p>
                  {container.cpu_percent !== undefined && (
                    <div className="flex gap-4 mt-2 text-sm">
                      <span>CPU: {container.cpu_percent.toFixed(1)}%</span>
                      <span>Memory: {container.memory_usage}</span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-3 py-1 rounded text-xs  ${
                      container.state === "running"
                        ? "bg-green-100 text-green-800"
                        : container.state === "exited"
                        ? "bg-red-100 text-red-800"
                        : "bg-yellow-100 text-yellow-800"
                    }`}
                  >
                    {container.state}
                  </span>
                  <Button
                    onClick={() => handleRestart(container.name)}
                    size="sm"
                    className="!bg-[#ff6b35] !text-[#15291f] hover:!bg-[#ff5722]"
                  >
                    Restart
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
