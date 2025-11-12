"use client";

import { useParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";

export default function ActivityPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  return (
    <div>
      <AppHeader />
      
      <PageHeader
        breadcrumbs={[
          { label: "Projects", href: "/" },
          { label: projectName, href: `/project/${projectName}` },
          { label: "Apps", href: `/project/${projectName}` },
          { label: appName, href: `/project/${projectName}/app/${appName}` },
          { label: "Activity", href: `/project/${projectName}/app/${appName}/activity` }
        ]}
        title="Activity"
        description={`Recent deployment events and activity logs for ${appName}`}
      />

      {/* Content */}
      <div className="space-y-3">
        <div className="bg-white rounded-lg p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex items-start gap-4">
            <div className="w-2 h-2 bg-[#008545] rounded-full mt-2" />
            <div className="flex-1">
              <p className="text-[15px] text-[#0a0a0a]  mb-1">
                Application deployed
              </p>
              <p className="text-[13px] text-[#8b8b8b]">2 hours ago</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex items-start gap-4">
            <div className="w-2 h-2 bg-[#6366f1] rounded-full mt-2" />
            <div className="flex-1">
              <p className="text-[15px] text-[#0a0a0a]  mb-1">
                Configuration updated
              </p>
              <p className="text-[13px] text-[#8b8b8b]">5 hours ago</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex items-start gap-4">
            <div className="w-2 h-2 bg-[#8b8b8b] rounded-full mt-2" />
            <div className="flex-1">
              <p className="text-[15px] text-[#0a0a0a]  mb-1">
                Application created
              </p>
              <p className="text-[13px] text-[#8b8b8b]">1 day ago</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

