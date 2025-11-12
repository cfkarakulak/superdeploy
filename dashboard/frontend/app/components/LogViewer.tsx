"use client";

import { useState, useEffect, useRef } from "react";
import { Card } from "@/components/Card";
import { Button } from "@/components/Button";
import { 
  X, 
  Download, 
  Search, 
  AlertCircle, 
  Info,
  ChevronDown,
  Pause,
  Play
} from "lucide-react";

interface LogViewerProps {
  projectName: string;
  containerName: string;
  onClose?: () => void;
}

const API_URL = "http://localhost:8401";

export function LogViewer({ projectName, containerName, onClose }: LogViewerProps) {
  const [logs, setLogs] = useState<Array<{type: string, message: string}>>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!isPaused) {
      connectToLogs();
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [projectName, containerName, isPaused]);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const connectToLogs = () => {
    const eventSource = new EventSource(
      `${API_URL}/api/containers/${projectName}/containers/${containerName}/logs?tail=100`
    );

    eventSource.onopen = () => {
      setIsConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLogs((prev) => [...prev, data]);
      } catch (error) {
        console.error("Failed to parse log:", error);
      }
    };

    eventSource.onerror = (error) => {
      console.error("EventSource error:", error);
      setIsConnected(false);
      eventSource.close();
      
      // Retry connection after 5 seconds if not paused
      if (!isPaused) {
        setTimeout(() => {
          connectToLogs();
        }, 5000);
      }
    };

    eventSourceRef.current = eventSource;
  };

  const handlePauseResume = () => {
    if (isPaused) {
      // Resume
      setIsPaused(false);
    } else {
      // Pause
      setIsPaused(true);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        setIsConnected(false);
      }
    }
  };

  const handleDownload = () => {
    const logText = filteredLogs
      .map((log) => `[${log.type}] ${log.message}`)
      .join("\n");

    const blob = new Blob([logText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${containerName}-logs.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearLogs = () => {
    setLogs([]);
  };

  const filteredLogs = logs.filter((log) => {
    // Filter by search term
    if (searchTerm && !log.message.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }

    // Filter by level
    if (filterLevel !== "all") {
      if (filterLevel === "error" && log.type !== "error") return false;
      if (filterLevel === "info" && log.type !== "info" && log.type !== "log") return false;
    }

    return true;
  });

  const getLogColor = (type: string) => {
    switch (type) {
      case "error":
        return "text-red-600 dark:text-red-400";
      case "info":
        return "text-blue-600 dark:text-blue-400";
      default:
        return "text-gray-700 dark:text-gray-300";
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-6xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">Container Logs</h2>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {containerName}
            </span>
            {isConnected && !isPaused && (
              <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                <span className="w-2 h-2 bg-green-600 rounded-full animate-pulse"></span>
                Live
              </span>
            )}
            {isPaused && (
              <span className="flex items-center gap-1 text-xs text-yellow-600 dark:text-yellow-400">
                <Pause className="w-3 h-3" />
                Paused
              </span>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search logs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
            />
          </div>

          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
          >
            <option value="all">All Levels</option>
            <option value="info">Info</option>
            <option value="error">Errors</option>
          </select>

          <Button
            size="sm"
            variant="outline"
            onClick={handlePauseResume}
          >
            {isPaused ? (
              <>
                <Play className="w-4 h-4 mr-1" />
                Resume
              </>
            ) : (
              <>
                <Pause className="w-4 h-4 mr-1" />
                Pause
              </>
            )}
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setAutoScroll(!autoScroll)}
          >
            <ChevronDown className={`w-4 h-4 mr-1 ${autoScroll ? "text-blue-600" : ""}`} />
            Auto-scroll
          </Button>

          <Button size="sm" variant="outline" onClick={handleClearLogs}>
            Clear
          </Button>

          <Button size="sm" variant="outline" onClick={handleDownload}>
            <Download className="w-4 h-4 mr-1" />
            Download
          </Button>
        </div>

        {/* Logs */}
        <div
          ref={logsContainerRef}
          className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-900 font-mono text-xs"
        >
          {filteredLogs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <Info className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No logs to display</p>
                {logs.length > 0 && (
                  <p className="text-xs mt-1">Try adjusting your filters</p>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {filteredLogs.map((log, index) => (
                <div
                  key={index}
                  className={`${getLogColor(log.type)} leading-relaxed`}
                >
                  {log.message}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500">
          <span>
            Showing {filteredLogs.length} of {logs.length} log lines
          </span>
          {!isConnected && !isPaused && (
            <span className="text-yellow-600 dark:text-yellow-400 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              Reconnecting...
            </span>
          )}
        </div>
      </Card>
    </div>
  );
}

