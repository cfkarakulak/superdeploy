"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components";

export default function NotFound() {
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
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
        
        <h3 className="text-[17px] text-[#111] mb-[2px]">
          Page Not Found
        </h3>
        
        <p className="text-[13px] text-[#8b8b8b] leading-relaxed font-light tracking-[0.01em] mb-6">
          The page you're looking for doesn't exist or has been moved.
        </p>

        <Button onClick={() => router.push("/")}>
          Go to Dashboard
        </Button>
      </div>
    </div>
  );
}

