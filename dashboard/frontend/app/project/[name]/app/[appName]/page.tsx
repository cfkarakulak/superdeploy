"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

export default function AppDetailPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  return (
    <div className="max-w-[960px] mx-auto py-8 px-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-6">
        <Link
          href={`/project/${projectName}`}
          className="text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-900">
            Projects
          </Link>
          <span>/</span>
          <Link
            href={`/project/${projectName}`}
            className="hover:text-gray-900"
          >
            {projectName}
          </Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{appName}</span>
        </div>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-2">{appName}</h1>
        <p className="text-gray-600">Application management</p>
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-3 gap-4">
        <Link
          href={`/project/${projectName}/config-vars/${appName}`}
          className="bg-white shadow-sm rounded-lg p-6 hover:shadow-md transition-shadow"
        >
          <div className="font-semibold text-lg mb-1">Config Vars</div>
          <div className="text-sm text-gray-500">Manage environment variables</div>
        </Link>

        <Link
          href={`/project/${projectName}/app/${appName}/github`}
          className="bg-white shadow-sm rounded-lg p-6 hover:shadow-md transition-shadow"
        >
          <div className="font-semibold text-lg mb-1">GitHub</div>
          <div className="text-sm text-gray-500">Actions & workflows</div>
        </Link>

        <Link
          href={`/project/${projectName}/app/${appName}/monitoring`}
          className="bg-white shadow-sm rounded-lg p-6 hover:shadow-md transition-shadow"
        >
          <div className="font-semibold text-lg mb-1">Monitoring</div>
          <div className="text-sm text-gray-500">Containers & logs</div>
        </Link>
      </div>
    </div>
  );
}
