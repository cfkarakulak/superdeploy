"use client";

import Link from "next/link";

interface PageHeaderProps {
  breadcrumb?: {
    label: string;
    href: string;
  };
  title: string;
  description: string;
}

export default function PageHeader({ breadcrumb, title, description }: PageHeaderProps) {
  return (
    <div className="mb-10">
      {/* Breadcrumb - Küçük üst link */}
      {breadcrumb && (
        <nav aria-label="Breadcrumb">
          <Link 
            href={breadcrumb.href}
            className="text-[14px] font-semibold text-[#37948c] hover:text-[#2d7a73] transition-colors"
          >
            {breadcrumb.label}
          </Link>
        </nav>
      )}

      <h1 
        className="text-[24px] leading-[30px] font-bold text-[#0a0a0a] mb-2"
      >
        {title}
      </h1>

    </div>
  );
}
