"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Lock, ChevronDown, X, Trash2, Plus, Loader2, Check } from "lucide-react";
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
        <div className="relative w-full overflow-x-auto scrollbar-thin rounded-[20px] bg-white border border-[#ebebeb] shadow-x1">
          <table className="shadow-table min-h-[92px] w-full min-w-max border-collapse">
            <thead>
              <tr className="border-none">
                <th className="bg-white px-3 py-3 text-left" style={{ width: "300px" }}>
                  <div className="flex items-center">
                    <div className="w-[16px] h-[16px] bg-[#eef2f5] rounded skeleton-animated mr-4 ml-1" />
                    <div className="w-[40px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
                  </div>
                </th>
                <th className="bg-white px-3 py-3 text-left">
                  <div className="w-[50px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
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
                  <td className="px-3 py-3" style={{ width: "300px" }}>
                    <div className="flex items-center">
                      <div className="w-[16px] h-[16px] bg-[#eef2f5] rounded skeleton-animated mr-4 ml-1" />
                      <div className="flex items-center gap-3">
                        <div className="w-[16px] h-[16px] bg-[#eef2f5] rounded skeleton-animated" />
                        <div className="w-[120px] h-[16px] bg-[#eef2f5] rounded skeleton-animated" />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="w-[180px] h-[16px] bg-[#eef2f5] rounded skeleton-animated" />
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
  const appName = params?.app as string;

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
  const [appDomain, setAppDomain] = useState<string>(projectName);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingSecret, setDeletingSecret] = useState<Secret | null>(null);

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
      setSecrets(data.secrets || []);
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
    setEditingSecret(secret);
    setEditValue(secret.value);
    setEditModalOpen(true);
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
            menuLabel="Secrets"
            title="Environment Variables"
          />

          {/* Environment Selector and Add Button */}
          <div className="mb-4 flex items-end justify-between gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-[#777] font-light tracking-[0.03em] block">Environment:</label>
              <div className="min-w-[200px]">
                <DropdownMenu.Root>
                  <DropdownMenu.Trigger className="bg-white user-select-none border border-[#0000001f] shadow-x1 relative flex h-8 w-auto items-center justify-between px-2 pr-[22px] py-2 rounded-[10px] cursor-pointer outline-none group">
                    <span className="capitalize text-[11px] tracking-[0.03em] font-light text-[#141414] user-select-none">{selectedEnvironment}</span>
                    <ChevronDown className="top-[10px] right-[9px] absolute w-3 h-3 text-black transition-transform duration-200 group-data-[state=open]:rotate-180" />
                  </DropdownMenu.Trigger>

                  <DropdownMenu.Portal>
                    <DropdownMenu.Content
                      align="start"
                      className="min-w-[200px] bg-white rounded-lg shadow-[0_4px_12px_rgba(0,0,0,0.15)] p-1 animate-[slide-fade-in-vertical_0.2s_ease-out] distance-8"
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
                          <span className="text-[11px] text-[#111] font-light tracking-[0.03em]">{env.label}</span>
                          {selectedEnvironment === env.value && (
                            <Check className="w-3.5 h-3.5 text-[#374046]" strokeWidth={2.5} />
                          )}
                        </DropdownMenu.Item>
                      ))}
                    </DropdownMenu.Content>
                  </DropdownMenu.Portal>
                </DropdownMenu.Root>
              </div>
            </div>

            <Button onClick={openAddModal} icon={<Plus className="w-3.5 h-3.5" />}>
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
              columns={[
                {
                  title: "Key",
                  width: "300px",
                  render: (item: Item) => (
                    <div className="flex items-center gap-3">
                      <Lock className="w-4 h-4 text-[#8b8b8b]" />
                      <code className="text-[13px] font-mono text-[#374046]">{item.data.key}</code>
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
                {
                  title: "",
                  width: "60px",
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
    </div>
  );
}
