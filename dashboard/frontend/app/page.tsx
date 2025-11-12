"use client";

import SimpleHeader from "@/components/SimpleHeader";
import PageHeader from "@/components/PageHeader";

export default function HomePage() {
  return (
    <div>
      <SimpleHeader />
      
      <PageHeader
        title="Projects"
        description="Select a project from the dropdown above to get started"
      />
      
      <div className="text-center py-20">
        <p className="text-[15px] text-[#8b8b8b]">No project selected</p>
      </div>
    </div>
  );
}
