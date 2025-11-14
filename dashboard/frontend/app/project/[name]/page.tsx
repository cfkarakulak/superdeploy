"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Package, Database, ChevronRight } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";

interface App {
  name: string;
  type: string;
  domain: string | null;
}

interface Addon {
  name: string;
  type: string;
  category: string;
  reference: string;
}

// Breadcrumb Skeleton
const BreadcrumbSkeleton = () => (
  <div className="flex items-center gap-3 mb-6">
    <div className="w-5 h-5 bg-[#e3e8ee] rounded skeleton-animated" />
    <div className="flex items-center gap-2">
      <div className="w-[80px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[100px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Header Skeleton
const ProjectHeaderSkeleton = () => (
  <div className="mb-8">
    <div className="w-[200px] h-[28px] bg-[#e3e8ee] rounded-md mb-2 skeleton-animated" />
    <div className="w-[150px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
  </div>
);

// App Card Skeleton
const AppCardSkeleton = () => (
  <div className="bg-white shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)] rounded-lg p-6">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="flex-1 space-y-2">
        <div className="w-[120px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
        <div className="w-[180px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      </div>
      <div className="w-4 h-4 bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Addons Card Skeleton
const AddonsCardSkeleton = () => (
  <div className="bg-white shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)] rounded-lg p-6">
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-[#e3e8ee] rounded skeleton-animated" />
        <div className="space-y-2">
          <div className="w-[80px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
          <div className="w-[140px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
        </div>
      </div>
      <div className="w-4 h-4 bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
    <div className="flex flex-wrap gap-2">
      {Array.from({ length: 3 }, (_, i) => (
        <div key={`addon-tag-skeleton-${i}`} className="w-[100px] h-[24px] bg-[#e3e8ee] rounded-full skeleton-animated" />
      ))}
    </div>
  </div>
);

// Full Page Skeleton
const ProjectPageSkeleton = () => (
  <div>
    <BreadcrumbSkeleton />
    <ProjectHeaderSkeleton />

    {/* Applications Section */}
    <div className="mb-8">
      <div className="w-[130px] h-[24px] bg-[#e3e8ee] rounded-md mb-4 skeleton-animated" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: 2 }, (_, i) => (
          <AppCardSkeleton key={`app-skeleton-${i}`} />
        ))}
      </div>
    </div>

    {/* Addons Section */}
    <div>
      <div className="w-[80px] h-[24px] bg-[#e3e8ee] rounded-md mb-4 skeleton-animated" />
      <AddonsCardSkeleton />
    </div>
  </div>
);

export default function ProjectPage() {
  const params = useParams();
  const projectName = params?.name as string;

  const [apps, setApps] = useState<App[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [appsRes, addonsRes] = await Promise.all([
          fetch(`http://localhost:8000/api/apps/${projectName}/list`),
          fetch(`http://localhost:8000/api/addons/${projectName}/list`),
        ]);

        const appsData = await appsRes.json();
        const addonsData = await addonsRes.json();

        setApps(appsData.apps || []);
        setAddons(addonsData.addons || []);
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

  if (loading) {
    return <ProjectPageSkeleton />;
  }

  return (
    <div>
      <AppHeader />
      
        <PageHeader
          breadcrumb={{
            label: "Projects",
            href: "/"
          }}
          title={projectName}
          description="Manage applications, add-ons, and infrastructure for your project"
        />

      {/* Applications */}
      <div className="mb-10">
        <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Applications</h2>
        {apps.length > 0 ? (
          <div className="space-y-3">
            {apps.map((app) => (
              <Link
                key={app.name}
                href={`/project/${projectName}/app/${app.name}`}
                className="block bg-white rounded-[16px] p-[20px] hover:bg-[#f7f7f7] transition-all shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-[#f7f7f7] rounded flex items-center justify-center">
                    <Package className="w-5 h-5 text-[#008545]" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-[17px] font-semibold text-[#0a0a0a]">{app.name}</h3>
                    {app.domain && (
                      <p className="text-[13px] text-[#8b8b8b]">{app.domain}</p>
                    )}
                  </div>
                  <ChevronRight className="w-5 h-5 text-[#8b8b8b]" />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-[16px] p-[20px] text-center shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
            <p className="text-[15px] text-[#8b8b8b]">No applications yet</p>
          </div>
        )}
      </div>

      {/* Addons Summary */}
      <div>
        <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Add-ons</h2>
        <Link
          href={`/project/${projectName}/addons`}
          className="block bg-[#f7f7f7] rounded-lg p-5 hover:bg-[#ebebeb] transition-all shadow-[0_0_0_1px_rgba(0,0,0,0.08)] hover:shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-[#f7f7f7] rounded flex items-center justify-center">
                <Database className="w-5 h-5 text-[#6366f1]" />
              </div>
              <div>
                <h3 className="text-[17px] font-semibold text-[#0a0a0a]">View all add-ons</h3>
                <p className="text-[13px] text-[#69707e]">
                  {addons.length} add-on{addons.length !== 1 ? "s" : ""} installed
                </p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-[#69707e]" />
          </div>
          {addons.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {addons.slice(0, 5).map((addon) => (
                <span
                  key={addon.reference}
                  className="px-3 py-1 bg-[#e0e7ff] text-[#4f46e5] rounded-full text-[12px] "
                >
                  {addon.name}
                </span>
              ))}
              {addons.length > 5 && (
                <span className="px-3 py-1 bg-[#ebebeb] text-[#69707e] rounded-full text-[12px] ">
                  +{addons.length - 5} more
                </span>
              )}
            </div>
          )}
        </Link>
      </div>
    </div>
  );
}
