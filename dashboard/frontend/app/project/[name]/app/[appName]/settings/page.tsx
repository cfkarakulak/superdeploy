"use client";

import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";

export default function SettingsPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  return (
    <div>
      <AppHeader />
      
      {/* Coming Soon Placeholder */}
      <div className="bg-white rounded-[16px] p-[20px] pt-[25px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumb={{
            label: "Settings",
            href: `/project/${projectName}/app/${appName}/settings`
          }}
          title="Application Settings"
          description={`Configure application options and preferences for ${appName}`}
        />

        <div className="flex flex-col items-center justify-center py-20">
          <div className="text-center">
            <h2 className="text-[24px] font-semibold text-[#0a0a0a] mb-3">Coming Soon</h2>
            <p className="text-[15px] text-[#8b8b8b]">
              Application settings will be available soon.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
