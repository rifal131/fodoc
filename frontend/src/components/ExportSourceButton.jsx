import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// Admin-only: authenticated blob download of the project source ZIP
export const ExportSourceButton = ({ className = "", testId = "export-source-button" }) => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  if (user?.role !== "admin") return null;

  const download = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/dev/download-project-source", { responseType: "blob", timeout: 0 });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "fodoc_project_source.zip";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      toast.success("Source code berhasil diunduh");
    } catch {
      toast.error("Gagal mengunduh source code");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={download}
      disabled={loading}
      data-testid={testId}
      className={`cta-btn-light inline-flex items-center gap-1.5 font-mono text-[11px] px-3 py-1.5 disabled:opacity-60 cursor-pointer ${className}`}
    >
      {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
      {loading ? "Menyiapkan…" : "Export ZIP"}
    </button>
  );
};
