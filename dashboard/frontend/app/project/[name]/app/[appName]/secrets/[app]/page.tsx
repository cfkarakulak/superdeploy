"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Lock, ChevronDown } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import AppHeader from "@/components/AppHeader";
import PageHeader from "@/components/PageHeader";
import { Button, Input, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components";

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
  <div className="bg-white rounded-lg overflow-hidden shadow-sm">
    <table className="w-full">
      <thead className="bg-gray-50">
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
      <tbody className="divide-y divide-gray-100">
        {Array.from({ length: 4 }, (_, i) => (
          <tr key={`config-var-skeleton-${i}`} className="hover:bg-gray-50">
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
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingSecret, setEditingSecret] = useState<Secret | null>(null);
  const [editValue, setEditValue] = useState("");
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [selectedEnvironment, setSelectedEnvironment] = useState("production");

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

  const toggleShowValue = (key: string) => {
    setShowValues((prev) => ({ ...prev, [key]: !prev[key] }));
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
        <>
          <PageHeader
            breadcrumb={{
              label: "Config Vars",
              href: `/project/${projectName}/app/${appName}/secrets/${appName}`
            }}
            title="Environment Variables"
            description={`Manage configuration and secrets for ${appName}`}
          />

      {/* Environment Selector */}
      <div className="mb-6 flex items-center gap-4">
        <label className="text-[15px] text-[#0a0a0a]">Environment:</label>
        <div className="min-w-[200px]">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger className="flex h-11 w-full items-center justify-between bg-white px-4 py-3 text-[15px] text-[#0a0a0a] border border-[#e3e8ee] rounded-md hover:bg-[#f7f7f7] transition-colors cursor-pointer outline-none group">
              <span className="capitalize">{selectedEnvironment}</span>
              <ChevronDown className="w-4 h-4 text-[#8b8b8b] transition-transform duration-200 group-data-[state=open]:rotate-180" />
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
                    <span className="text-[14px] text-[#0a0a0a]">{env.label}</span>
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
      <div className="mb-4">
        <Button onClick={openAddModal}>
          Add New Config Var
        </Button>
      </div>

      {/* Secrets Table */}
      <div className="bg-white rounded-[16px] overflow-hidden shadow-[0_0_0_1px_rgba(11,26,38,0.06),0_4px_12px_rgba(0,0,0,0.03),0_1px_3px_rgba(0,0,0,0.04)]">
        <table className="w-full">
          <thead className="bg-[#f7f7f7]">
            <tr>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#525252] uppercase tracking-wider w-12">
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#525252] uppercase tracking-wider">
                Key
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#525252] uppercase tracking-wider">
                Value
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e3e8ee]">
            {configVars.map((configVar) => (
              <tr 
                key={configVar.key} 
                onClick={() => configVar.editable && openEditModal(configVar)}
                className={`${configVar.editable ? 'cursor-pointer hover:bg-[#f7f7f7]' : ''} transition-colors`}
              >
                <td className="px-4 py-3">
                  <Lock className="w-4 h-4 text-[#8b8b8b]" />
                </td>
                <td className="px-4 py-3">
                  <code className="text-[13px] font-mono text-[#0a0a0a]">{configVar.key}</code>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <code className="text-[13px] font-mono text-[#525252]">
                      {showValues[configVar.key]
                        ? configVar.value
                        : maskValue(configVar.value)}
                    </code>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleShowValue(configVar.key);
                      }}
                      className="text-[#8b8b8b] hover:text-[#0a0a0a] text-[11px]"
                    >
                      {showValues[configVar.key] ? "hide" : "show"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {configVars.length === 0 && (
          <div className="text-center py-8 text-[#8b8b8b] text-[15px]">
            No config vars defined yet
          </div>
        )}
      </div>

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
            <DialogTitle>Edit Config Variable</DialogTitle>
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
              autoFocus
            />
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => setEditModalOpen(false)}
              disabled={savingKey !== null}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdate}
              disabled={savingKey !== null}
              loading={savingKey !== null}
            >
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
        </>
      )}
    </div>
  );
}
