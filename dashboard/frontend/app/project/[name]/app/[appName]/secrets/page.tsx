"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SecretsRedirectPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  useEffect(() => {
    if (projectName && appName) {
      router.replace(`/project/${projectName}/app/${appName}/secrets/${appName}`);
    }
  }, [projectName, appName, router]);

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-[15px] text-[#8b8b8b]">Redirecting...</div>
    </div>
  );
}

