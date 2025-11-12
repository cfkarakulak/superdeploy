"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface ConfigVar {
  key: string;
  value: string;
  source: "app" | "shared" | "addon";
  editable: boolean;
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
const ConfigVarsHeaderSkeleton = () => (
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
const ConfigVarsTableSkeleton = () => (
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
          <th className="px-4 py-3 text-left">
            <div className="w-[80px] h-[16px] bg-[#e3e8ee] rounded skeleton-animated" />
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
              <div className="w-[80px] h-[24px] bg-[#e3e8ee] rounded-full skeleton-animated" />
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
const ConfigVarsPageSkeleton = () => (
  <div className="max-w-[960px] mx-auto py-8 px-6">
    <BreadcrumbSkeleton />
    <ConfigVarsHeaderSkeleton />
    <InfoBoxSkeleton />
    <div className="mb-4">
      <div className="w-[180px] h-[36px] bg-[#e3e8ee] rounded skeleton-animated" />
    </div>
    <ConfigVarsTableSkeleton />
  </div>
);

export default function ConfigVarsPage() {
  const params = useParams();
  const projectName = params?.name as string;
  const appName = params?.app as string;

  const [configVars, setConfigVars] = useState<ConfigVar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});

  const fetchConfigVars = async () => {
    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/config-vars/${projectName}/${appName}`
      );
      if (!response.ok) throw new Error("Failed to fetch config vars");
      const data = await response.json();
      setConfigVars(data.config_vars || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectName && appName) {
      fetchConfigVars();
    }
  }, [projectName, appName]);

  const handleAdd = async () => {
    if (!newKey.trim() || !newValue.trim()) {
      alert("Key and value are required");
      return;
    }

    setSavingKey("__new__");

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/config-vars/${projectName}/${appName}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: newKey, value: newValue }),
        }
      );

      if (!response.ok) throw new Error("Failed to add config var");

      setNewKey("");
      setNewValue("");
      setShowAddForm(false);
      await fetchConfigVars();
      alert("Config var added successfully. Containers are restarting...");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add config var");
    } finally {
      setSavingKey(null);
    }
  };

  const handleUpdate = async (key: string, value: string) => {
    setSavingKey(key);

    try {
      const response = await fetch(
        `http://localhost:8401/api/secrets/config-vars/${projectName}/${appName}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key, value }),
        }
      );

      if (!response.ok) throw new Error("Failed to update config var");

      setEditingKey(null);
      await fetchConfigVars();
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
        `http://localhost:8401/api/secrets/config-vars/${projectName}/${appName}/${key}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) throw new Error("Failed to delete config var");

      await fetchConfigVars();
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

  if (loading) {
    return <ConfigVarsPageSkeleton />;
  }

  if (error) {
    return (
      <div className="max-w-[960px] mx-auto py-8 px-6">
        <div className="bg-red-50 rounded-lg p-4 shadow-sm">
          <p className="text-red-800">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[960px] mx-auto py-8 px-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-6">
        <Link
          href={`/project/${projectName}/app/${appName}`}
          className="text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-900">
            Projects
          </Link>
          <span>/</span>
          <Link
            href={`/project/${projectName}`}
            className="hover:text-gray-900"
          >
            {projectName}
          </Link>
          <span>/</span>
          <Link
            href={`/project/${projectName}/app/${appName}`}
            className="hover:text-gray-900"
          >
            {appName}
          </Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">Config Vars</span>
        </div>
      </div>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">Config Vars</h1>
        <p className="text-gray-600">
          Manage environment variables for {appName}
        </p>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 rounded-lg p-4 mb-6 shadow-sm">
        <p className="text-sm text-blue-800">
          <strong>Note:</strong> Changes to config vars will trigger a container
          restart to apply the new environment variables.
        </p>
      </div>

      {/* Add New Button */}
      <div className="mb-4">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium"
        >
          {showAddForm ? "Cancel" : "Add New Config Var"}
        </button>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="bg-white rounded-lg p-4 mb-6 shadow-sm">
          <h3 className="font-semibold mb-4">Add New Config Var</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">Key</label>
              <input
                type="text"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="DATABASE_URL"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Value</label>
              <input
                type="text"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder="postgres://..."
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <button
            onClick={handleAdd}
            disabled={savingKey === "__new__"}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium disabled:opacity-50"
          >
            {savingKey === "__new__" ? "Saving..." : "Add Config Var"}
          </button>
        </div>
      )}

      {/* Config Vars Table */}
      <div className="bg-white rounded-lg overflow-hidden shadow-sm">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Key
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Value
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Source
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {configVars.map((configVar) => {
              const isEditing = editingKey === configVar.key;
              const isSaving = savingKey === configVar.key;

              return (
                <tr key={configVar.key} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <code className="text-sm font-mono">{configVar.key}</code>
                  </td>
                  <td className="px-4 py-3">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm font-mono"
                        autoFocus
                      />
                    ) : (
                      <div className="flex items-center gap-2">
                        <code className="text-sm font-mono">
                          {showValues[configVar.key]
                            ? configVar.value
                            : maskValue(configVar.value)}
                        </code>
                        <button
                          onClick={() => toggleShowValue(configVar.key)}
                          className="text-gray-400 hover:text-gray-600 text-xs"
                        >
                          {showValues[configVar.key] ? "hide" : "show"}
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        configVar.source === "addon"
                          ? "bg-purple-100 text-purple-800"
                          : configVar.source === "shared"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {configVar.source}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {configVar.editable ? (
                      <div className="flex justify-end gap-2">
                        {isEditing ? (
                          <>
                            <button
                              onClick={() =>
                                handleUpdate(configVar.key, editValue)
                              }
                              disabled={isSaving}
                              className="text-green-600 hover:text-green-700 text-sm font-medium disabled:opacity-50"
                            >
                              {isSaving ? "Saving..." : "Save"}
                            </button>
                            <button
                              onClick={() => setEditingKey(null)}
                              disabled={isSaving}
                              className="text-gray-600 hover:text-gray-700 text-sm font-medium disabled:opacity-50"
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => {
                                setEditingKey(configVar.key);
                                setEditValue(configVar.value);
                              }}
                              disabled={isSaving}
                              className="text-blue-600 hover:text-blue-700 text-sm font-medium disabled:opacity-50"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDelete(configVar.key)}
                              disabled={isSaving}
                              className="text-red-600 hover:text-red-700 text-sm font-medium disabled:opacity-50"
                            >
                              {isSaving ? "Deleting..." : "Delete"}
                            </button>
                          </>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">Read-only</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {configVars.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No config vars defined yet
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-4 text-sm text-gray-600">
        <p>
          <strong>Sources:</strong>
        </p>
        <ul className="list-disc list-inside mt-2 space-y-1">
          <li>
            <strong>app</strong> - Variables specific to this application
          </li>
          <li>
            <strong>shared</strong> - Variables shared across all applications
          </li>
          <li>
            <strong>addon</strong> - Auto-generated by attached addons
            (read-only)
          </li>
        </ul>
      </div>
    </div>
  );
}
