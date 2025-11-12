"use client";

import { Card } from "@/components/Card";
import { Activity } from "lucide-react";

interface MetricsChartProps {
  containerName: string;
  projectName: string;
}

export function MetricsChart({ containerName, projectName }: MetricsChartProps) {
  // TODO: Implement real-time metrics chart with recharts or Chart.js
  // For now, showing placeholder

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-blue-600" />
        <h3 className="font-semibold">Real-time Metrics</h3>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {containerName}
        </span>
      </div>

      <div className="space-y-4">
        {/* CPU Chart Placeholder */}
        <div>
          <div className="text-sm font-medium mb-2">CPU Usage</div>
          <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded flex items-center justify-center text-gray-400 text-sm">
            CPU chart (coming soon)
          </div>
        </div>

        {/* Memory Chart Placeholder */}
        <div>
          <div className="text-sm font-medium mb-2">Memory Usage</div>
          <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded flex items-center justify-center text-gray-400 text-sm">
            Memory chart (coming soon)
          </div>
        </div>

        {/* Network Chart Placeholder */}
        <div>
          <div className="text-sm font-medium mb-2">Network I/O</div>
          <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded flex items-center justify-center text-gray-400 text-sm">
            Network chart (coming soon)
          </div>
        </div>
      </div>
    </Card>
  );
}

