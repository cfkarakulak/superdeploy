"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import ProjectSelector from "./ProjectSelector";

export default function OrchestratorHeader() {
  const pathname = usePathname();

  const menuItems = [
    { label: "Configuration", href: "/infrastructure/orchestrator" },
    { label: "Addons", href: "/infrastructure/orchestrator/addons" },
    { label: "Logs", href: "/infrastructure/orchestrator/logs" },
    { label: "Settings", href: "/infrastructure/orchestrator/settings" },
  ];

  const isActive = (href: string) => {
    if (href === "/infrastructure/orchestrator") {
      return pathname === href;
    }
    return pathname?.startsWith(href);
  };

  return (
    <div>
      {/* Top Bar */}
      <div className="mb-6">
        <div className="flex items-center gap-4">
          <ProjectSelector currentProjectName="orchestrator" />
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

