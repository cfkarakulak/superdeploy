"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";

interface RefreshButtonProps {
  projectName?: string;
  onRefresh: () => void | Promise<void>;
  syncFirst?: boolean; // If true, call sync endpoint before onRefresh
  className?: string;
}

export function RefreshButton({ 
  projectName, 
  onRefresh, 
  syncFirst = false,
  className = "" 
}: RefreshButtonProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    if (isRefreshing) return;
    
    setIsRefreshing(true);
    
    try {
      // If syncFirst is true and projectName is provided, call sync endpoint first
      if (syncFirst && projectName) {
        const response = await fetch(`http://localhost:8401/api/projects/${projectName}/sync`, {
          method: "POST",
        });

        const result = await response.json();
        
        if (!response.ok) {
          console.error("Sync failed:", result.detail || result);
          return;
        }

        console.log("Sync complete:", result.message);
      }

      // Call the refresh callback
      await onRefresh();
    } catch (error) {
      console.error("Failed to refresh:", error);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <button
      onClick={handleRefresh}
      disabled={isRefreshing}
      className={`p-1.5 rounded-md hover:bg-[#f6f8fa] transition-colors disabled:opacity-50 ${className}`}
      title="Refresh"
    >
      <RefreshCw 
        className={`w-4 h-4 text-[#8b8b8b] ${isRefreshing ? "animate-spin" : ""}`} 
      />
    </button>
  );
}

