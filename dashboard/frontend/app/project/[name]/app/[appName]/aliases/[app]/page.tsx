"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppHeader, PageHeader, Button, Input, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, Table, ToastContainer } from "@/components";
import type { Item } from "@/components";
import { Link2, Plus, Trash2, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/useToast";

interface Alias {
  alias_key: string;
  target_key: string;
  created_at?: string;
}

// Skeleton
const AliasesPageSkeleton = () => {
  const shimmerStyles = `
    @keyframes shimmer {
      0% { background-position: -1000px 0; }
      100% { background-position: 1000px 0; }
    }
    .skeleton-animated {
      animation: shimmer 2s infinite linear;
      background: linear-gradient(to right, #eef2f5 0%, #e3e8ee 20%, #eef2f5 40%, #eef2f5 100%);
      background-size: 1000px 100%;
    }
  `;

  return (
    <div>
      <style dangerouslySetInnerHTML={{ __html: shimmerStyles }} />
      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
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
        <div className="relative w-full overflow-x-auto scrollbar-thin rounded-[20px] bg-white border border-[#ebebeb]">
          <table className="shadow-table min-h-[92px] w-full min-w-max border-collapse">
            <thead>
              <tr className="border-none">
                <th className="bg-white px-3 py-3 text-left" style={{ width: "40%" }}>
                  <div className="w-[80px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
                </th>
                <th className="bg-white px-3 py-3 text-left" style={{ width: "40%" }}>
                  <div className="w-[80px] h-[14px] bg-[#eef2f5] rounded skeleton-animated" />
                </th>
                <th className="bg-white px-3 py-3 text-left" style={{ width: "20%" }}></th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 5 }).map((_, index) => (
                <tr key={`skeleton-row-${index}`} className={`table-row ${index !== 4 ? "border-b border-[#f0f0f0]" : ""}`}>
                  <td className="px-3 py-3">
                    <div className="w-[120px] h-[16px] bg-[#eef2f5] rounded skeleton-animated" />
                  </td>
                  <td className="px-3 py-3">
                    <div className="w-[180px] h-[16px] bg-[#eef2f5] rounded skeleton-animated" />
                  </td>
                  <td className="px-3 py-3">
                    <div className="w-[60px] h-[32px] bg-[#eef2f5] rounded skeleton-animated" />
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

export default function AliasesPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = (params?.app || params?.appName) as string;
  const toast = useToast();

  const [aliases, setAliases] = useState<Alias[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [editingAlias, setEditingAlias] = useState<Alias | null>(null);
  const [deletingAlias, setDeletingAlias] = useState<Alias | null>(null);
  const [newAliasKey, setNewAliasKey] = useState("");
  const [newTargetKey, setNewTargetKey] = useState("");
  const [editTargetKey, setEditTargetKey] = useState("");
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [appDomain, setAppDomain] = useState<string>("");
  const [selectedItems, setSelectedItems] = useState<Set<string | number>>(new Set());
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);

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

  const fetchAliases = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `http://localhost:8401/api/secrets/aliases/${projectName}/${appName}`
      );
      if (!response.ok) throw new Error("Failed to fetch aliases");
      const data = await response.json();
      setAliases(data.aliases || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectName && appName) {
      fetchAliases();
    }
  }, [projectName, appName]);

  const openAddModal = () => {
    setNewAliasKey("");
    setNewTargetKey("");
    setAddModalOpen(true);
  };

  const openEditModal = (alias: Alias) => {
    setEditingAlias(alias);
    setEditTargetKey(alias.target_key);
    setEditModalOpen(true);
  };

  const openDeleteModal = (alias: Alias) => {
    setDeletingAlias(alias);
    setDeleteModalOpen(true);
  };

  const handleAdd = async () => {
    if (!newAliasKey.trim() || !newTargetKey.trim()) {
      toast.error("Alias key and target key are required");
      return;
    }

    setSavingKey("__new__");

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/aliases/${projectName}/${appName}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ alias_key: newAliasKey, target_key: newTargetKey }),
        }
      );

      if (!response.ok) throw new Error("Failed to add alias");

      setNewAliasKey("");
      setNewTargetKey("");
      setAddModalOpen(false);
      await fetchAliases();
      toast.success("Alias added successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add alias");
    } finally {
      setSavingKey(null);
    }
  };

  const handleUpdate = async () => {
    if (!editingAlias) return;

    setSavingKey(editingAlias.alias_key);

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/aliases/${projectName}/${appName}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ alias_key: editingAlias.alias_key, target_key: editTargetKey }),
        }
      );

      if (!response.ok) throw new Error("Failed to update alias");

      setEditModalOpen(false);
      setEditingAlias(null);
      await fetchAliases();
      toast.success("Alias updated successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update alias");
    } finally {
      setSavingKey(null);
    }
  };

  const handleDelete = async () => {
    if (!deletingAlias) return;

    setSavingKey(deletingAlias.alias_key);

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/aliases/${projectName}/${appName}/${deletingAlias.alias_key}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) throw new Error("Failed to delete alias");

      setDeleteModalOpen(false);
      setDeletingAlias(null);
      await fetchAliases();
      toast.success("Alias deleted successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete alias");
    } finally {
      setSavingKey(null);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedItems.size === 0) return;

    try {
      const selectedKeys = Array.from(selectedItems);
      const selectedAliases = aliases.filter((a) => selectedKeys.includes(a.alias_key));

      if (selectedAliases.length === 0) {
        toast.error("No aliases selected");
        return;
      }

      // Delete all selected aliases
      await Promise.all(
        selectedAliases.map((alias) =>
          fetch(
            `http://localhost:8401/api/secrets/aliases/${projectName}/${appName}/${alias.alias_key}`,
            { method: "DELETE" }
          )
        )
      );

      setBulkDeleteModalOpen(false);
      setSelectedItems(new Set());
      await fetchAliases();
      toast.success(`${selectedAliases.length} alias(es) deleted successfully`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete aliases");
    }
  };

  return (
    <div>
      <ToastContainer />
      <AppHeader />

      {loading ? (
        <AliasesPageSkeleton />
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
            menuLabel="Aliases"
            title="Environment Variable Aliases"
          />

          {/* Add Button */}
          <div className="mb-4 flex items-end justify-between gap-4">
            <div className="text-[12px] text-[#8b8b8b] flex-1 max-w-[600px]">
              Aliases map one environment variable to another<br></br> (e.g., DB_HOST → postgres.primary.HOST)
            </div>
            <Button onClick={openAddModal} icon={<Plus className="w-3.5 h-3.5" />} className="shrink-0 whitespace-nowrap">
              Add New Alias
            </Button>
          </div>

          {/* Aliases Table */}
          {aliases.length === 0 ? (
            <div className="rounded-[10px] p-8 text-center text-[#8b8b8b] text-[15px]">
              No aliases defined yet
            </div>
          ) : (
            <Table
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
                  title: "Alias Key",
                  width: "40%",
                  render: (item: Item) => (
                    <div className="flex items-center gap-3">
                      <Link2 className="w-4 h-4 text-[#8b8b8b]" />
                      <code className="text-[13px] font-mono text-[#374046]">{item.data.alias_key}</code>
                    </div>
                  ),
                },
                {
                  title: "Target Key",
                  width: "40%",
                  render: (item: Item) => (
                    <code className="text-[13px] font-mono text-[#6366f1]">
                      {item.data.target_key}
                    </code>
                  ),
                },
                {
                  title: "",
                  width: "20%",
                  render: (item: Item) => (
                    <div className="flex items-center justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Trash2 className="w-3.5 h-3.5" />}
                        onClick={(e) => {
                          e.stopPropagation();
                          openDeleteModal(item.data);
                        }}
                        disabled={savingKey === item.data.alias_key}
                        className="p-1.5! hover:bg-[#fef2f2]! text-[#8b8b8b]! hover:text-[#ef4444]!"
                      >
                        {/* Icon only */}
                      </Button>
                    </div>
                  ),
                },
              ]}
              data={aliases.map((alias) => ({
                id: alias.alias_key,
                type: "alias",
                data: alias,
              }))}
              getRowKey={(item) => `alias-${item.id}`}
              onRowClick={(item) => openEditModal(item.data)}
              onSelectionChange={setSelectedItems}
              isRowSelectable={() => true}
            />
          )}
        </div>
      )}

      {/* Add Modal */}
      <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add New Alias</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <Input
              label="Alias Key"
              type="text"
              value={newAliasKey}
              onChange={(e) => setNewAliasKey(e.target.value)}
              placeholder="DB_HOST"
              autoFocus
            />

            <Input
              label="Target Key"
              type="text"
              value={newTargetKey}
              onChange={(e) => setNewTargetKey(e.target.value)}
              placeholder="postgres.primary.HOST"
            />

            <p className="text-[11px] text-[#8b8b8b]">
              Example: Map <code>DB_HOST</code> to <code>postgres.primary.HOST</code>
            </p>
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
              Add Alias
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              <code className="font-mono">{editingAlias?.alias_key}</code>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <Input
              label="Target Key"
              type="text"
              value={editTargetKey}
              onChange={(e) => setEditTargetKey(e.target.value)}
              placeholder="postgres.primary.HOST"
              autoFocus
            />

            <p className="text-[11px] text-[#8b8b8b]">
              Update the target key that this alias points to
            </p>
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

      {/* Delete Confirmation Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Alias</DialogTitle>
          </DialogHeader>

          <div className="py-4">
            <p className="text-[14px] text-[#343a46] mb-3">
              Are you sure you want to delete this alias?
            </p>

            <div className="bg-[#fef2f2] rounded-lg p-3">
              <code className="text-[13px] font-mono text-[#ef4444] break-all">
                {deletingAlias?.alias_key} → {deletingAlias?.target_key}
              </code>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                setDeleteModalOpen(false);
                setDeletingAlias(null);
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

      {/* Bulk Delete Confirmation */}
      <Dialog open={bulkDeleteModalOpen} onOpenChange={setBulkDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Aliases</DialogTitle>
          </DialogHeader>
          <p className="text-[14px] text-[#374046] py-4">
            Are you sure you want to delete {selectedItems.size} alias(es)? This action cannot be undone.
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
    </div>
  );
}

