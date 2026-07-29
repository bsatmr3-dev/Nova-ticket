import React, { useState, useEffect } from "react";
import { Header } from "./components/Header";
import { TokenModal } from "./components/TokenModal";
import { BotDashboard } from "./components/BotDashboard";

export default function App() {
  const [lang, setLang] = useState<"ar" | "en">("ar");
  const [status, setStatus] = useState({
    isRunning: false,
    hasToken: false,
    maskedToken: "",
    pid: null,
    uptime: 0
  });
  const [isTokenModalOpen, setIsTokenModalOpen] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/bot/status");
      if (!res.ok) return;
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await res.json();
        if (data && typeof data === "object") {
          setStatus(data);
        }
      }
    } catch {
      // Silently swallow fetch errors during background polling
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSaveToken = async (token: string) => {
    const res = await fetch("/api/bot/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token })
    });
    const contentType = res.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to save token");
      }
    } else if (!res.ok) {
      throw new Error("Failed to save token");
    }
    await fetchStatus();
  };

  const handleStartBot = async () => {
    try {
      const res = await fetch("/api/bot/start", { method: "POST" });
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await res.json();
        if (!res.ok) alert(data.error || "Failed to start bot");
      }
      fetchStatus();
    } catch (err) {
      console.error("Start bot error:", err);
    }
  };

  const handleStopBot = async () => {
    try {
      await fetch("/api/bot/stop", { method: "POST" });
      fetchStatus();
    } catch (err) {
      console.error("Stop bot error:", err);
    }
  };

  const handleDownloadZip = () => {
    window.location.href = "/api/codebase/download-zip";
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500/30">
      <Header
        isRunning={status.isRunning}
        hasToken={status.hasToken}
        maskedToken={status.maskedToken}
        lang={lang}
        setLang={setLang}
        onOpenTokenModal={() => setIsTokenModalOpen(true)}
        onStartBot={handleStartBot}
        onStopBot={handleStopBot}
        onDownloadZip={handleDownloadZip}
      />

      {/* Main Content Area - Clean Single-View Operations Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6">
        <BotDashboard
          lang={lang}
          status={status}
          onStartBot={handleStartBot}
          onStopBot={handleStopBot}
          onOpenTokenModal={() => setIsTokenModalOpen(true)}
          fetchStatus={fetchStatus}
        />
      </main>

      <TokenModal
        isOpen={isTokenModalOpen}
        onClose={() => setIsTokenModalOpen(false)}
        onSaveToken={handleSaveToken}
        lang={lang}
      />
    </div>
  );
}
