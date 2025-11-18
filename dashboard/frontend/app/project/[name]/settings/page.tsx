"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ProjectHeader, PageHeader, Button, Input } from "@/components";
import { AlertTriangle, Trash2, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components";
import { useDeploymentLog } from "@/contexts/DeploymentLogContext";

export default function ProjectSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const projectName = params?.name as string;
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const { addLog, clearLogs, show: showGlobalLog, setDeploying: setGlobalDeploying, setTitle } = useDeploymentLog();

  const handleDelete = async () => {
    if (deleteConfirmation !== projectName) {
      return;
    }

    setDeleting(true);
    clearLogs();
    setTitle("Project Teardown");
    showGlobalLog();
    setGlobalDeploying(true);

    try {
      const response = await fetch(`http://localhost:8401/api/projects/${projectName}/down`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to delete project");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const logMessage = line.substring(6);
              if (logMessage) {
                addLog(logMessage);
              }
            }
          }
        }
      }

      // Wait a bit before redirecting
      setTimeout(() => {
        setGlobalDeploying(false);
        router.push("/");
      }, 2000);
    } catch (err) {
      console.error("Failed to delete project:", err);
      const errorMsg = `✗ Failed to delete project: ${err instanceof Error ? err.message : "Unknown error"}`;
      addLog(errorMsg);
      setGlobalDeploying(false);
      setDeleting(false);
    }
  };

  return (
    <div>
      <ProjectHeader />

      <div className="bg-white rounded-[16px] p-[32px] shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)]">
        <PageHeader
          breadcrumbs={[
            { label: "Projects", href: "/" },
            { label: projectName, href: `/project/${projectName}` },
          ]}
          menuLabel="Settings"
          title="Project Settings"
        />

        {/* Danger Zone */}
        <div className="mb-8">
          <h2 className="flex items-center gap-2 text-[11px] text-[#777] leading-tight tracking-[0.02em] mb-[6px] font-light">
            <AlertTriangle className="w-4 h-4" />
            Danger Zone
          </h2>
          <div className="p-5 bg-[#fff5f2] rounded-[12px]">
            <div>
              <h3 className="text-[14px] text-[#f33] mb-2">Delete Project</h3>
              <p className="text-[11px] text-[#f33] font-light tracking-[0.03em] leading-relaxed max-w-[500px] mb-4">
                Once you delete a project, there is no going back. This will permanently delete
                all VMs, apps, addons, secrets, and deployment history. Please be certain.
              </p>
              <Button
                variant="ghost"
                onClick={() => setShowDeleteModal(true)}
                icon={<Trash2 className="w-4 h-4" />}
                className="bg-[#ea5a5a]! text-white! hover:bg-[#cb2323]!"
              >
                Delete Project
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <DialogContent className="max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Delete Project</DialogTitle>
            <DialogDescription>
              This action cannot be undone. This will permanently teardown all infrastructure and delete the{" "}
              <span className="font-medium text-[#0a0a0a]">{projectName}</span> project from the database.
            </DialogDescription>
          </DialogHeader>

          {!deleting ? (
            <div className="py-4">
              <Input
                type="text"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                placeholder={`Type "${projectName}" to confirm`}
              />
            </div>
          ) : (
            <div className="py-8 flex flex-col items-center justify-center">
              <Loader2 className="w-8 h-8 text-[#8b8b8b] animate-spin mb-4" />
              <p className="text-[11px] text-[#8b8b8b] font-light tracking-[0.03em]">
                Running command...
              </p>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setShowDeleteModal(false);
                setDeleteConfirmation("");
              }}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleDelete}
              disabled={deleteConfirmation !== projectName || deleting}
              icon={deleting ? undefined : <Trash2 className="w-4 h-4" />}
              className="bg-red-600! hover:bg-red-700!"
            >
              {deleting ? "Deleting..." : "Delete Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
