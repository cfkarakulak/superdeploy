"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import ProjectSelector from "./ProjectSelector";

export default function AppHeader() {
  const params = useParams();
  const pathname = usePathname();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const menuItems = [
    { label: "Overview", href: `/project/${projectName}/app/${appName}` },
    { label: "Resources", href: `/project/${projectName}/app/${appName}/resources` },
    { label: "Deploy", href: `/project/${projectName}/app/${appName}/deploy` },
    { label: "Actions", href: `/project/${projectName}/app/${appName}/github` },
    { label: "Secrets", href: `/project/${projectName}/app/${appName}/secrets` },
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
    
    if (href === `/project/${projectName}/app/${appName}/github`) {
      return pathname?.startsWith(href);
    }
    
    return pathname?.startsWith(href);
  };

  return (
    <div>
      {/* Top Bar */}
      <div className="mb-6">
        <div className="flex items-center gap-4">
          <ProjectSelector currentProjectName={projectName} currentAppName={appName} />
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
