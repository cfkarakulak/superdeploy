"use client";

import { useParams } from "next/navigation";
import { AppHeader, PageHeader } from "@/components";

export default function ResourcesPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  return (
    <div>
      <AppHeader />
      
      {/* Single Card with Sections */}
      <div className="bg-white rounded-[16px] p-[20px] pt-[25px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
            <PageHeader
          breadcrumb={{
            label: "Resources",
            href: `/project/${projectName}/app/${appName}/resources`
          }}
          title="Dynos & Add-ons"
          description={`Manage compute resources and scaling configuration for ${appName}`}
        />

        <div className="mb-8">
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Dynos</h2>
          <p className="text-[15px] text-[#8b8b8b]">No dynos configured yet</p>
        </div>

        <div className="border-t border-[#e3e8ee] my-6"></div>

        <div>
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Add-ons</h2>
          <p className="text-[15px] text-[#8b8b8b]">No add-ons attached</p>
        </div>
      </div>
    </div>
  );
}

