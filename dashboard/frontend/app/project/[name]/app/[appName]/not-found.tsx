"use client";

import { useRouter, useParams } from "next/navigation";
import { PackageX } from "lucide-react";
import { Button } from "@/components";

export default function AppNotFound() {
  const router = useRouter();
  const params = useParams();
  const projectName = params?.name as string;

  return (
    <div className="min-h-screen bg-[#fafbfc] flex items-center justify-center px-4">
      <div className="text-center">
        <PackageX className="w-12 h-12 text-[#ef4444] mx-auto mb-6" strokeWidth={1.5} />
        
        <h1 className="text-[18px] text-[#222] font-normal mb-2">
          Application Not Found
        </h1>
        
        <p className="text-[13px] text-[#8b8b8b] font-light tracking-[0.03em] mb-8 max-w-md mx-auto">
          The application you're looking for doesn't exist in this project.
        </p>

        <div className="flex items-center justify-center gap-3">
          <Button
            variant="ghost"
            size="default"
            onClick={() => router.back()}
          >
            Go Back
          </Button>
          <Button
            variant="default"
            size="default"
            onClick={() => router.push(`/project/${projectName}`)}
          >
            View Project
          </Button>
        </div>
      </div>
    </div>
  );
}

