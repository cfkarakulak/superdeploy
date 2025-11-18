"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import ProjectSelector from "./ProjectSelector";

export default function ProjectHeader() {
  const params = useParams();
  const pathname = usePathname();
  const projectName = params?.name as string;

  const menuItems = [
    { label: "Configuration", href: `/project/${projectName}` },
    { label: "Apps", href: `/project/${projectName}/apps` },
    { label: "Addons", href: `/project/${projectName}/addons` },
    { label: "Deployment", href: `/project/${projectName}/deployment` },
    { label: "Settings", href: `/project/${projectName}/settings` },
  ];

  const isActive = (href: string) => {
    if (href === `/project/${projectName}`) {
      return pathname === href;
    }
    return pathname?.startsWith(href);
  };

  return (
    <div>
      {/* Top Bar */}
      <div className="mb-6">
        <div className="flex items-center gap-4">
          <ProjectSelector currentProjectName={projectName} />
        </div>
      </div>

      {/* Menu */}
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
    </div>
  );
}

