"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";

interface RefreshButtonProps {
  projectName: string;
  onRefreshComplete?: () => void;
  className?: string;
}

export function RefreshButton({ projectName, onRefreshComplete, className = "" }: RefreshButtonProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    if (isRefreshing) return;
    
    setIsRefreshing(true);
    
    try {
      const response = await fetch(`http://localhost:8401/api/projects/${projectName}/sync`, {
        method: "POST",
      });

      if (!response.ok) {
        const error = await response.json();
        console.error("Sync failed:", error);
      }

      // Call the callback to refresh the page data
      if (onRefreshComplete) {
        onRefreshComplete();
      }
    } catch (error) {
      console.error("Failed to sync:", error);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <button
      onClick={handleRefresh}
      disabled={isRefreshing}
      className={`p-1.5 rounded-md hover:bg-[#f6f8fa] transition-colors disabled:opacity-50 ${className}`}
      title="Sync from VMs"
    >
      <RefreshCw 
        className={`w-4 h-4 text-[#8b8b8b] ${isRefreshing ? "animate-spin" : ""}`} 
      />
    </button>
  );
}

