import React from "react";
import { Bot, Play, Square, Download, Key, Sparkles, Terminal, CheckCircle2, AlertCircle } from "lucide-react";

interface HeaderProps {
  isRunning: boolean;
  hasToken: boolean;
  maskedToken: string;
  lang: "ar" | "en";
  setLang: (lang: "ar" | "en") => void;
  onOpenTokenModal: () => void;
  onStartBot: () => void;
  onStopBot: () => void;
  onDownloadZip: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isRunning,
  hasToken,
  maskedToken,
  lang,
  setLang,
  onOpenTokenModal,
  onStartBot,
  onStopBot,
  onDownloadZip
}) => {
  const isAr = lang === "ar";

  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50 px-4 py-3 shadow-xl" dir={isAr ? "rtl" : "ltr"}>
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Left / Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-white tracking-tight">
                {isAr ? "استوديو بوت التذاكر المتقدم" : "Discord Ticket Bot Studio"}
              </h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 font-medium border border-indigo-500/20">
                python3 / discord.py v2.3+
              </span>
            </div>
            <p className="text-xs text-slate-400">
              {isAr ? "نظام تذاكر احترافي متكامل مع Cogs و HTML Transcripts و 5-Star Rating" : "Professional Python Discord Ticket Bot with Cogs, HTML Transcripts & Ratings"}
            </p>
          </div>
        </div>

        {/* Right / Actions & Status */}
        <div className="flex items-center flex-wrap gap-2 sm:gap-3">
          {/* Status Badge */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border ${
            isRunning 
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" 
              : "bg-slate-800 text-slate-400 border-slate-700"
          }`}>
            <span className={`w-2 h-2 rounded-full ${isRunning ? "bg-emerald-500 animate-pulse" : "bg-slate-500"}`} />
            {isRunning 
              ? (isAr ? "البوت يعمل الآن" : "Bot Online") 
              : (isAr ? "البوت متوقف" : "Bot Offline")}
          </div>

          {/* Token Status Button */}
          <button
            onClick={onOpenTokenModal}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              hasToken
                ? "bg-slate-800 text-slate-200 border-slate-700 hover:border-slate-600"
                : "bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse"
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            {hasToken ? (
              <span>{isAr ? "التوكن:" : "Token:"} <code className="text-indigo-400 font-mono">{maskedToken}</code></span>
            ) : (
              <span>{isAr ? "إدخال توكن البوت (Secret)" : "Set Bot Token"}</span>
            )}
          </button>

          {/* Bot Run / Stop Button */}
          {isRunning ? (
            <button
              onClick={onStopBot}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 rounded-lg text-xs font-semibold transition-all cursor-pointer"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              {isAr ? "إيقاف البوت" : "Stop Bot"}
            </button>
          ) : (
            <button
              onClick={onStartBot}
              disabled={!hasToken}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white shadow-md transition-all cursor-pointer ${
                hasToken
                  ? "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/20"
                  : "bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed"
              }`}
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              {isAr ? "تشغيل البوت" : "Run Bot"}
            </button>
          )}

          {/* Download ZIP */}
          <button
            onClick={onDownloadZip}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            {isAr ? "تحميل مشروع Python (ZIP)" : "Download Python Code (ZIP)"}
          </button>

          {/* Language Toggle */}
          <button
            onClick={() => setLang(isAr ? "en" : "ar")}
            className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-bold border border-slate-700 transition-all cursor-pointer"
          >
            {isAr ? "EN" : "العربية"}
          </button>
        </div>
      </div>
    </header>
  );
};
