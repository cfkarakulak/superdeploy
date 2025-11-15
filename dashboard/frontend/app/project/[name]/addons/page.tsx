"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";
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
  <div>
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
      <div>
        <div className="bg-red-50 rounded-lg p-4 shadow-sm">
          <p className="text-red-800">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <AppHeader />
      
      <PageHeader
        breadcrumb={{
          label: projectName,
          href: `/project/${projectName}`
        }}
        title="Add-ons"
        description="Manage database, cache, queue services and other infrastructure add-ons"
      />

      {addons.length === 0 ? (
        <div className="bg-white rounded-[16px] p-[32px] text-center shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <p className="text-[15px] text-[#8b8b8b]">No add-ons installed yet</p>
        </div>
      ) : (
        <div className="space-y-4">
          {addons.map((addon) => (
            <div
              key={addon.reference}
              className="bg-white rounded-[16px] p-[32px] pt-[25px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]"
            >
              <div className="flex items-start justify-between mb-5">
                <div>
                  <h3 className="text-[20px] font-semibold text-[#0a0a0a] mb-2">{addon.name}</h3>
                  <div className="flex items-center gap-3">
                    <span className="px-2.5 py-1 bg-[#e0e7ff] text-[#4f46e5] rounded text-[12px] ">
                      {addon.type}
                    </span>
                    <span className="text-[13px] text-[#8b8b8b]">Plan: {addon.plan}</span>
                    <span
                      className={`px-2.5 py-1 rounded text-[12px]  ${
                        addon.status === "running"
                          ? "bg-[#dcfce7] text-[#16a34a]"
                          : "bg-[#ebebeb] text-[#8b8b8b]"
                      }`}
                    >
                      {addon.status}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-[13px]  text-[#8b8b8b] mb-3">
                  Attached Apps ({addon.attachments.length})
                </h4>
                {addon.attachments.length === 0 ? (
                  <p className="text-[13px] text-[#8b8b8b]">
                    Not attached to any apps yet
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {addon.attachments.map((attachment, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-[#dbeafe] text-[#2563eb] rounded-full text-[12px] "
                      >
                        {attachment.app_name}
                        {attachment.as_prefix && (
                          <span className="ml-1">
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
