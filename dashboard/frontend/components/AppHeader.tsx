"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import ProjectSelector from "./ProjectSelector";

interface AppDetails {
  name: string;
  url?: string;
  port?: number;
}

export default function AppHeader() {
  const params = useParams();
  const pathname = usePathname();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  const [appDetails, setAppDetails] = useState<AppDetails | null>(null);

  useEffect(() => {
    if (projectName && appName) {
      // Fetch app details to get URL
      fetch(`http://localhost:8401/api/projects/${projectName}`)
        .then((res) => res.json())
        .then((data) => {
          const apps = data.apps_config || {};
          const app = apps[appName];
          if (app) {
            // Get URL from app config or construct from VM IP + port
            let appUrl = app.url;
            const appPort = app.processes?.web?.port || app.port;
            const vmRole = app.vm || 'app';
            
            // Get VMs from vms array (normalized data)
            const vmsArray = data.vms || [];
            // Find VM by role
            const vm = vmsArray.find((v: any) => v.role === vmRole);
            
            if (!appUrl && vm?.external_ip && appPort) {
              appUrl = `http://${vm.external_ip}:${appPort}`;
            }
            
            setAppDetails({ name: appName, url: appUrl, port: appPort });
          }
        })
        .catch((err) => console.error('Failed to fetch app details:', err));
    }
  }, [projectName, appName]);

  const menuItems = [
    { label: "Overview", href: `/project/${projectName}/app/${appName}` },
    { label: "Resources", href: `/project/${projectName}/app/${appName}/resources` },
    { label: "Deploy", href: `/project/${projectName}/app/${appName}/deploy` },
    { label: "Actions", href: `/project/${projectName}/app/${appName}/actions` },
    { label: "Secrets", href: `/project/${projectName}/app/${appName}/secrets` },
    { label: "Aliases", href: `/project/${projectName}/app/${appName}/aliases` },
    { label: "Logs", href: `/project/${projectName}/app/${appName}/logs` },
  ];

  const isActive = (href: string) => {
    if (href === `/project/${projectName}/app/${appName}`) {
      return pathname === href;
    }
    
    if (href === `/project/${projectName}/app/${appName}/resources`) {
      return pathname?.startsWith(`/project/${projectName}/app/${appName}/addons/`) || pathname?.startsWith(href);
    }
    
    if (href === `/project/${projectName}/app/${appName}/secrets`) {
      return pathname?.startsWith(href);
    }
    
    if (href === `/project/${projectName}/app/${appName}/aliases`) {
      return pathname?.startsWith(href);
    }
    
    if (href === `/project/${projectName}/app/${appName}/actions`) {
      return pathname?.startsWith(href) || pathname?.startsWith(`/project/${projectName}/app/${appName}/github`);
    }
    
    return pathname?.startsWith(href);
  };

  return (
    <div>
      {/* Top Bar */}
      <div className="mb-6">
        <div className="flex items-center gap-4">
          <ProjectSelector currentProjectName={projectName} currentAppName={appName} />
          
          {/* View Site Link */}
          {appDetails?.url && (
            <a
              href={appDetails.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] text-[#8b8b8b] hover:text-[#0a0a0a] transition-colors border border-[#eef2f5] rounded-lg hover:border-[#d1d5da]"
              title={`Open ${appName} in new tab`}
            >
              <span>View Site</span>
              <ExternalLink className="w-3 h-3" strokeWidth={2} />
            </a>
          )}
        </div>
      </div>

      {/* Menu */}
      {appName && (
        <div className="flex items-center gap-5 mb-5">
          {menuItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`text-[14px] font-normal transition-colors ${
                isActive(item.href)
                  ? "text-[#0a0a0a]"
                  : "text-[#8b8b8b] hover:text-[#0a0a0a]"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
