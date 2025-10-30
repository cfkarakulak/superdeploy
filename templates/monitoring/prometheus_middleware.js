/**
 * Prometheus metrics middleware for Node.js/Express
 * Auto-tracks HTTP requests with path, method, status code
 */
const promClient = require('prom-client');

// Create metrics
const httpRequestsTotal = new promClient.Counter({
  name: 'app_http_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['method', 'path', 'status']
});

const httpRequestDuration = new promClient.Histogram({
  name: 'app_http_request_duration_seconds',
  help: 'HTTP request latency',
  labelNames: ['method', 'path'],
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5]
});

const httpRequestsInProgress = new promClient.Gauge({
  name: 'app_http_requests_in_progress',
  help: 'HTTP requests in progress',
  labelNames: ['method', 'path']
});

// Enable default metrics (CPU, memory, etc.)
promClient.collectDefaultMetrics();

/**
 * Express middleware for Prometheus metrics
 */
function prometheusMiddleware(req, res, next) {
  const start = Date.now();
  const path = req.route ? req.route.path : req.path;
  const method = req.method;
  
  // Track in-progress requests
  httpRequestsInProgress.labels(method, path).inc();
  
  // Capture response
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    const status = res.statusCode;
    
    // Record metrics
    httpRequestsTotal.labels(method, path, status).inc();
    httpRequestDuration.labels(method, path).observe(duration);
    httpRequestsInProgress.labels(method, path).dec();
  });
  
  next();
}

/**
 * Metrics endpoint handler
 */
async function metricsHandler(req, res) {
  res.set('Content-Type', promClient.register.contentType);
  res.end(await promClient.register.metrics());
}

/**
 * Setup Prometheus metrics for Express app
 */
function setupExpressMetrics(app) {
  // Add middleware
  app.use(prometheusMiddleware);
  
  // Add metrics endpoint
  app.get('/metrics', metricsHandler);
  
  return app;
}

module.exports = {
  prometheusMiddleware,
  metricsHandler,
  setupExpressMetrics,
  httpRequestsTotal,
  httpRequestDuration,
  httpRequestsInProgress
};
