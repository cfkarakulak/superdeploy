"use client";

import { useParams } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";
import { Button, Input } from "@/components";

export default function AddonDetailPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const reference = params?.reference as string;

  return (
    <div>
      <AppHeader />
      
      <PageHeader
        breadcrumb={{
          label: "Add-ons",
          href: `/project/${projectName}/addons`
        }}
        title={reference}
        description="Add-on connection details, resource usage, and management options"
      />

      {/* Content */}
      <div className="space-y-6">
        <div className="bg-white rounded-lg p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Connection Info</h2>
          <div className="space-y-3">
            <Input
              label="Host"
              type="text"
              value="localhost"
              disabled
              className="font-mono"
            />
            
            <Input
              label="Port"
              type="text"
              value="5432"
              disabled
              className="font-mono"
            />
            
            <Input
              label="Database"
              type="text"
              value={projectName}
              disabled
              className="font-mono"
            />
          </div>
        </div>

        <div className="bg-white rounded-lg p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Resource Usage</h2>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-[13px] text-[#8b8b8b]">CPU</span>
                <span className="text-[13px]  text-[#0a0a0a]">12%</span>
              </div>
              <div className="w-full bg-[#f7f7f7] rounded-full h-2">
                <div className="bg-[#008545] h-2 rounded-full" style={{ width: "12%" }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-[13px] text-[#8b8b8b]">Memory</span>
                <span className="text-[13px]  text-[#0a0a0a]">45%</span>
              </div>
              <div className="w-full bg-[#f7f7f7] rounded-full h-2">
                <div className="bg-[#008545] h-2 rounded-full" style={{ width: "45%" }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-[13px] text-[#8b8b8b]">Storage</span>
                <span className="text-[13px]  text-[#0a0a0a]">23%</span>
              </div>
              <div className="w-full bg-[#f7f7f7] rounded-full h-2">
                <div className="bg-[#008545] h-2 rounded-full" style={{ width: "23%" }} />
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Quick Actions</h2>
          <div className="flex gap-3">
            <Button>
              Restart
            </Button>
            <Button variant="secondary">
              View Logs
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

