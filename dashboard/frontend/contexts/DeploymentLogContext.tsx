"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

interface DeploymentLogContextType {
  logs: string[];
  isVisible: boolean;
  isDeploying: boolean;
  title: string;
  addLog: (log: string) => void;
  clearLogs: () => void;
  show: () => void;
  hide: () => void;
  setDeploying: (deploying: boolean) => void;
  setTitle: (title: string) => void;
}

const DeploymentLogContext = createContext<DeploymentLogContextType | undefined>(undefined);

export function DeploymentLogProvider({ children }: { children: ReactNode }) {
  const [logs, setLogs] = useState<string[]>([]);
  const [isVisible, setIsVisible] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);
  const [title, setTitle] = useState("Deployment");

  const addLog = (log: string) => {
    setLogs((prev) => [...prev, log]);
    setIsVisible(true); // Auto-show when logs come in
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const show = () => setIsVisible(true);
  const hide = () => setIsVisible(false);
  const setDeploying = (deploying: boolean) => setIsDeploying(deploying);

  return (
    <DeploymentLogContext.Provider
      value={{ logs, isVisible, isDeploying, title, addLog, clearLogs, show, hide, setDeploying, setTitle }}
    >
      {children}
    </DeploymentLogContext.Provider>
  );
}

export function useDeploymentLog() {
  const context = useContext(DeploymentLogContext);
  if (!context) {
    throw new Error("useDeploymentLog must be used within DeploymentLogProvider");
  }
  return context;
}

