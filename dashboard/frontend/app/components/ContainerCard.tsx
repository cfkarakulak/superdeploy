"use client";

import { useState } from "react";
import { Card } from "@/components/Card";
import { Button } from "@/components/Button";
import { 
  PlayCircle, 
  StopCircle, 
  RefreshCw, 
  Terminal, 
  Activity,
  CheckCircle,
  XCircle,
  AlertCircle
} from "lucide-react";
import toast from "react-hot-toast";

interface ContainerCardProps {
  container: {
    id: string;
    name: string;
    image: string;
    status: string;
    state: string;
    vm: string;
    vm_ip: string;
    cpu_percent?: number;
    memory_usage?: string;
    memory_percent?: number;
    network_rx?: string;
    network_tx?: string;
  };
  projectName: string;
  onRestart?: () => void;
  onViewLogs?: () => void;
  onViewMetrics?: () => void;
}

const API_URL = "http://localhost:8401";

export function ContainerCard({ 
  container, 
  projectName,
  onRestart,
  onViewLogs,
  onViewMetrics 
}: ContainerCardProps) {
  const [isRestarting, setIsRestarting] = useState(false);

  const getStatusBadge = () => {
    switch (container.state) {
      case "running":
        return (
          <div className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
            <CheckCircle className="w-3 h-3" />
            <span>Running</span>
          </div>
        );
      case "unhealthy":
        return (
          <div className="flex items-center gap-1 text-xs text-yellow-600 dark:text-yellow-400">
            <AlertCircle className="w-3 h-3" />
            <span>Unhealthy</span>
          </div>
        );
      case "exited":
        return (
          <div className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
            <XCircle className="w-3 h-3" />
            <span>Exited</span>
          </div>
        );
      case "restarting":
        return (
          <div className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>Restarting</span>
          </div>
        );
      default:
        return (
          <div className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
            <AlertCircle className="w-3 h-3" />
            <span>Unknown</span>
          </div>
        );
    }
  };

  const handleRestart = async () => {
    if (isRestarting) return;
    
    setIsRestarting(true);
    
    try {
      const response = await fetch(
        `${API_URL}/api/containers/${projectName}/containers/${container.name}/restart`,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error("Failed to restart container");
      }

      toast.success(`Container ${container.name} restarted successfully`);
      
      if (onRestart) {
        onRestart();
      }
    } catch (error) {
      toast.error(`Failed to restart container: ${error}`);
    } finally {
      setIsRestarting(false);
    }
  };

  return (
    <Card className="p-4 hover:shadow-lg transition-shadow">
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-sm truncate" title={container.name}>
              {container.name}
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate" title={container.image}>
              {container.image}
            </p>
          </div>
          {getStatusBadge()}
        </div>

        {/* Metrics */}
        {container.state === "running" && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-gray-500 dark:text-gray-400">CPU:</span>
              <span className="ml-1 font-medium">
                {container.cpu_percent !== undefined
                  ? `${container.cpu_percent.toFixed(1)}%`
                  : "N/A"}
              </span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Memory:</span>
              <span className="ml-1 font-medium">
                {container.memory_usage || "N/A"}
              </span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">RX:</span>
              <span className="ml-1 font-medium">
                {container.network_rx || "N/A"}
              </span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">TX:</span>
              <span className="ml-1 font-medium">
                {container.network_tx || "N/A"}
              </span>
            </div>
          </div>
        )}

        {/* VM Info */}
        <div className="text-xs text-gray-500 dark:text-gray-400">
          <span>VM: {container.vm}</span>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          <Button
            size="sm"
            variant="outline"
            onClick={handleRestart}
            disabled={isRestarting}
            className="flex-1 text-xs"
          >
            <RefreshCw className={`w-3 h-3 mr-1 ${isRestarting ? "animate-spin" : ""}`} />
            Restart
          </Button>
          
          <Button
            size="sm"
            variant="outline"
            onClick={onViewLogs}
            className="text-xs"
          >
            <Terminal className="w-3 h-3" />
          </Button>
          
          <Button
            size="sm"
            variant="outline"
            onClick={onViewMetrics}
            className="text-xs"
          >
            <Activity className="w-3 h-3" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

