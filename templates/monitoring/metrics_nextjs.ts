/**
 * Prometheus Metrics Endpoint for Next.js
 * 
 * Usage:
 * 1. Copy this file to: src/app/api/metrics/route.ts
 * 2. Access metrics at: GET /api/metrics
 * 
 * Provides basic Node.js runtime metrics for Prometheus scraping.
 */

import { NextResponse } from "next/server";

export async function GET() {
  const uptime = process.uptime();
  const memoryUsage = process.memoryUsage();

  // Prometheus text format
  const metrics = `# HELP nodejs_uptime_seconds Process uptime in seconds
# TYPE nodejs_uptime_seconds gauge
nodejs_uptime_seconds ${uptime}

# HELP nodejs_heap_size_total_bytes Process heap size total in bytes
# TYPE nodejs_heap_size_total_bytes gauge
nodejs_heap_size_total_bytes ${memoryUsage.heapTotal}

# HELP nodejs_heap_size_used_bytes Process heap size used in bytes
# TYPE nodejs_heap_size_used_bytes gauge
nodejs_heap_size_used_bytes ${memoryUsage.heapUsed}

# HELP nodejs_external_memory_bytes External memory size in bytes
# TYPE nodejs_external_memory_bytes gauge
nodejs_external_memory_bytes ${memoryUsage.external}

# HELP nodejs_rss_bytes Resident set size in bytes
# TYPE nodejs_rss_bytes gauge
nodejs_rss_bytes ${memoryUsage.rss}

# HELP up Service is up
# TYPE up gauge
up 1
`;

  return new NextResponse(metrics, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}

