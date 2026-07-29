import React, { useState } from "react";
import { Key, ShieldCheck, X, Check, Lock, ExternalLink } from "lucide-react";

interface TokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveToken: (token: string) => Promise<void>;
  lang: "ar" | "en";
}

export const TokenModal: React.FC<TokenModalProps> = ({ isOpen, onClose, onSaveToken, lang }) => {
  const [inputToken, setInputToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!isOpen) return null;
  const isAr = lang === "ar";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputToken.trim()) return;
    setLoading(true);
    setMessage(null);
    try {
      await onSaveToken(inputToken.trim());
      setMessage(isAr ? "تم حفظ التوكن بنجاح في ملف .env!" : "Bot token saved successfully in .env!");
      setTimeout(() => {
        onClose();
        setMessage(null);
        setInputToken("");
      }, 1200);
    } catch (err: any) {
      setMessage(err.message || "Error saving token");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 relative" dir={isAr ? "rtl" : "ltr"}>
        <button
          onClick={onClose}
          className="absolute top-4 left-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
            <Key className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">
              {isAr ? "إدخال توكن البوت (Discord Bot Token)" : "Configure Discord Bot Token"}
            </h3>
            <p className="text-xs text-slate-400">
              {isAr ? "يتم حفظ التوكن بأمان في ملف .env بالخادم" : "Stored securely in server .env file"}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              {isAr ? "توكن البوت الخاص بك" : "Your Bot Secret Token"}
            </label>
            <div className="relative">
              <input
                type="password"
                value={inputToken}
                onChange={(e) => setInputToken(e.target.value)}
                placeholder="MTM0NTY3ODkwMTIzNDU2Nzg5MA.G12345.abcdefghijklmnopqrstuvwxyz..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 font-mono placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
              <Lock className="w-4 h-4 text-slate-600 absolute right-3 top-3.5" />
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3 text-xs text-slate-400 space-y-1">
            <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              {isAr ? "كيف تحصل على توكن البوت؟" : "How to get your Bot Token?"}
            </div>
            <p className="leading-relaxed">
              {isAr ? "1. افتح بوابة المطورين بـ Discord" : "1. Open Discord Developer Portal"}
            </p>
            <p className="leading-relaxed">
              {isAr ? "2. اختر تطبيقك وادخل لقسم Bot ثم اضغط Reset Token" : "2. Select your App -> Bot -> Reset Token"}
            </p>
            <p className="leading-relaxed">
              {isAr ? "3. انسخ التوكن والصقه هنا للتفعيل الحقيقي للبوت" : "3. Copy token and paste here to run live bot"}
            </p>
            <a
              href="https://discord.com/developers/applications"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-indigo-400 hover:underline pt-1 text-xs"
            >
              Discord Developer Portal <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          {message && (
            <div className="p-3 rounded-xl text-xs bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 flex items-center gap-2">
              <Check className="w-4 h-4 text-indigo-400" />
              {message}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium transition-colors"
            >
              {isAr ? "إلغاء" : "Cancel"}
            </button>
            <button
              type="submit"
              disabled={loading || !inputToken.trim()}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
            >
              {loading ? (isAr ? "جاري الحفظ..." : "Saving...") : (isAr ? "حفظ التوكن" : "Save Token")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
