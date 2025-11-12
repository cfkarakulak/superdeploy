"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface Addon {
  name: string;
  type: string;
  category: string;
  reference: string;
  plan: string;
  attachments: Array<{
    app_name: string;
    as_prefix: string | null;
  }>;
  status: string;
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
      <div className="w-[80px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Header Skeleton
const AddonsHeaderSkeleton = () => (
  <div className="mb-6">
    <div className="w-[100px] h-[28px] bg-[#e3e8ee] rounded-md mb-2 skeleton-animated" />
    <div className="w-[320px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
  </div>
);

// Addon Card Skeleton
const AddonCardSkeleton = () => (
  <div className="bg-white rounded-lg p-6 shadow-sm">
    <div className="flex items-start justify-between mb-4">
      <div className="flex-1">
        <div className="w-[180px] h-[24px] bg-[#e3e8ee] rounded-md mb-3 skeleton-animated" />
        <div className="flex items-center gap-3">
          <div className="w-[80px] h-[20px] bg-[#e3e8ee] rounded skeleton-animated" />
          <div className="w-[100px] h-[20px] bg-[#e3e8ee] rounded skeleton-animated" />
          <div className="w-[70px] h-[20px] bg-[#e3e8ee] rounded skeleton-animated" />
        </div>
      </div>
    </div>
    <div>
      <div className="w-[130px] h-[16px] bg-[#e3e8ee] rounded mb-2 skeleton-animated" />
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 2 }, (_, i) => (
          <div key={`attachment-skeleton-${i}`} className="w-[100px] h-[24px] bg-[#e3e8ee] rounded-full skeleton-animated" />
        ))}
      </div>
    </div>
  </div>
);

// Full Page Skeleton
const AddonsPageSkeleton = () => (
  <div className="max-w-[960px] mx-auto py-8 px-6">
    <BreadcrumbSkeleton />
    <AddonsHeaderSkeleton />
    <div className="grid gap-4">
      {Array.from({ length: 3 }, (_, i) => (
        <AddonCardSkeleton key={`addon-skeleton-${i}`} />
      ))}
    </div>
  </div>
);

export default function AddonsPage() {
  const params = useParams();
  const projectName = params?.name as string;

  const [addons, setAddons] = useState<Addon[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAddons = async () => {
    try {
      const response = await fetch(
        `http://localhost:8401/api/addons/${projectName}/list`
      );
      if (!response.ok) throw new Error("Failed to fetch addons");
      const data = await response.json();
      setAddons(data.addons || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectName) {
      fetchAddons();
    }
  }, [projectName]);

  if (loading) {
    return <AddonsPageSkeleton />;
  }

  if (error) {
    return (
      <div className="max-w-[960px] mx-auto py-8 px-6">
        <div className="bg-red-50 rounded-lg p-4 shadow-sm">
          <p className="text-red-800">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[960px] mx-auto py-8 px-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-6">
        <Link href={`/project/${projectName}`} className="text-gray-500 hover:text-gray-900">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-900">
            Projects
          </Link>
          <span>/</span>
          <Link href={`/project/${projectName}`} className="hover:text-gray-900">
            {projectName}
          </Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">Addons</span>
        </div>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">Addons</h1>
        <p className="text-gray-600">
          Installed database, cache, and queue services
        </p>
      </div>

      {addons.length === 0 ? (
        <div className="bg-white shadow-sm rounded-lg p-8 text-center">
          <p className="text-gray-600">No addons installed yet</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {addons.map((addon) => (
            <div
              key={addon.reference}
              className="bg-white rounded-lg p-6 shadow-sm"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-bold mb-1">{addon.name}</h3>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium">
                      {addon.type}
                    </span>
                    <span className="text-gray-600">Plan: {addon.plan}</span>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        addon.status === "running"
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {addon.status}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-2">
                  Attached Apps ({addon.attachments.length})
                </h4>
                {addon.attachments.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    Not attached to any apps yet
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {addon.attachments.map((attachment, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium"
                      >
                        {attachment.app_name}
                        {attachment.as_prefix && (
                          <span className="ml-1 text-blue-600">
                            (as {attachment.as_prefix})
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
