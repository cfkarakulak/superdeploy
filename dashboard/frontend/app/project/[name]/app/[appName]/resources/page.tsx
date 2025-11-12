"use client";

import { useParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";

export default function ResourcesPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  return (
    <div>
      <AppHeader />
      
      <PageHeader
        breadcrumb={{
          label: "Resources",
          href: `/project/${projectName}/app/${appName}/resources`
        }}
        title="Dynos & Add-ons"
        description={`Manage compute resources and scaling configuration for ${appName}`}
      />

      {/* Single Card with Sections */}
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0_0_0_1px_rgba(11,26,38,0.06),0_4px_12px_rgba(0,0,0,0.03),0_1px_3px_rgba(0,0,0,0.04)]">
        <div className="mb-8">
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Dynos</h2>
          <p className="text-[15px] text-[#525252]">No dynos configured yet</p>
        </div>

        <div className="border-t border-[#e3e8ee] my-6"></div>

        <div>
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Add-ons</h2>
          <p className="text-[15px] text-[#525252]">No add-ons attached</p>
        </div>
      </div>
    </div>
  );
}

