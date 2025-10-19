const express = require('express');
const axios = require('axios');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const API_URL = process.env.API_URL || 'http://api:8000';
const PROXY_REGISTRY_URL = process.env.PROXY_REGISTRY_URL || 'http://proxy_registry:8080';

app.use(express.static('public'));
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// API proxy endpoints
app.get('/api/status', async (req, res) => {
    try {
        const [apiHealth, proxyHealth] = await Promise.all([
            axios.get(`${API_URL}/health`).catch(e => ({ data: { status: 'error', message: e.message } })),
            axios.get(`${PROXY_REGISTRY_URL}/health`).catch(e => ({ data: { status: 'error', message: e.message } }))
        ]);

        res.json({
            api: apiHealth.data,
            proxy_registry: proxyHealth.data,
            dashboard: { status: 'healthy' }
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/tasks', async (req, res) => {
    try {
        const response = await axios.get(`${API_URL}/api/tasks`);
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/proxies', async (req, res) => {
    try {
        const response = await axios.get(`${PROXY_REGISTRY_URL}/api/proxies`);
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Serve index.html for all other routes
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`Dashboard running on port ${PORT}`);
    console.log(`API URL: ${API_URL}`);
    console.log(`Proxy Registry URL: ${PROXY_REGISTRY_URL}`);
});
