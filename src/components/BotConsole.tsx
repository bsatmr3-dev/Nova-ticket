import React, { useState, useEffect, useRef } from "react";
import { Terminal, Trash2, RefreshCw, Copy, Check } from "lucide-react";

interface BotConsoleProps {
  lang: "ar" | "en";
}

export const BotConsole: React.FC<BotConsoleProps> = ({ lang }) => {
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const isAr = lang === "ar";

  const fetchLogs = async () => {
    try {
      const res = await fetch("/api/bot/logs");
      if (!res.ok) return;
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await res.json();
        if (data.logs) setLogs(data.logs);
      }
    } catch {
      // Silently handle polling error
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (autoScroll) {
      logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const copyLogs = () => {
    navigator.clipboard.writeText(logs.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col h-[580px]" dir={isAr ? "rtl" : "ltr"}>
      {/* Console Header */}
      <div className="bg-slate-950/80 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-indigo-400" />
          <h3 className="text-sm font-bold text-slate-200">
            {isAr ? "سجل البوت المباشر (Bot Output Terminal Log)" : "Bot Output Terminal Log"}
          </h3>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchLogs}
            className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs"
            title="Refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={copyLogs}
            className="flex items-center gap-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? (isAr ? "تم النسخ" : "Copied") : (isAr ? "نسخ السجل" : "Copy Logs")}
          </button>
        </div>
      </div>

      {/* Terminal View */}
      <div className="flex-1 bg-black/90 p-4 font-mono text-xs text-slate-300 overflow-y-auto space-y-1 selection:bg-indigo-500/30">
        {logs.length === 0 ? (
          <p className="text-slate-600 italic">No output logs yet...</p>
        ) : (
          logs.map((log, index) => {
            let colorClass = "text-slate-300";
            if (log.includes("[STDERR]") || log.includes("❌") || log.includes("Error")) {
              colorClass = "text-red-400";
            } else if (log.includes("⚡") || log.includes("✅") || log.includes("STDOUT")) {
              colorClass = "text-emerald-400";
            } else if (log.includes("🚀") || log.includes("🔑")) {
              colorClass = "text-indigo-400";
            }

            return (
              <div key={index} className={`leading-relaxed whitespace-pre-wrap ${colorClass}`}>
                {log}
              </div>
            );
          })
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
};
