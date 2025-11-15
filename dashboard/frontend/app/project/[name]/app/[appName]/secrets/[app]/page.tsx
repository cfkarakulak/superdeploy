"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Lock, ChevronDown } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { AppHeader, PageHeader, Button, Input, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, Table } from "@/components";
import type { Item, TableColumn } from "@/components";

interface Secret {
  key: string;
  value: string;
  source: "app" | "shared" | "addon";
  editable: boolean;
  id?: number;
}

// Breadcrumb Skeleton
const BreadcrumbSkeleton = () => (
  <div className="flex items-center gap-3 mb-6">
    <div className="w-5 h-5 bg-[#e3e8ee] rounded skeleton-animated" />
    <div className="flex items-center gap-2">
      <div className="w-[80px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[100px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[100px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[8px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
      <div className="w-[120px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
  </div>
);

// Header Skeleton
const SecretsHeaderSkeleton = () => (
  <div className="mb-6">
    <div className="w-[150px] h-[28px] bg-[#e3e8ee] rounded-md mb-2 skeleton-animated" />
    <div className="w-[300px] h-[20px] bg-[#e3e8ee] rounded-md skeleton-animated" />
  </div>
);

// Info Box Skeleton
const InfoBoxSkeleton = () => (
  <div className="bg-[#e3e8ee] rounded-lg p-4 mb-6 shadow-sm skeleton-animated h-[60px]" />
);

// Table Skeleton
const SecretsTableSkeleton = () => (
  <div className="bg-white rounded-lg overflow-hidden shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
    <table className="w-full">
      <thead className="bg-[#f7f7f7]">
        <tr>
          <th className="px-4 py-3 text-left">
            <div className="w-[60px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
          </th>
          <th className="px-4 py-3 text-left">
            <div className="w-[70px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
          </th>
          <th className="px-4 py-3 text-right">
            <div className="w-[90px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated ml-auto" />
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-[#e3e8ee]">
        {Array.from({ length: 4 }, (_, i) => (
          <tr key={`config-var-skeleton-${i}`} className="hover:bg-[#f7f7f7]">
            <td className="px-4 py-3">
              <div className="w-[140px] h-[18px] bg-[#e3e8ee] rounded skeleton-animated" />
            </td>
            <td className="px-4 py-3">
              <div className="w-[200px] h-[18px] bg-[#e3e8ee] rounded skeleton-animated" />
            </td>
            <td className="px-4 py-3">
              <div className="flex justify-end gap-2">
                <div className="w-[50px] h-[18px] bg-[#e3e8ee] rounded skeleton-animated" />
                <div className="w-[50px] h-[18px] bg-[#e3e8ee] rounded skeleton-animated" />
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

// Full Page Skeleton
const SecretsPageSkeleton = () => (
  <div>
    <BreadcrumbSkeleton />
    <SecretsHeaderSkeleton />
    <InfoBoxSkeleton />
    <div className="mb-4">
      <div className="w-[180px] h-[36px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
    <SecretsTableSkeleton />
  </div>
);

export default function SecretsPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.app as string;

  const [configVars, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(true);
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

  const fetchSecrets = async () => {
    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/secrets/${projectName}/${appName}?environment=${selectedEnvironment}`
      );
      if (!response.ok) throw new Error("Failed to fetch config vars");
      const data = await response.json();
      setSecrets(data.secrets || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectName && appName) {
      fetchSecrets();
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
    setEditingSecret(secret);
    setEditValue(secret.value);
    setEditModalOpen(true);
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

  const handleDelete = async (key: string) => {
    if (!confirm(`Delete config var "${key}"?`)) return;

    setSavingKey(key);

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/secrets/${projectName}/${appName}/${key}?environment=${selectedEnvironment}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) throw new Error("Failed to delete config var");

      await fetchSecrets();
      alert("Config var deleted successfully. Containers are restarting...");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete config var");
    } finally {
      setSavingKey(null);
    }
  };

  const maskValue = (value: string) => {
    return "•".repeat(Math.min(value.length, 20));
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
              { label: appDomain || projectName, href: `/project/${projectName}` },
              { label: appName, href: `/project/${projectName}/app/${appName}` },
            ]}
            title="Environment Variables"
          />

          {/* Environment Selector */}
          <div className="mb-6 flex flex-col gap-1">
            <label className="text-[11px] text-[#777] font-light tracking-[0.03em] block">Environment:</label>
            <div className="min-w-[200px]">
              <DropdownMenu.Root>
                <DropdownMenu.Trigger className="bg-[#e5e8ee] relative flex h-9.5 w-auto items-center justify-between px-3 pr-8 py-2 text-[15px] text-[#0a0a0a] rounded-[10px] transition-colors cursor-pointer outline-none group">
                  <span className="capitalize text-[14px] text-[#0a0a0a]">{selectedEnvironment}</span>
                  <ChevronDown className="top-[13px] right-[10px] absolute w-4 h-4 text-[#8b8b8b] transition-transform duration-200 group-data-[state=open]:rotate-180" />
                </DropdownMenu.Trigger>

                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    align="start"
                    className="min-w-[200px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8"
                    sideOffset={5}
                  >
                    {[
                      { value: 'production', label: 'Production' },
                      { value: 'staging', label: 'Staging' },
                      { value: 'review', label: 'Review' }
                    ].map((env) => (
                      <DropdownMenu.Item
                        key={env.value}
                        onClick={() => setSelectedEnvironment(env.value)}
                        className="flex items-center justify-between px-3 py-2 rounded hover:bg-[#f7f7f7] outline-none cursor-pointer"
                      >
                        <span className="text-[14px] text-[#343a46]">{env.label}</span>
                        {selectedEnvironment === env.value && (
                          <div className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                        )}
                      </DropdownMenu.Item>
                    ))}
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
          </div>

          {/* Add New Button */}
          <div className="mb-4 hidden">
            <Button onClick={openAddModal}>
              Add New Config Var
            </Button>
          </div>

          {/* Secrets Table */}
          {configVars.length === 0 ? (
            <div className="rounded-[10px] p-8 text-center text-[#8b8b8b] text-[15px]">
              No config vars defined yet
            </div>
          ) : (
            <Table
              columns={[
                {
                  title: "Key",
                  width: "300px",
                  render: (item: Item) => (
                    <div className="flex items-center gap-3">
                      <Lock className="w-4 h-4 text-[#8b8b8b]" />
                      <code className="text-[13px] font-mono text-[#0a0a0a]">{item.data.key}</code>
                    </div>
                  ),
                },
                {
                  title: "Value",
                  render: (item: Item) => (
                    <code className="text-[13px] font-mono text-[#8b8b8b]">
                      {maskValue(item.data.value)}
                    </code>
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
              Add Config Var
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingSecret?.editable ? 'Edit Config Variable' : 'View Config Variable'}
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <Input
              label="Key"
              type="text"
              value={editingSecret?.key || ''}
              disabled
              className="font-mono"
            />
            
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
    </div>
  );
}
