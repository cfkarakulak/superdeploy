"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Lock, ChevronDown, X, Trash2, Plus, Loader2, Check, RefreshCw } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { AppHeader, PageHeader, Button, Input, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, Table } from "@/components";
import type { Item, TableColumn } from "@/components";
import { parseAnsi, segmentToStyle } from "@/lib/ansiParser";

interface Secret {
  key: string;
  value: string;
  source: "app" | "shared" | "addon" | "alias";
  editable: boolean;
  id?: number;
  target_key?: string; // For aliases - points to actual secret
}

// Full Page Skeleton
const SecretsPageSkeleton = () => {
  const shimmerStyles = `
    @keyframes shimmer {
      0% {
        background-position: -1000px 0;
      }
      100% {
        background-position: 1000px 0;
      }
    }
    .skeleton-animated {
      animation: shimmer 2s infinite linear;
      background: linear-gradient(
        to right,
        #eef2f5 0%,
        #e3e8ee 20%,
        #eef2f5 40%,
        #eef2f5 100%
      );
      background-size: 1000px 100%;
    }
  `;

  return (
    <div>
      <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
      
      {/* White container like real content */}
      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        {/* Breadcrumb and Title */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-[80px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
            <div className="w-[8px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
            <div className="w-[60px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
          </div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-[16px] h-[16px] bg-[#eef2f5] rounded skeleton-animated" />
            <div className="w-[200px] h-[24px] bg-[#eef2f5] rounded skeleton-animated" />
          </div>
        </div>

        {/* Environment Selector */}
        <div className="mb-4">
          <div className="w-[80px] h-[12px] bg-[#eef2f5] rounded skeleton-animated mb-2" />
          <div className="w-[200px] h-[32px] bg-[#eef2f5] rounded-[10px] skeleton-animated" />
        </div>

        {/* Table Container */}
        <div className="relative w-full rounded-[20px] bg-white border border-[#ebebeb] shadow-x1">
          <table className="shadow-table min-h-[92px] w-full border-collapse table-fixed">
            <thead>
              <tr className="border-none">
                <th className="bg-white px-3 py-3 text-left" style={{ width: "60%" }}>
                  <div className="flex items-center">
                    <div className="w-[16px] h-[16px] bg-[#eef2f5] rounded skeleton-animated mr-4 ml-1" />
                    <div className="w-[40px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
                  </div>
                </th>
                <th className="bg-white px-3 py-3 text-left" style={{ width: "30%" }}>
                  <div className="w-[50px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
                </th>
                <th className="bg-white px-3 py-3 text-left" style={{ width: "10%" }}>
                </th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 10 }).map((_, index) => (
                <tr
                  key={`skeleton-row-${index}`}
                  className={`table-row ${
                    index !== 9 ? "border-b border-[#f0f0f0]" : ""
                  }`}
                >
                  <td className="px-3 py-3" style={{ width: "60%" }}>
                    <div className="flex items-center">
                      <div className="w-[16px] h-[16px] bg-[#eef2f5] rounded skeleton-animated mr-4 ml-1" />
                      <div className="w-[120px] h-[16px] bg-[#eef2f5] rounded skeleton-animated" />
                    </div>
                  </td>
                  <td className="px-3 py-3" style={{ width: "30%" }}>
                    <div className="w-[50px] h-[20px] bg-[#eef2f5] rounded skeleton-animated" />
                  </td>
                  <td className="px-3 py-3" style={{ width: "10%" }}>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default function SecretsPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = (params?.app || params?.appName) as string;

  const [configVars, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(true);
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingSecret, setEditingSecret] = useState<Secret | null>(null);
  const [editValue, setEditValue] = useState("");
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [selectedEnvironment, setSelectedEnvironment] = useState("production");
  const [appDomain, setAppDomain] = useState<string>("");
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingSecret, setDeletingSecret] = useState<Secret | null>(null);
  const [selectedItems, setSelectedItems] = useState<Set<string | number>>(new Set());
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [syncLogs, setSyncLogs] = useState<string>("");
  const [syncing, setSyncing] = useState(false);
  const syncLogsEndRef = useRef<HTMLDivElement>(null);
  
  // Alias modal states
  const [aliasModalOpen, setAliasModalOpen] = useState(false);
  const [viewingAlias, setViewingAlias] = useState<Secret | null>(null);


  // Auto-scroll to bottom when logs update
  useEffect(() => {
    if (syncModalOpen && syncLogs) {
      syncLogsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [syncLogs, syncModalOpen]);
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

  const fetchSecrets = async (showSpinner = false) => {
    try {
      if (showSpinner) {
        setEnvironmentLoading(true);
        // 200ms manual sleep for smooth transition
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      
      const response = await fetch(
        `http://localhost:8401/api/secrets/secrets/${projectName}/${appName}?environment=${selectedEnvironment}`
      );
      if (!response.ok) throw new Error("Failed to fetch config vars");
      const data = await response.json();
      
      // Filter out addon secrets (they're shown in addon detail page)
      // Then sort: app, shared, alias
      const sourceOrder: Record<string, number> = {
        app: 1,
        shared: 2,
        alias: 3,
      };
      
      const filteredAndSorted = (data.secrets || [])
        .filter((s: Secret) => s.source !== 'addon') // Remove addon secrets
        .sort((a: Secret, b: Secret) => {
          const orderA = sourceOrder[a.source] || 5;
          const orderB = sourceOrder[b.source] || 5;
          return orderA - orderB;
        });
      
      setSecrets(filteredAndSorted);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
      setEnvironmentLoading(false);
    }
  };

  useEffect(() => {
    if (projectName && appName) {
      fetchSecrets(loading === false); // Show spinner only after initial load
    }
  }, [projectName, appName, selectedEnvironment]);

  const openAddModal = () => {
    setNewKey("");
    setNewValue("");
    setAddModalOpen(true);
  };

  const handleAdd = async () => {
    if (!newKey.trim() || !newValue.trim()) {
      alert("Key and value are required");
      return;
    }

    setSavingKey("__new__");

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/secrets/${projectName}/${appName}?environment=${selectedEnvironment}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: newKey, value: newValue }),
        }
      );

      if (!response.ok) throw new Error("Failed to add config var");

      setNewKey("");
      setNewValue("");
      setAddModalOpen(false);
      await fetchSecrets();
      alert("Config var added successfully. Containers are restarting...");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add config var");
    } finally {
      setSavingKey(null);
    }
  };

  const openEditModal = (secret: Secret) => {
    // If it's an alias, open alias modal instead
    if (secret.source === 'alias') {
      setViewingAlias(secret);
      setAliasModalOpen(true);
    } else {
      setEditingSecret(secret);
      setEditValue(secret.value);
      setEditModalOpen(true);
    }
  };

  const openDeleteModal = (secret: Secret) => {
    setDeletingSecret(secret);
    setDeleteModalOpen(true);
  };

  const handleUpdate = async () => {
    if (!editingSecret) return;
    
    setSavingKey(editingSecret.key);

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/secrets/${projectName}/${appName}?environment=${selectedEnvironment}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: editingSecret.key, value: editValue }),
        }
      );

      if (!response.ok) throw new Error("Failed to update config var");

      setEditModalOpen(false);
      setEditingSecret(null);
      await fetchSecrets();
      alert("Config var updated successfully. Containers are restarting...");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update config var");
    } finally {
      setSavingKey(null);
    }
  };

  const handleDelete = async () => {
    if (!deletingSecret) return;

    setSavingKey(deletingSecret.key);

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/secrets/${projectName}/${appName}/${deletingSecret.key}?environment=${selectedEnvironment}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) throw new Error("Failed to delete config var");

      setDeleteModalOpen(false);
      setDeletingSecret(null);
      await fetchSecrets();
      alert("Config var deleted successfully. Containers are restarting...");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete config var");
    } finally {
      setSavingKey(null);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedItems.size === 0) return;

    try {
      const selectedKeys = Array.from(selectedItems);
      const editableSecrets = configVars.filter(
        (s) => s.editable && selectedKeys.includes(s.key)
      );

      if (editableSecrets.length === 0) {
        alert("No editable secrets selected");
        return;
      }

      // Delete all selected secrets
      await Promise.all(
        editableSecrets.map((secret) =>
          fetch(
            `http://localhost:8401/api/secrets/secrets/${projectName}/${appName}/${secret.key}?environment=${selectedEnvironment}`,
            { method: "DELETE" }
          )
        )
      );

      setBulkDeleteModalOpen(false);
      setSelectedItems(new Set());
      await fetchSecrets();
      alert(`${editableSecrets.length} config var(s) deleted successfully. Containers are restarting...`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete config vars");
    }
  };

  const stripAnsi = (str: string) => {
    return str.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncLogs("");
    setSyncModalOpen(true);

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/sync/${projectName}/${appName}?environment=${selectedEnvironment}`,
        { method: "POST" }
      );

      if (!response.ok) {
        const error = await response.text();
        setSyncLogs(prev => prev + `\nError: ${error}`);
        return;
      }

      // Stream the logs
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          setSyncLogs(prev => prev + chunk);
        }
      }

      await fetchSecrets();
    } catch (err) {
      setSyncLogs(prev => prev + `\nError: ${err instanceof Error ? err.message : "Failed to sync"}`);
    } finally {
      setSyncing(false);
    }
  };
  const maskValue = (value: string) => {
    return "•••";
  };

  return (
    <div>
      <AppHeader />
      
      {loading ? (
        <SecretsPageSkeleton />
      ) : error ? (
        <div className="alert alert-error">
          <p><strong>Error:</strong> {error}</p>
        </div>
      ) : (
        <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
          <PageHeader
            breadcrumbs={[
              { label: appDomain || "Loading...", href: `/project/${projectName}` },
              { label: appName, href: `/project/${projectName}/app/${appName}` },
            ]}
            menuLabel="Secrets"
            title="Environment Variables"
          />

          {/* Environment Selector and Add Button */}
          <div className="mb-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-1">
              <div>
                <DropdownMenu.Root>
                  <DropdownMenu.Trigger className="border border-[#e3e8ee] hover:bg-[#f6f8fa] user-select-none relative flex items-center justify-between px-4 pr-8 py-2 rounded-[10px] cursor-pointer outline-none group w-auto">
                    <span className="capitalize text-[13px] tracking-[0.03em] font-light text-[#0a0a0a] user-select-none">{selectedEnvironment}</span>
                    <ChevronDown className="absolute right-3 w-3.5 h-3.5 text-[#8b8b8b] transition-transform duration-200 group-data-[state=open]:rotate-180" />
                  </DropdownMenu.Trigger>

                    <DropdownMenu.Portal>
                      <DropdownMenu.Content
                        align="start"
                        className="min-w-[200px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8 z-100"
                        sideOffset={5}
                      >
                        {[
                          { value: 'production', label: 'Production' },
                          { value: 'staging', label: 'Staging' }
                        ].map((env) => (
                          <DropdownMenu.Item
                            key={env.value}
                            onClick={() => setSelectedEnvironment(env.value)}
                            className="flex items-center justify-between px-3 py-2 rounded hover:bg-[#f6f8fa] outline-none cursor-pointer"
                          >
                            <span className="text-[13px] text-[#0a0a0a] font-light tracking-[0.03em]">{env.label}</span>
                            {selectedEnvironment === env.value && (
                              <Check className="w-3.5 h-3.5 text-[#0a0a0a]" strokeWidth={2.5} />
                            )}
                          </DropdownMenu.Item>
                        ))}
                    </DropdownMenu.Content>
                  </DropdownMenu.Portal>
                </DropdownMenu.Root>
              </div>

              <Button 
                onClick={handleSync} 
                icon={<RefreshCw className="w-3.5 h-3.5" />}
                className="bg-[#fed7aa]! text-[#9a3412]! hover:bg-[#fdba74]!"
              >
                Sync Secrets
              </Button>
            </div>

            <Button 
              onClick={openAddModal} 
              icon={<Plus className="w-3.5 h-3.5" />}
              className="shrink-0"
            >
              Add New Secret
            </Button>
          </div>

          {/* Secrets Table */}
          {environmentLoading ? (
            <div className="rounded-[16px] border border-[#e3e8ee] bg-white p-16 flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-[#687b8c] animate-spin" />
            </div>
          ) : configVars.length === 0 ? (
            <div className="rounded-[10px] p-8 text-center text-[#8b8b8b] text-[15px]">
              No config vars defined yet
            </div>
          ) : (
            <Table
              tableFixed={true}
              bulkActionsBar={
                selectedItems.size > 0 ? (
                  <div className="flex items-center justify-between w-full">
                    <span className="text-[13px] text-[#374046] font-normal">
                      {selectedItems.size} selected
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Trash2 className="w-3.5 h-3.5" />}
                        onClick={() => setBulkDeleteModalOpen(true)}
                        className="bg-[#fef2f2]! text-[#ef4444]! hover:bg-[#fee2e2]! hover:text-[#ef4444]!"
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                ) : undefined
              }
                columns={[
                  {
                    title: "Key",
                    width: "60%",
                    render: (item: Item) => (
                      <div className="flex items-center gap-2 min-w-0">
                        <Lock className="w-4 h-4 text-[#8b8b8b] shrink-0" />
                        <code className="text-[13px] font-mono text-[#111] truncate">{item.data.key}</code>
                      </div>
                    ),
                  },
                  {
                    title: "Type",
                    width: "30%",
                    render: (item: Item) => {
                      const sourceColors = {
                        shared: "bg-[#dbeafe] text-[#1e40af]",
                        app: "bg-[#dcfce7] text-[#15803d]",
                        addon: "bg-[#e0e7ff] text-[#4338ca]",
                        alias: "bg-[#fed7aa] text-[#9a3412]",
                      };
                      const sourceLabels = {
                        shared: "Shared",
                        app: "App",
                        addon: "Addon",
                        alias: "Alias",
                      };
                      const source = item.data.source || "app";
                      return (
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] tracking-[0.03em] font-light ${sourceColors[source as keyof typeof sourceColors]}`}>
                          {sourceLabels[source as keyof typeof sourceLabels]}
                        </span>
                      );
                    },
                  },
                  {
                    title: "",
                    width: "10%",
                    render: (item: Item) => (
                      <div className="flex items-center justify-end">
                        {item.data.editable && (
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={<Trash2 className="w-3.5 h-3.5" />}
                            onClick={(e) => {
                              e.stopPropagation();
                              openDeleteModal(item.data);
                            }}
                            disabled={savingKey === item.data.key}
                            className="p-1.5! hover:bg-[#fef2f2]! text-[#8b8b8b]! hover:text-[#ef4444]!"
                          >
                            {/* Icon only button */}
                          </Button>
                        )}
                      </div>
                    ),
                  },
                ]}
                data={configVars.map((configVar) => ({
                  id: configVar.key,
                  type: "secret",
                  data: configVar,
                }))}
                getRowKey={(item) => `secret-${item.id}`}
                onRowClick={(item) => {
                  // Open modal for all secrets to view (editable ones can be changed)
                  openEditModal(item.data);
                }}
                onSelectionChange={setSelectedItems}
                isRowSelectable={(item) => item.data.editable}
            />
          )}
        </div>
      )}

      {/* Add Modal */}
      <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add Config Variable</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <Input
              label="Key"
              type="text"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="DATABASE_URL"
              autoFocus
            />
            
            <Input
              label="Value"
              type="text"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder="postgres://..."
            />
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => setAddModalOpen(false)}
              disabled={savingKey !== null}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAdd}
              disabled={savingKey !== null}
              loading={savingKey !== null}
            >
              Add Secret
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              <code className="font-mono">{editingSecret?.key}</code>
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <Input
              label="Value"
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              placeholder="Enter new value..."
              disabled={!editingSecret?.editable}
              autoFocus={editingSecret?.editable}
            />
            
            {!editingSecret?.editable && (
              <p className="text-[12px] text-[#8b8b8b]">
                This is a {editingSecret?.source} secret and cannot be edited directly.
              </p>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => setEditModalOpen(false)}
              disabled={savingKey !== null}
            >
              {editingSecret?.editable ? 'Cancel' : 'Close'}
            </Button>
            {editingSecret?.editable && (
              <Button
                onClick={handleUpdate}
                disabled={savingKey !== null}
                loading={savingKey !== null}
              >
                Save Changes
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Config Variable</DialogTitle>
          </DialogHeader>
          
          <div className="py-4">
            <p className="text-[14px] text-[#343a46] mb-3">
              Are you sure you want to delete this config variable?
            </p>
            
            <div className="bg-[#fef2f2] border border-[#fee2e2] rounded-lg p-3">
              <code className="text-[13px] font-mono text-[#ef4444] break-all">
                {deletingSecret?.key}
              </code>
            </div>
            
            <p className="text-[12px] text-[#8b8b8b] mt-3">
              This action will restart your containers.
            </p>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                setDeleteModalOpen(false);
                setDeletingSecret(null);
              }}
              disabled={savingKey !== null}
            >
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              disabled={savingKey !== null}
              loading={savingKey !== null}
              className="bg-[#ef4444]! hover:bg-[#dc2626]!"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog open={bulkDeleteModalOpen} onOpenChange={setBulkDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Config Vars</DialogTitle>
          </DialogHeader>
          <p className="text-[14px] text-[#374046] py-4">
            Are you sure you want to delete {selectedItems.size} config var(s)? This action cannot be undone and will restart your containers.
          </p>
          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => setBulkDeleteModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleBulkDelete}
              className="bg-[#ef4444]! hover:bg-[#dc2626]!"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync Secrets Dialog */}
      <Dialog open={syncModalOpen} onOpenChange={setSyncModalOpen}>
        <DialogContent className="sm:max-w-[720px] w-[720px] max-w-[720px]">
          <DialogHeader>
            <DialogTitle>Sync Secrets to GitHub</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <div className="terminal-container scrollbar-custom rounded-lg p-4 text-[13px] leading-relaxed overflow-y-auto h-[500px] max-h-[500px]">
              {syncLogs ? (
                <div className="space-y-0.5">
                  {syncLogs.split('\n').map((line, index) => {
                    const segments = parseAnsi(line);
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
                  <div ref={syncLogsEndRef} />
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-[#8b8b8b]">
                  <div className="text-center">
                    <p>Initializing sync...</p>
                  </div>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setSyncModalOpen(false)}
              disabled={syncing}
            >
              {syncing ? "Syncing..." : "Close"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Alias View Modal */}
      <Dialog open={aliasModalOpen} onOpenChange={setAliasModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              <code className="font-mono">{viewingAlias?.key}</code>
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {viewingAlias?.target_key && (
              <div>
                <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-2">Points To</label>
                <code className="block text-[13px] font-mono bg-[#fff8e1] px-3 py-2.5 rounded-[10px] text-[#795548] break-all">
                  {viewingAlias.target_key}
                </code>
              </div>
            )}
            
            <div>
              <label className="text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light block mb-2">Resolved Value (Read-only)</label>
              <code className="block text-[13px] font-mono bg-[#f6f8fa] px-3 py-2.5 rounded-[10px] text-[#0a0a0a] break-all">
                {viewingAlias?.value}
              </code>
            </div>
            
            <div className="bg-[#e0f2fe] rounded-[10px] p-3">
              <p className="text-[11px] tracking-[0.03em] font-light text-[#075985]">
                <strong className="font-medium">Alias:</strong> This is an alias that points to another secret. The value is resolved automatically from the target secret. To manage aliases, visit the Aliases page.
              </p>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => setAliasModalOpen(false)}
            >
              Close
            </Button>
            <Button
              onClick={() => {
                if (viewingAlias) {
                  openDeleteModal(viewingAlias);
                  setAliasModalOpen(false);
                }
              }}
              className="bg-[#ef4444]! hover:bg-[#dc2626]! text-white!"
            >
              Delete Alias
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
