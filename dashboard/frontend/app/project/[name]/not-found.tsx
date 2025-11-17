"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components";

export default function ProjectNotFound() {
  const router = useRouter();

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center max-w-md px-6">
        <svg
          className="w-6 h-6 text-[#374046] mx-auto mb-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776"
          />
        </svg>
        
        <h3 className="text-[17px] text-[#111] mb-[2px]">
          Project Not Found
        </h3>
        
        <p className="text-[13px] text-[#8b8b8b] leading-relaxed font-light tracking-[0.01em] mb-6">
          The project you're looking for doesn't exist
          <br />
          or you don't have access to it.
        </p>

        <Button onClick={() => router.push("/")}>
          Go to Dashboard
        </Button>
      </div>
    </div>
  );
}

