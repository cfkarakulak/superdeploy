"use client";

import { useParams } from "next/navigation";
import { ProjectHeader, PageHeader } from "@/components";
import { Rocket, Package, Clock } from "lucide-react";

export default function ProjectDeploymentPage() {
  const params = useParams();
  const projectName = params?.name as string;

  return (
    <div>
      <ProjectHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Projects", href: "/" },
            { label: projectName, href: `/project/${projectName}` },
          ]}
          menuLabel="Deployment"
          title="Deployment Management"
        />

        {/* Deployment Overview */}
        <div className="mb-8">
          <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
            <Rocket className="w-4 h-4" />
            Deployment Overview
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Total Apps */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-50 rounded-lg">
                    <Package className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Total Apps</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">-</span>
                <span className="text-[16px] text-[#8b8b8b]">apps</span>
              </div>
            </div>

            {/* Deployed Apps */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-50 rounded-lg">
                    <Rocket className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Deployed Apps</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[26px] text-[#0a0a0a]">-</span>
                <span className="text-[16px] text-[#8b8b8b]">running</span>
              </div>
            </div>

            {/* Last Deployment */}
            <div className="p-5 border border-[#e3e8ee] rounded-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-50 rounded-lg">
                    <Clock className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <h3 className="text-[13px] text-[#8b8b8b] font-light">Last Deployment</h3>
                  </div>
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[16px] text-[#8b8b8b]">-</span>
              </div>
            </div>
          </div>
        </div>

        {/* Deployment History */}
        <div className="mb-8">
          <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[8px] font-light">
            <Clock className="w-4 h-4" />
            Recent Deployments
          </h2>
          <div className="border border-[#e3e8ee] rounded-lg p-16 text-center">
            <div className="w-16 h-16 bg-[#f6f8fa] rounded-full flex items-center justify-center mx-auto mb-4">
              <Clock className="w-6 h-6 text-[#8b8b8b]" />
            </div>
            <p className="text-[14px] text-[#0a0a0a] mb-2">No deployment history</p>
            <p className="text-[13px] text-[#8b8b8b]">
              Deploy individual apps from their respective pages
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

