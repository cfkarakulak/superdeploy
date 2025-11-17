"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader, Button } from "@/components";
import { Pause, Play, Trash2 } from "lucide-react";
import { parseAnsi, segmentToStyle } from "@/lib/ansiParser";

export default function LogsPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.appName as string;
  
  const [logs, setLogs] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [appDomain, setAppDomain] = useState<string>("");
  const logsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pausedLogsRef = useRef<string[]>([]);

  // Fetch app domain
  useEffect(() => {
    const fetchAppInfo = async () => {
      try {
        const response = await fetch(`http://localhost:8401/api/projects/${projectName}`);
        if (response.ok) {
          const data = await response.json();
          setAppDomain(data.domain || projectName);
        }
      } catch (err) {
        setAppDomain(projectName);
      }
    };
    if (projectName && appName) fetchAppInfo();
  }, [projectName, appName]);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    if (!isPaused) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs, isPaused]);

  // Start streaming logs
  const startStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(
      `http://localhost:8401/api/logs/${projectName}/apps/${appName}/logs/stream?lines=100`
    );

    eventSource.onmessage = (event) => {
      const logLine = event.data;
      
      if (isPaused) {
        // Store logs while paused
        pausedLogsRef.current.push(logLine);
      } else {
        setLogs((prev) => [...prev, logLine]);
      }
    };

    eventSource.onerror = (error) => {
      console.error("EventSource error:", error);
      setIsStreaming(false);
      eventSource.close();
    };

    eventSourceRef.current = eventSource;
    setIsStreaming(true);
  };

  // Stop streaming
  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
  };

  // Toggle pause
  const togglePause = () => {
    if (isPaused) {
      // Resume: add paused logs
      if (pausedLogsRef.current.length > 0) {
        setLogs((prev) => [...prev, ...pausedLogsRef.current]);
        pausedLogsRef.current = [];
      }
    }
    setIsPaused(!isPaused);
  };

  // Clear logs
  const clearLogs = () => {
    setLogs([]);
    pausedLogsRef.current = [];
  };

  // Start streaming on mount
  useEffect(() => {
    startStreaming();
    
    return () => {
      stopStreaming();
    };
  }, [projectName, appName]);

  return (
    <div>
      <AppHeader />
      
      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: appDomain || "Loading...", href: `/project/${projectName}` },
            { label: appName, href: `/project/${projectName}/app/${appName}` },
          ]}
          menuLabel="Logs"
          title="Application Logs"
        />

        {/* Controls */}
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-[14px] text-[#8b8b8b] pt-2">
              {isStreaming ? (
                <span className="flex items-center gap-2">
                  <div className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </div>
                  <span className="text-green-600">Streaming</span>
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500"></span>
                  <span className="text-red-600">Disconnected</span>
                </span>
              )}
            </span>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <Button
              onClick={togglePause}
              variant="neutral"
              size="md"
              icon={isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            >
              {isPaused ? "Resume" : "Pause"}
            </Button>

            <Button
              onClick={clearLogs}
              variant="neutral"
              size="md"
              icon={<Trash2 className="w-4 h-4" />}
            >
              Clear
            </Button>
          </div>
        </div>

        {/* Logs Terminal */}
        <div className="terminal-container scrollbar-custom rounded-lg p-4 text-[13px] leading-relaxed overflow-y-auto h-[600px] max-h-[600px]">
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-[#8b8b8b]">
              <div className="text-center">
                <p>Waiting for logs...</p>
              </div>
            </div>
          ) : (
            <div className="space-y-0.5">
              {logs.map((log, index) => {
                const segments = parseAnsi(log);
                return (
                  <div
                    key={index}
                    className="px-2 py-0.5 rounded whitespace-pre-wrap break-all"
                  >
                    {segments.map((segment, segIndex) => (
                      <span key={segIndex} style={segmentToStyle(segment)}>
                        {segment.text}
                      </span>
                    ))}
                  </div>
                );
              })}
              {isPaused && pausedLogsRef.current.length > 0 && (
                <div className="text-[#f59e0b] px-2 py-1 italic">
                  {pausedLogsRef.current.length} new logs (paused)
                </div>
              )}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="text-[11px] text-[#777] leading-tight tracking-[0.03em] mb-[6px] mt-3 font-light">
          <p>
            Showing logs for <span className="text-[#0a0a0a]">{appName}</span> in project{" "}
            <span className="text-[#0a0a0a]">{projectName}</span>
          </p>
        </div>
      </div>
    </div>
  );
}

