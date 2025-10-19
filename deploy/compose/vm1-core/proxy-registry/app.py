from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI(title="Proxy Registry", version="1.0.0")

# In-memory storage (for MVP - replace with database later)
proxies_db = {}


class ProxyInfo(BaseModel):
    ip: str
    port: int
    protocol: str  # socks5, http
    status: str = "active"
    vm_name: Optional[str] = None
    last_seen: Optional[str] = None


@app.get("/")
def read_root():
    return {
        "service": "Proxy Registry",
        "version": "1.0.0",
        "status": "running",
        "proxies_count": len(proxies_db),
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "proxies_count": len(proxies_db),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/proxies")
def list_proxies():
    """List all registered proxies"""
    return {"proxies": list(proxies_db.values()), "total": len(proxies_db)}


@app.get("/api/proxies/{proxy_id}")
def get_proxy(proxy_id: str):
    """Get specific proxy"""
    if proxy_id not in proxies_db:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return proxies_db[proxy_id]


@app.post("/api/proxies")
def register_proxy(proxy: ProxyInfo):
    """Register a new proxy"""
    proxy_id = f"{proxy.ip}:{proxy.port}"
    proxy_data = proxy.dict()
    proxy_data["last_seen"] = datetime.utcnow().isoformat()
    proxies_db[proxy_id] = proxy_data

    return {
        "id": proxy_id,
        "proxy": proxy_data,
        "message": "Proxy registered successfully",
    }


@app.put("/api/proxies/{proxy_id}")
def update_proxy(proxy_id: str, proxy: ProxyInfo):
    """Update existing proxy"""
    if proxy_id not in proxies_db:
        raise HTTPException(status_code=404, detail="Proxy not found")

    proxy_data = proxy.dict()
    proxy_data["last_seen"] = datetime.utcnow().isoformat()
    proxies_db[proxy_id] = proxy_data

    return {
        "id": proxy_id,
        "proxy": proxy_data,
        "message": "Proxy updated successfully",
    }


@app.delete("/api/proxies/{proxy_id}")
def delete_proxy(proxy_id: str):
    """Delete proxy"""
    if proxy_id not in proxies_db:
        raise HTTPException(status_code=404, detail="Proxy not found")

    deleted = proxies_db.pop(proxy_id)
    return {"message": "Proxy deleted successfully", "proxy": deleted}


@app.get("/api/proxies/next/available")
def get_next_proxy():
    """Get next available proxy for rotation"""
    active_proxies = [p for p in proxies_db.values() if p.get("status") == "active"]

    if not active_proxies:
        raise HTTPException(status_code=404, detail="No active proxies available")

    # Simple round-robin (improve with better algorithm later)
    return active_proxies[0]
