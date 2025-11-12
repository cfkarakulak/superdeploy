"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import {
  Activity,
  Rocket,
  GitBranch,
  Settings,
  Package,
  RefreshCw,
  ChevronRight,
  Filter
} from "lucide-react";
import { Button } from "@/components/Button";

interface ActivityItem {
  id: number;
  type: string;
  actor: string;
  app_name: string | null;
  metadata: any;
  timestamp: string;
}

interface ActivityFeedProps {
  projectName: string;
  limit?: number;
  showFilters?: boolean;
}

const API_URL = "http://localhost:8401";

export function ActivityFeed({ 
  projectName, 
  limit = 10,
  showFilters = false 
}: ActivityFeedProps) {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [appFilter, setAppFilter] = useState<string>("all");

  useEffect(() => {
    fetchActivities();
  }, [projectName, typeFilter, appFilter]);

  const fetchActivities = async () => {
    setLoading(true);
    
    try {
      let url = `${API_URL}/api/activity/${projectName}?limit=${limit}`;
      
      if (typeFilter !== "all") {
        url += `&type_filter=${typeFilter}`;
      }
      
      if (appFilter !== "all") {
        url += `&app_filter=${appFilter}`;
      }
      
      const response = await fetch(url);
      const data = await response.json();
      
      setActivities(data);
    } catch (error) {
      console.error("Failed to fetch activities:", error);
    } finally {
      setLoading(false);
    }
  };

  const getActivityIcon = (type: string) => {
    switch (type) {
      case "deploy":
        return <Rocket className="w-4 h-4 text-blue-600" />;
      case "scale":
        return <GitBranch className="w-4 h-4 text-purple-600" />;
      case "config":
        return <Settings className="w-4 h-4 text-green-600" />;
      case "addon":
        return <Package className="w-4 h-4 text-orange-600" />;
      case "restart":
        return <RefreshCw className="w-4 h-4 text-yellow-600" />;
      case "rollback":
        return <Activity className="w-4 h-4 text-red-600" />;
      default:
        return <Activity className="w-4 h-4 text-gray-600" />;
    }
  };

  const formatActivityMessage = (activity: ActivityItem) => {
    const { type, actor, app_name, metadata } = activity;

    switch (type) {
      case "deploy":
        return (
          <span>
            <strong>{actor}</strong> deployed <strong>{app_name}</strong> 
            {metadata?.version && ` v${metadata.version}`}
            {metadata?.status === "success" && " successfully"}
          </span>
        );
      
      case "scale":
        return (
          <span>
            <strong>{actor}</strong> scaled <strong>{app_name}</strong>
            {metadata?.process_type && ` ${metadata.process_type}`}
            {` from ${metadata?.from_replicas || 0} to ${metadata?.to_replicas || 0} replicas`}
          </span>
        );
      
      case "config":
        return (
          <span>
            <strong>{actor}</strong> {metadata?.action === "set" ? "set" : "deleted"}
            {" config var "}<strong>{metadata?.key}</strong>
            {app_name && ` for ${app_name}`}
          </span>
        );
      
      case "addon":
        const addonAction = metadata?.action || "managed";
        return (
          <span>
            <strong>{actor}</strong> {addonAction}
            {" addon "}<strong>{metadata?.addon_name}</strong>
            {metadata?.addon_type && ` (${metadata.addon_type})`}
            {app_name && addonAction === "attach" && ` to ${app_name}`}
          </span>
        );
      
      case "restart":
        return (
          <span>
            <strong>{actor}</strong> restarted
            {metadata?.container_name ? ` container ${metadata.container_name}` : ` ${app_name}`}
          </span>
        );
      
      case "rollback":
        return (
          <span>
            <strong>{actor}</strong> rolled back <strong>{app_name}</strong>
            {metadata?.to_version && ` to v${metadata.to_version}`}
          </span>
        );
      
      default:
        return (
          <span>
            <strong>{actor}</strong> performed <strong>{type}</strong> on {app_name || "project"}
          </span>
        );
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
  };

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5" />
          <h3 className="font-semibold">Recent Activity</h3>
        </div>
        <div className="text-center py-8 text-gray-500">
          Loading activities...
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          <h3 className="font-semibold">Recent Activity</h3>
        </div>
        
        {showFilters && (
          <div className="flex gap-2">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            >
              <option value="all">All Types</option>
              <option value="deploy">Deploys</option>
              <option value="scale">Scaling</option>
              <option value="config">Config</option>
              <option value="addon">Addons</option>
              <option value="restart">Restarts</option>
            </select>
          </div>
        )}
      </div>

      {activities.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No activity yet
        </div>
      ) : (
        <div className="space-y-3">
          {activities.map((activity) => (
            <div
              key={activity.id}
              className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <div className="mt-1">
                {getActivityIcon(activity.type)}
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="text-sm">
                  {formatActivityMessage(activity)}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {formatTimestamp(activity.timestamp)}
                </div>
              </div>
              
              {activity.metadata && Object.keys(activity.metadata).length > 0 && (
                <button className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                  <ChevronRight className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      
      {activities.length >= limit && (
        <div className="mt-4 text-center">
          <Button variant="outline" size="sm">
            View All Activity
          </Button>
        </div>
      )}
    </Card>
  );
}

