"use client";

import { useDeploymentLog } from "@/contexts/DeploymentLogContext";
import { useEffect, useRef, useState } from "react";
import { X, Minimize2, Maximize2 } from "lucide-react";

export default function GlobalDeploymentLog() {
  const { logs, isVisible, isDeploying, title, hide } = useDeploymentLog();
  const logEndRef = useRef<HTMLDivElement>(null);
  const [isMinimized, setIsMinimized] = useState(false);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (logEndRef.current && !isMinimized) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, isMinimized]);

  if (!isVisible) return null;

  return (
    <div
      className={`fixed z-9999 bg-[#1a1a1a] border border-[#333] shadow-2xl transition-all duration-300 ${
        isMinimized ? "bottom-4 right-4 w-[300px]" : "bottom-4 right-4 w-[600px] h-[400px]"
      }`}
      style={{ borderRadius: "12px" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#333]">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isDeploying ? "bg-[#0ea5e9] animate-pulse" : "bg-[#22c55e]"}`} />
          <span className="text-[13px] font-medium text-white">
            {isDeploying ? `${title}...` : `${title} Complete`}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1.5 hover:bg-[#333] rounded-md transition-colors cursor-pointer"
            title={isMinimized ? "Maximize" : "Minimize"}
          >
            {isMinimized ? (
              <Maximize2 className="w-3.5 h-3.5 text-[#8b8b8b]" />
            ) : (
              <Minimize2 className="w-3.5 h-3.5 text-[#8b8b8b]" />
            )}
          </button>
          <button
            onClick={hide}
            className="p-1.5 hover:bg-[#333] rounded-md transition-colors cursor-pointer"
            title="Close"
          >
            <X className="w-3.5 h-3.5 text-[#8b8b8b]" />
          </button>
        </div>
      </div>

      {/* Logs */}
      {!isMinimized && (
        <div className="overflow-y-auto h-[calc(100%-52px)] p-3 font-mono text-[11px] leading-relaxed scrollbar-dark terminal-selection">
          {logs.length === 0 ? (
            <div className="text-[#666] text-center py-8">No logs yet...</div>
          ) : (
            logs.map((log, idx) => {
              // Determine log color based on content
              let colorClass = "text-[#d4d4d4]"; // Default light gray
              
              // Check for tree structure with checkmarks (debug/info lines)
              if ((log.includes("├──") || log.includes("└──")) && log.includes("✓")) {
                colorClass = "text-[#6b7280]"; // Soft gray for debug lines
              } else if (log.includes("✓") || log.includes("✅")) {
                colorClass = "text-[#10b981]"; // Green for main success
              } else if (log.includes("✗") || log.includes("❌") || log.includes("Error") || log.includes("error")) {
                colorClass = "text-[#ef4444]"; // Red
              } else if (log.includes("⚠") || log.includes("Warning") || log.includes("warning")) {
                colorClass = "text-[#f59e0b]"; // Amber/Orange
              } else if (log.includes("▶") || log.includes("🚀")) {
                colorClass = "text-[#f97316]"; // Orange (for play icons)
              } else if (log.includes("└──") || log.includes("├──") || log.includes("│")) {
                colorClass = "text-[#6b7280]"; // Soft gray for tree characters
              } else if (log.includes("💾") || log.includes("🔐") || log.includes("📝")) {
                colorClass = "text-[#60a5fa]"; // Blue for info icons
              } else if (log.includes("ℹ️") || log.includes("INFO")) {
                colorClass = "text-[#3b82f6]"; // Blue
              }
              
              return (
                <div key={idx} className={`mb-1 ${colorClass}`}>
                  {log}
                </div>
              );
            })
          )}
          <div ref={logEndRef} />
        </div>
      )}

      {isMinimized && (
        <div className="px-4 py-2 text-[11px] text-[#8b8b8b]">
          {logs.length} log entries
        </div>
      )}
    </div>
  );
}

