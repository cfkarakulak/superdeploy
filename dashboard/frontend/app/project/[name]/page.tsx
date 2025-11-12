"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

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
  <div className="bg-white shadow-sm rounded-lg p-6">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="flex-1 space-y-2">
        <div className="w-[120px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
        <div className="w-[180px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      </div>
      <div className="w-6 h-6 bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Addons Card Skeleton
const AddonsCardSkeleton = () => (
  <div className="bg-white shadow-sm rounded-lg p-6">
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-[#e3e8ee] rounded skeleton-animated" />
        <div className="space-y-2">
          <div className="w-[80px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
          <div className="w-[140px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
        </div>
      </div>
      <div className="w-6 h-6 bg-[#e3e8ee] rounded skeleton-animated" />
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
  <div className="max-w-[960px] mx-auto py-8 px-6">
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
          fetch(`http://localhost:8401/api/apps/${projectName}/list`),
          fetch(`http://localhost:8401/api/addons/${projectName}/list`),
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
    <div className="max-w-[960px] mx-auto py-8 px-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-6">
        <Link href="/" className="text-gray-500 hover:text-gray-900">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-900">
            Projects
          </Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{projectName}</span>
        </div>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-2">{projectName}</h1>
        <p className="text-gray-600">Project dashboard</p>
      </div>

      {/* Applications */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-4">Applications</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {apps.map((app) => (
            <Link
              key={app.name}
              href={`/project/${projectName}/app/${app.name}`}
              className="bg-white shadow-sm rounded-lg p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded flex items-center justify-center text-white font-bold">
                  {app.name[0].toUpperCase()}
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">{app.name}</h3>
                  {app.domain && (
                    <p className="text-sm text-gray-500">{app.domain}</p>
                  )}
                </div>
                <span className="text-gray-400">→</span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Addons */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Addons</h2>
        <Link
          href={`/project/${projectName}/addons`}
          className="block bg-white shadow-sm rounded-lg p-6 hover:shadow-md transition-shadow"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-purple-600 rounded flex items-center justify-center text-white font-bold">
                A
              </div>
              <div>
                <h3 className="font-semibold text-lg">Addons</h3>
                <p className="text-sm text-gray-500">
                  {addons.length} addon{addons.length !== 1 ? "s" : ""} installed
                </p>
              </div>
            </div>
            <span className="text-gray-400">→</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {addons.slice(0, 5).map((addon) => (
              <span
                key={addon.reference}
                className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-xs font-medium"
              >
                {addon.name} ({addon.type})
              </span>
            ))}
            {addons.length > 5 && (
              <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-xs font-medium">
                +{addons.length - 5} more
              </span>
            )}
          </div>
        </Link>
      </div>
    </div>
  );
}
