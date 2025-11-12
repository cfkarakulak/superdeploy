"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ExternalLink, Package, Database } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";

interface App {
  name: string;
  type: string;
  domain: string | null;
  vm: string;
  port: number;
  repo: string;
  owner: string;
}

interface Addon {
  reference: string;
  name: string;
  type: string;
  version: string;
  plan: string;
}

export default function AppOverviewPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;

  const [app, setApp] = useState<App | null>(null);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch app details
        const appResponse = await fetch(`http://localhost:8401/api/apps/${projectName}/list`);
        const appData = await appResponse.json();
        const currentApp = appData.apps.find((a: App) => a.name === appName);
        setApp(currentApp || null);

        // Fetch addons
        const addonsResponse = await fetch(`http://localhost:8401/api/addons/${projectName}/list`);
        const addonsData = await addonsResponse.json();
        setAddons(addonsData.addons || []);
      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    };

    if (projectName && appName) {
      fetchData();
    }
  }, [projectName, appName]);

  return (
    <div>
      <AppHeader />
      
      {loading ? (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-[15px] text-[#8b8b8b]">Loading...</div>
        </div>
      ) : !app ? (
        <div className="alert alert-error">
          <p>Application not found</p>
        </div>
      ) : (
        <>
          <PageHeader
            breadcrumb={{
              label: "Application",
              href: `/project/${projectName}/app/${appName}`
            }}
            title="Overview"
            description={`Application details and configuration for ${appName}`}
          />

      {/* Single Card with Sections */}
      <div className="bg-white rounded-[16px] p-[20px] shadow-[0_0_0_1px_rgba(11,26,38,0.06),0_4px_12px_rgba(0,0,0,0.03),0_1px_3px_rgba(0,0,0,0.04)]">
        {/* Application Info Section */}
        <div className="mb-8">
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Application Info</h2>
          <div className="space-y-3">
            <div className="flex justify-between text-[15px]">
              <span className="text-[#8b8b8b]">Type</span>
              <span className="text-[#0a0a0a] ">{app.type}</span>
            </div>
            <div className="flex justify-between text-[15px]">
              <span className="text-[#8b8b8b]">VM</span>
              <span className="text-[#0a0a0a] ">{app.vm}</span>
            </div>
            <div className="flex justify-between text-[15px]">
              <span className="text-[#8b8b8b]">Port</span>
              <span className="text-[#0a0a0a] ">{app.port}</span>
            </div>
            {app.domain && (
              <div className="flex justify-between text-[15px]">
                <span className="text-[#8b8b8b]">Domain</span>
                <a
                  href={`https://${app.domain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#008545] hover:text-[#006635] flex items-center gap-1"
                >
                  {app.domain}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            )}
            <div className="flex justify-between text-[15px]">
              <span className="text-[#8b8b8b]">Repository</span>
              <a
                href={`https://github.com/${app.owner}/${app.repo}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#008545] hover:text-[#006635] flex items-center gap-1"
              >
                {app.owner}/{app.repo}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-[#e3e8ee] my-6"></div>

        {/* Attached Add-ons Section */}
        <div>
          <h2 className="text-[17px] font-semibold text-[#0a0a0a] mb-4">Attached Add-ons</h2>
          {addons.length > 0 ? (
            <div className="space-y-3">
              {addons.map((addon) => (
                <Link
                  key={addon.reference}
                  href={`/project/${projectName}/addons/${addon.reference}`}
                  className="flex items-center justify-between p-3 rounded hover:bg-[#f7f7f7] transition-all"
                >
                  <div className="flex items-center gap-3">
                    <Database className="w-4 h-4 text-[#8b8b8b]" />
                    <div>
                      <div className="text-[15px]  text-[#0a0a0a]">
                        {addon.type} ({addon.name})
                      </div>
                      <div className="text-[13px] text-[#8b8b8b]">
                        {addon.plan} • v{addon.version}
                      </div>
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-[#8b8b8b]" />
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-[15px] text-[#8b8b8b]">No add-ons attached</p>
          )}
        </div>
      </div>
        </>
      )}
    </div>
  );
}
