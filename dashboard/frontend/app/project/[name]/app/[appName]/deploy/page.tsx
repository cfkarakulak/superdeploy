"use client";

import { useParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";

export default function DeployPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  return (
    <div>
      <AppHeader />
      
      <PageHeader
        breadcrumb={{
          label: "Deploy",
          href: `/project/${projectName}/app/${appName}/deploy`
        }}
        title="Deployment"
        description={`Configure automated and manual deployments for ${appName}`}
      />

      {/* Coming Soon Placeholder */}
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0_0_0_1px_rgba(11,26,38,0.06),0_4px_12px_rgba(0,0,0,0.03),0_1px_3px_rgba(0,0,0,0.04)]">
        <div className="flex flex-col items-center justify-center py-20">
          <div className="text-center">
            <h2 className="text-[24px] font-semibold text-[#0a0a0a] mb-3">Coming Soon</h2>
            <p className="text-[15px] text-[#8b8b8b]">
              Deployment configuration will be available soon.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

