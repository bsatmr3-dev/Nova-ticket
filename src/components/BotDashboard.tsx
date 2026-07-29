import React, { useState, useEffect } from "react";
import {
  Play,
  Square,
  RefreshCw,
  Key,
  ShieldCheck,
  Terminal as TerminalIcon,
  CheckCircle2,
  AlertCircle,
  Clock,
  Cpu,
  Server,
  ExternalLink,
  Bot,
  Zap,
  Sparkles,
  Layers,
  MessageSquare,
  ChevronRight,
  RotateCw
} from "lucide-react";

interface BotDashboardProps {
  lang: "ar" | "en";
  status: {
    isRunning: boolean;
    hasToken: boolean;
    maskedToken: string;
    pid: number | null;
    uptime: number;
  };
  onStartBot: () => Promise<void>;
  onStopBot: () => Promise<void>;
  onOpenTokenModal: () => void;
  fetchStatus: () => Promise<void>;
}

export function BotDashboard({
  lang,
  status,
  onStartBot,
  onStopBot,
  onOpenTokenModal,
  fetchStatus
}: BotDashboardProps) {
  const isAr = lang === "ar";

  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<{ success: boolean; message: string } | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string>("");
  const [logs, setLogs] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<"controls" | "logs">("controls");

  // Fetch bot invite URL
  useEffect(() => {
    fetch("/api/control/guilds")
      .then((res) => res.json())
      .then((data) => {
        if (data.bot_invite_url) {
          setInviteUrl(data.bot_invite_url);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch logs periodically
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await fetch("/api/bot/logs");
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.logs)) {
            setLogs(data.logs);
          }
        }
      } catch {
        // ignore
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 2500);
    return () => clearInterval(interval);
  }, []);

  // Handle Sync Commands
  const handleSyncCommands = async () => {
    setIsSyncing(true);
    setSyncResult(null);
    try {
      const res = await fetch("/api/bot/sync-commands", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.success) {
        setSyncResult({
          success: true,
          message: data.message || (isAr ? "تم مزامنة وتحديث أوامر البوت بنجاح!" : "Bot commands synced successfully!")
        });
      } else {
        setSyncResult({
          success: false,
          message: data.error || data.message || (isAr ? "حدث خطأ أثناء مزامنة الأوامر" : "Error syncing commands")
        });
      }
      await fetchStatus();
    } catch (err: any) {
      setSyncResult({
        success: false,
        message: err.message || (isAr ? "تعذر الاتصال بالسيرفر لمزامنة الأوامر" : "Failed to connect to server")
      });
    } finally {
      setIsSyncing(false);
    }
  };

  const commandList = [
    { name: "/control_panel", desc: isAr ? "لوحة التحكم الرئيسية التفاعلية الكاملة للمالك والإدارة" : "Full master interactive control panel" },
    { name: "/setup_panel", desc: isAr ? "نشر وتعديل لوحة التذاكر بإمبد أزارا ودروب داون" : "Post custom ticket panel embed with dropdown" },
    { name: "/setup", desc: isAr ? "معالج الإعداد الشامل خطوة بخطوة للوحات والتذاكر" : "Comprehensive step-by-step setup wizard" },
    { name: "/create", desc: isAr ? "إنشاء لوحة تذاكر تفاعلية جديدة بخصائصها" : "Create new interactive ticket panel" },
    { name: "/edit", desc: isAr ? "تعديل أقسام أو ألوان أو نصوص أي لوحة موجودة" : "Edit existing ticket panel details" },
    { name: "/dashboard", desc: isAr ? "فتح لوحة الإعدادات والتخصيص المباشرة" : "Open in-app settings dashboard" },
    { name: "/close", desc: isAr ? "إغلاق التذكرة الحالية وتنزيل السجل" : "Close active ticket and save transcript" },
    { name: "/claim", desc: isAr ? "استلام التذكرة من قبل عضو طاقم الدعم" : "Claim ticket for support staff" },
    { name: "/transcript", desc: isAr ? "تصدير محادثة التذكرة إلى ملف HTML احترافي" : "Export ticket conversation as HTML" },
    { name: "/blacklist_add", desc: isAr ? "حظر عضو من فتح التذاكر بالسيرفر" : "Blacklist user from opening tickets" }
  ];

  return (
    <div className="space-y-6" dir={isAr ? "rtl" : "ltr"}>
      {/* Top Banner Status */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/95 to-indigo-950/40 p-6 border border-slate-800 shadow-xl">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 via-indigo-500 to-amber-500" />
        
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className={`relative p-4 rounded-2xl border flex items-center justify-center ${
              status.isRunning
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-slate-800/60 border-slate-700/50 text-slate-400"
            }`}>
              <Bot className="w-8 h-8" />
              {status.isRunning && (
                <span className="absolute top-1 right-1 flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white">
                  {isAr ? "لوحة تشغيل البوت المباشرة" : "Bot Control Dashboard"}
                </h1>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  status.isRunning
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : "bg-slate-800 text-slate-400 border border-slate-700"
                }`}>
                  {status.isRunning ? (isAr ? "متصل ويعمل الآن" : "Running") : (isAr ? "متوقف" : "Stopped")}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                {isAr
                  ? "تحكم مباشر لتشغيل البوت، إيقافه، وتحديث أوامره مع ديسكورد بسرعة وفورية"
                  : "Direct control center to start, stop, and sync bot slash commands with Discord"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 w-full md:w-auto">
            {inviteUrl && (
              <a
                href={inviteUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700/80 transition-all cursor-pointer"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                {isAr ? "دعوة البوت لسيرفرك" : "Invite Bot"}
              </a>
            )}

            <button
              onClick={onOpenTokenModal}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-950/60 hover:bg-indigo-900/60 text-indigo-300 text-xs font-medium border border-indigo-700/50 transition-all cursor-pointer"
            >
              <Key className="w-3.5 h-3.5 text-indigo-400" />
              {status.hasToken
                ? (isAr ? `التوكن: ${status.maskedToken}` : `Token: ${status.maskedToken}`)
                : (isAr ? "إدخال توكن البوت" : "Enter Bot Token")}
            </button>
          </div>
        </div>
      </div>

      {/* Main 3 Action Cards (Start, Stop, Sync Commands) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* 1. Start Bot Card */}
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800/80 p-6 flex flex-col justify-between hover:border-emerald-500/40 transition-all shadow-lg group">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <Play className="w-6 h-6 fill-emerald-500/20" />
              </div>
              <span className="text-xs font-mono text-emerald-400/80 bg-emerald-950/40 px-2 py-1 rounded border border-emerald-800/40">
                python3 -m bot.main
              </span>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white group-hover:text-emerald-400 transition-colors">
                {isAr ? "1. تشغيل البوت" : "1. Start Bot"}
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                {isAr
                  ? "بدء تشغيل عملية البوت بالخلفية والاتصال المباشر مع سيرفرات ديسكورد"
                  : "Launch the Python Discord bot process and establish live gateway connection"}
              </p>
            </div>
          </div>

          <button
            onClick={status.hasToken ? onStartBot : onOpenTokenModal}
            disabled={status.isRunning}
            className={`mt-6 w-full py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md ${
              status.isRunning
                ? "bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed"
                : !status.hasToken
                ? "bg-amber-600 hover:bg-amber-500 text-white shadow-amber-600/20 hover:scale-[1.02]"
                : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20 hover:scale-[1.02]"
            }`}
          >
            <Play className="w-4 h-4 fill-current" />
            {status.isRunning
              ? (isAr ? "البوت قيد التشغيل بالفعل" : "Bot is already running")
              : !status.hasToken
              ? (isAr ? "إدخال التوكن وتشغيل البوت 🔑" : "Enter Token & Start Bot 🔑")
              : (isAr ? "تشغيل البوت الآن 🚀" : "Start Bot Now 🚀")}
          </button>
        </div>

        {/* 2. Stop Bot Card */}
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800/80 p-6 flex flex-col justify-between hover:border-rose-500/40 transition-all shadow-lg group">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <Square className="w-6 h-6 fill-rose-500/20" />
              </div>
              <span className="text-xs font-mono text-rose-400/80 bg-rose-950/40 px-2 py-1 rounded border border-rose-800/40">
                SIGTERM
              </span>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white group-hover:text-rose-400 transition-colors">
                {isAr ? "2. إيقاف البوت" : "2. Stop Bot"}
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                {isAr
                  ? "إنهاء عملية البوت بأمان وفصل الاتصال فوراً بدون تأثير على قاعدة البيانات"
                  : "Safely terminate the bot process and disconnect from Discord without data loss"}
              </p>
            </div>
          </div>

          <button
            onClick={onStopBot}
            disabled={!status.isRunning}
            className={`mt-6 w-full py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md ${
              !status.isRunning
                ? "bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed"
                : "bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/20 hover:scale-[1.02]"
            }`}
          >
            <Square className="w-4 h-4 fill-current" />
            {!status.isRunning
              ? (isAr ? "البوت متوقف حالياً" : "Bot is currently stopped")
              : (isAr ? "إيقاف البوت فوراً" : "Stop Bot Now")}
          </button>
        </div>

        {/* 3. Sync & Update Commands Card */}
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800/80 p-6 flex flex-col justify-between hover:border-indigo-500/40 transition-all shadow-lg group">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                <RefreshCw className={`w-6 h-6 ${isSyncing ? "animate-spin" : ""}`} />
              </div>
              <span className="text-xs font-mono text-indigo-400/80 bg-indigo-950/40 px-2 py-1 rounded border border-indigo-800/40">
                discord.tree.sync()
              </span>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white group-hover:text-indigo-400 transition-colors">
                {isAr ? "3. تحديث ومزامنة الأوامر" : "3. Sync / Update Commands"}
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                {isAr
                  ? "تحديث وتسجيل كافة أوامر السلاش (Slash Commands) مع سيرفرات ديسكورد فوراً"
                  : "Sync and register all application slash commands with Discord global API"}
              </p>
            </div>
          </div>

          <button
            onClick={handleSyncCommands}
            disabled={isSyncing || !status.hasToken}
            className={`mt-6 w-full py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md ${
              isSyncing
                ? "bg-indigo-800 text-indigo-200 cursor-wait"
                : !status.hasToken
                ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50"
                : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/20 hover:scale-[1.02]"
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${isSyncing ? "animate-spin" : ""}`} />
            {isSyncing
              ? (isAr ? "جاري المزامنـة..." : "Syncing...")
              : (isAr ? "تحديث وتزامُن الأوامر الآن" : "Sync & Update Commands Now")}
          </button>
        </div>
      </div>

      {/* Sync Status Alert Feedback */}
      {syncResult && (
        <div
          className={`p-4 rounded-xl border flex items-center gap-3 transition-all animate-fadeIn ${
            syncResult.success
              ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
              : "bg-rose-950/40 border-rose-500/40 text-rose-300"
          }`}
        >
          {syncResult.success ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          )}
          <p className="text-xs font-semibold leading-relaxed">{syncResult.message}</p>
        </div>
      )}

      {/* Commands & Terminal Tabs */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveTab("controls")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === "controls"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                  : "bg-slate-800/60 text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sparkles className="w-4 h-4" />
              {isAr ? "الأوامر المتاحة والمسجلة" : "Available Slash Commands"}
            </button>

            <button
              onClick={() => setActiveTab("logs")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === "logs"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                  : "bg-slate-800/60 text-slate-400 hover:text-slate-200"
              }`}
            >
              <TerminalIcon className="w-4 h-4" />
              {isAr ? "سجل التشغيل المباشر (Terminal)" : "Live Output Logs"}
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchStatus}
              className="p-2 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition-all cursor-pointer"
              title={isAr ? "تحديث الحالة" : "Refresh Status"}
            >
              <RotateCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-6">
          {activeTab === "controls" ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
                <span className="text-xs font-bold text-slate-300">
                  {isAr ? "قائمة أوامر السلاش المتاحة بالبوت:" : "Registered Application Slash Commands:"}
                </span>
                <span className="text-xs font-mono text-indigo-400 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/40">
                  {commandList.length} {isAr ? "أوامر" : "Commands"}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {commandList.map((cmd) => (
                  <div
                    key={cmd.name}
                    className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-indigo-500/30 transition-all flex items-start gap-3"
                  >
                    <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono text-xs font-bold shrink-0">
                      {cmd.name}
                    </div>
                    <div>
                      <p className="text-xs text-slate-300 leading-relaxed font-medium mt-0.5">{cmd.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-slate-400">
                  {isAr ? "سجل أحداث وتنبيهات البوت المباشرة (STDOUT / STDERR):" : "Live Bot Console Output Stream:"}
                </span>
                <span className="text-[11px] font-mono text-slate-500">
                  {logs.length} {isAr ? "سطر" : "lines"}
                </span>
              </div>

              <div className="bg-slate-950 rounded-xl p-4 border border-slate-800 font-mono text-xs text-slate-300 h-80 overflow-y-auto space-y-1 selection:bg-indigo-500/30 dir-ltr">
                {logs.length === 0 ? (
                  <div className="text-slate-600 text-center py-10">
                    {isAr ? "لا توجد سجلات حالية. انقر فوق [تشغيل البوت] لبدء التشغيل." : "No logs available. Click [Start Bot] to launch."}
                  </div>
                ) : (
                  logs.map((log, idx) => (
                    <div
                      key={idx}
                      className={`leading-relaxed break-all ${
                        log.includes("ERROR") || log.includes("❌")
                          ? "text-rose-400"
                          : log.includes("WARNING") || log.includes("⚠️")
                          ? "text-amber-300"
                          : log.includes("✅") || log.includes("🚀")
                          ? "text-emerald-400"
                          : "text-slate-300"
                      }`}
                    >
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
