"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface BreadcrumbItem {
  label: string;
  href: string;
}

interface PageHeaderProps {
  breadcrumb?: BreadcrumbItem;
  breadcrumbs?: BreadcrumbItem[];
  title: string;
  description?: string;
}

export default function PageHeader({ breadcrumb, breadcrumbs, title, description }: PageHeaderProps) {
  // Convert single breadcrumb to array for consistent handling
  const crumbs = breadcrumbs || (breadcrumb ? [breadcrumb] : []);

  return (
    <div className="mb-10">
      {/* Title */}
      <h1 className="text-[27px] leading-[32px] text-black mb-1">
        {title}
      </h1>

      {/* Breadcrumb with back arrow */}
      {crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="flex items-center gap-2">
          <Link 
            href={crumbs[0].href}
            className="flex items-center gap-2 text-[13px] tracking-[0.03em] font-light text-[#888] hover:text-[#0a0a0a] no-underline transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>{crumbs[0].label}</span>
          </Link>
          
          {/* Additional breadcrumb levels */}
          {crumbs.slice(1).map((crumb, index) => (
            <div key={index} className="flex items-center gap-2">
              <span className="text-[#6a6d77]">›</span>
              <Link 
                href={crumb.href}
                className="text-[13px] tracking-[0.03em] font-light text-[#888] hover:text-[#0a0a0a] no-underline transition-colors"
              >
                {crumb.label}
              </Link>
            </div>
          ))}
          
          {/* Current page */}
          <span className="text-[#6a6d77]">›</span>
          <span className="text-[13px] tracking-[0.02em] text-[#0a0a0a] font-normal">{title}</span>
        </nav>
      )}
    </div>
  );
}
