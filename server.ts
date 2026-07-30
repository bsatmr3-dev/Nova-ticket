import express from "express";
import path from "path";
import fs from "fs";
import { spawn, execFileSync, ChildProcess } from "child_process";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";
import JSZip from "jszip";
import { requireAuth } from "./src/middleware/auth";

dotenv.config();

const app = express();
const PORT = parseInt(process.env.PORT || "3000", 10);

console.log(`[System] Initializing server on port ${PORT}...`);

app.use(express.json());

// Health Check for Cloud Run / Container Monitoring
app.get("/health", (req, res) => {
  res.status(200).send("OK");
});

// Bot Process Management
let botProcess: ChildProcess | null = null;
const botLogs: string[] = ["System initialized. Ready to start Discord Ticket Bot."];

function addLog(message: string) {
  const timestamp = new Date().toLocaleTimeString();
  botLogs.push(`[${timestamp}] ${message}`);
  if (botLogs.length > 500) {
    botLogs.shift();
  }
}

// Helper to resolve bot token from .env, env, or SQLite DB
function getStoredToken(): string {
  if (fs.existsSync(".env")) {
    const envContent = fs.readFileSync(".env", "utf-8");
    const tokenMatch = envContent.match(/DISCORD_BOT_TOKEN=["']?([^"'\n\r]+)["']?/);
    if (tokenMatch && tokenMatch[1] && tokenMatch[1] !== "YOUR_DISCORD_BOT_TOKEN_HERE" && tokenMatch[1].trim().length > 10) {
      return tokenMatch[1].trim();
    }
  }

  if (process.env.DISCORD_BOT_TOKEN && process.env.DISCORD_BOT_TOKEN !== "YOUR_DISCORD_BOT_TOKEN_HERE" && process.env.DISCORD_BOT_TOKEN.trim().length > 10) {
    return process.env.DISCORD_BOT_TOKEN.trim();
  }

  try {
    const dbData = runCliApi("get_bot_token", {});
    if (dbData && dbData.token && dbData.token.length > 10) {
      return dbData.token.trim();
    }
  } catch {
    // ignore
  }

  return "";
}

// ----------------------------------------------------
// API ROUTES
// ----------------------------------------------------

// 1. Get Bot Status & Env Secret State
app.get("/api/bot/status", (req, res) => {
  const currentToken = getStoredToken();
  const hasToken = Boolean(currentToken && currentToken !== "YOUR_DISCORD_BOT_TOKEN_HERE" && currentToken.length > 10);
  const maskedToken = hasToken ? `${currentToken.substring(0, 6)}...${currentToken.substring(currentToken.length - 4)}` : "";

  res.json({
    isRunning: botProcess !== null && !botProcess.killed,
    hasToken,
    maskedToken,
    pid: botProcess ? botProcess.pid : null,
    uptime: botProcess ? Math.floor(process.uptime()) : 0
  });
});

// Helper to find working python executable
function getPythonExecutable(): string {
  const candidates = [
    "python3",
    "python",
    "/usr/bin/python3",
    "/usr/local/bin/python3",
    "/opt/venv/bin/python3",
    "/opt/venv/bin/python",
    "/usr/bin/python",
    "/usr/local/bin/python"
  ];
  for (const cmd of candidates) {
    try {
      execFileSync(cmd, ["--version"], { stdio: "ignore" });
      return cmd;
    } catch {
      // try next
    }
  }
  return "python3";
}

// Helper function to launch Python Discord Bot
function launchBotProcess() {
  const pythonCmd = getPythonExecutable();

  // Always clean up any orphan/lingering bot process before launching
  try {
    execFileSync("pkill", ["-f", `${pythonCmd} -m bot.main`]);
  } catch {
    // Ignore if no lingering process existed
  }

  if (botProcess && !botProcess.killed) {
    return { success: false, message: "Bot is already running." };
  }

  dotenv.config({ override: true });
  const token = getStoredToken();
  if (!token || token === "YOUR_DISCORD_BOT_TOKEN_HERE" || token.trim().length < 10) {
    return { success: false, message: "Please enter a valid Discord Bot Token first!" };
  }

  process.env.DISCORD_BOT_TOKEN = token;
  if (!fs.existsSync(".env")) {
    fs.writeFileSync(".env", `DISCORD_BOT_TOKEN=${token}\n`);
  }

  addLog(`🚀 Launching Python Discord Bot process (${pythonCmd} -m bot.main)...`);

  try {
    botProcess = spawn(pythonCmd, ["-m", "bot.main"], {
      cwd: process.cwd(),
      env: { ...process.env, DISCORD_BOT_TOKEN: token, PYTHONUNBUFFERED: "1", PYTHONPATH: process.cwd() }
    });

    botProcess.on("error", (err: any) => {
      addLog(`❌ Bot process error: ${err.message}`);
      botProcess = null;
    });

    botProcess.stdout?.on("data", (data) => {
      const output = data.toString().trim();
      if (output) {
        addLog(`[STDOUT] ${output}`);
        if (output.includes("Bot logged in successfully as")) {
          console.log("Discord bot connected");
        }
      }
    });

    botProcess.stderr?.on("data", (data) => {
      const output = data.toString().trim();
      if (output) addLog(`[STDERR] ${output}`);
    });

    botProcess.on("close", (code) => {
      addLog(`🛑 Bot process exited with code ${code}`);
      botProcess = null;
    });

    return { success: true, message: "Bot starting...", pid: botProcess.pid };
  } catch (err: any) {
    addLog(`❌ Failed to start bot: ${err.message}`);
    return { success: false, message: err.message };
  }
}

// 2. Save Discord Bot Token Secret & Auto-Start Bot
app.post("/api/bot/token", (req, res) => {
  const { token } = req.body;
  if (!token || typeof token !== "string" || token.trim().length < 10) {
    return res.status(400).json({ error: "Invalid token provided. Discord tokens are usually ~70 characters long." });
  }

  const cleanToken = token.trim().replace(/^["']|["']$/g, '').trim();
  let envContent = "";
  if (fs.existsSync(".env")) {
    envContent = fs.readFileSync(".env", "utf-8");
  } else if (fs.existsSync(".env.example")) {
    envContent = fs.readFileSync(".env.example", "utf-8");
  }

  if (envContent.includes("DISCORD_BOT_TOKEN=")) {
    envContent = envContent.replace(/DISCORD_BOT_TOKEN=.*/, `DISCORD_BOT_TOKEN=${cleanToken}`);
  } else {
    envContent += `\nDISCORD_BOT_TOKEN=${cleanToken}\n`;
  }

  fs.writeFileSync(".env", envContent);
  process.env.DISCORD_BOT_TOKEN = cleanToken;

  try {
    runCliApi("save_bot_token", { token: cleanToken });
  } catch {
    // ignore
  }

  addLog("🔑 Discord Bot Token updated successfully in .env and database.");

  // Automatically auto-start the bot immediately upon token submission
  const launchResult = launchBotProcess();
  res.json({ success: true, message: "Bot token saved successfully! " + launchResult.message, botStarted: launchResult.success });
});

// 3. Start Python Bot
app.post("/api/bot/start", (req, res) => {
  const result = launchBotProcess();
  if (!result.success) {
    return res.status(400).json({ error: result.message });
  }
  res.json(result);
});

// 4. Stop Python Bot
app.post("/api/bot/stop", (req, res) => {
  if (!botProcess) {
    return res.status(400).json({ error: "Bot is not running." });
  }

  botProcess.kill("SIGTERM");
  botProcess = null;
  addLog("🛑 Sent SIGTERM to stop bot process.");
  res.json({ success: true, message: "Bot process stopped." });
});

// 4b. Sync / Update Bot Commands
app.post("/api/bot/sync-commands", async (req, res) => {
  addLog("🔄 Request received: Syncing & Updating Bot Slash Commands...");
  const wasRunning = botProcess !== null && !botProcess.killed;

  if (wasRunning && botProcess) {
    addLog("⏸️ Temporarily pausing bot process to sync commands with Discord API...");
    botProcess.kill("SIGTERM");
    botProcess = null;
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }

  try {
    const data = runCliApi("sync_commands", {});
    if (data.success) {
      addLog(`✅ Slash Commands Synced: ${data.message}`);
    } else {
      addLog(`⚠️ Commands Sync Warning: ${data.error}`);
    }

    // Automatically restart bot if it was running previously
    let autoRestarted = false;
    if (wasRunning) {
      addLog("▶️ Restarting bot process after command sync...");
      const startRes = launchBotProcess();
      autoRestarted = startRes.success;
    }

    res.json({
      success: data.success,
      message: data.message || data.error,
      autoRestarted,
      details: data
    });
  } catch (err: any) {
    addLog(`❌ Failed to sync bot commands: ${err.message}`);
    res.status(500).json({ success: false, error: err.message });
  }
});

// 5. Get Bot Logs
app.get("/api/bot/logs", (req, res) => {
  res.json({ logs: botLogs });
});

// 6. Get Codebase File Tree
function getDirectoryTree(dirPath: string, relativeDir = ""): any[] {
  if (!fs.existsSync(dirPath)) return [];
  try {
    const items = fs.readdirSync(dirPath);
    const result: any[] = [];

    for (const item of items) {
      if (["node_modules", ".git", "dist", ".cache", "__pycache__"].includes(item)) continue;
      const fullPath = path.join(dirPath, item);
      const relPath = path.join(relativeDir, item);
      const stat = fs.statSync(fullPath);

      if (stat.isDirectory()) {
        result.push({
          name: item,
          type: "directory",
          path: relPath,
          children: getDirectoryTree(fullPath, relPath)
        });
      } else {
        result.push({
          name: item,
          type: "file",
          path: relPath,
          size: stat.size
        });
      }
    }

    return result;
  } catch {
    return [];
  }
}

app.get("/api/codebase/tree", (req, res) => {
  try {
    const botPath = path.join(process.cwd(), "bot");
    const botTree = fs.existsSync(botPath) ? getDirectoryTree(botPath, "bot") : [];
    const tree = [
      ...botTree,
      ...(fs.existsSync("requirements.txt") ? [{ name: "requirements.txt", type: "file", path: "requirements.txt" }] : []),
      ...(fs.existsSync("README.md") ? [{ name: "README.md", type: "file", path: "README.md" }] : []),
      ...(fs.existsSync(".env.example") ? [{ name: ".env.example", type: "file", path: ".env.example" }] : [])
    ];
    res.json({ tree });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// 7. Get File Content
app.get("/api/codebase/file", (req, res) => {
  const filePath = req.query.path as string;
  if (!filePath) return res.status(400).json({ error: "Path parameter missing" });

  const safePath = path.normalize(filePath).replace(/^(\.\.[\/\\])+/, "");
  const fullPath = path.join(process.cwd(), safePath);

  if (!fs.existsSync(fullPath)) {
    return res.status(404).json({ error: "File not found" });
  }

  const content = fs.readFileSync(fullPath, "utf-8");
  res.json({ path: filePath, content });
});

// 8. Download Codebase as ZIP
app.get("/api/codebase/download-zip", async (req, res) => {
  try {
    const zip = new JSZip();

    function addDirToZip(dirPath: string, zipFolder: JSZip) {
      const items = fs.readdirSync(dirPath);
      for (const item of items) {
        if (["node_modules", ".git", "dist", "__pycache__"].includes(item)) continue;
        const fullPath = path.join(dirPath, item);
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory()) {
          const subFolder = zipFolder.folder(item);
          if (subFolder) addDirToZip(fullPath, subFolder);
        } else {
          const content = fs.readFileSync(fullPath);
          zipFolder.file(item, content);
        }
      }
    }

    addDirToZip(path.join(process.cwd(), "bot"), zip.folder("bot")!);
    if (fs.existsSync("requirements.txt")) zip.file("requirements.txt", fs.readFileSync("requirements.txt"));
    if (fs.existsSync("README.md")) zip.file("README.md", fs.readFileSync("README.md"));
    if (fs.existsSync(".env.example")) zip.file(".env.example", fs.readFileSync(".env.example"));

    const zipBuffer = await zip.generateAsync({ type: "nodebuffer" });
    res.setHeader("Content-Type", "application/zip");
    res.setHeader("Content-Disposition", 'attachment; filename="discord_ticket_bot_python.zip"');
    res.send(zipBuffer);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// 9. Interactive HTML Transcript Preview Demo
app.get("/api/transcript/demo", (req, res) => {
  const sampleHtml = `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Transcript #ticket-0042</title>
    <style>
        body { background-color: #313338; color: #dbdee1; font-family: sans-serif; padding: 20px; }
        .header { background: #2b2d31; padding: 16px; border-radius: 8px; margin-bottom: 20px; border-right: 4px solid #5865f2; }
        .msg { display: flex; gap: 12px; margin-bottom: 16px; padding: 8px; border-radius: 6px; }
        .msg:hover { background: #2e3035; }
        .avatar { width: 40px; height: 40px; border-radius: 50%; }
        .author { font-weight: bold; color: #fff; margin-left: 8px; }
        .time { font-size: 12px; color: #949ba4; }
        .bot { background: #5865f2; color: #fff; font-size: 10px; padding: 2px 4px; border-radius: 4px; }
        .embed { background: #2b2d31; border-right: 4px solid #57f287; padding: 10px; border-radius: 4px; margin-top: 6px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>🎫 تذكرة دعم فني #ticket-0042</h2>
        <p>القسم: دعم عام | العميل: @Ahmed_User | تاريخ الإغلاق: 2026-07-27 10:30 UTC</p>
    </div>
    <div class="msg">
        <img class="avatar" src="https://cdn.discordapp.com/embed/avatars/0.png" />
        <div>
            <div><span class="author">Ahmed_User</span> <span class="time">10:15 AM</span></div>
            <div>السلام عليكم، لدي استفسار بخصوص تفعيل اشتراك السيرفر.</div>
        </div>
    </div>
    <div class="msg">
        <img class="avatar" src="https://cdn.discordapp.com/embed/avatars/1.png" />
        <div>
            <div><span class="author">Support_Manager</span> <span class="bot">BOT STAFF</span> <span class="time">10:17 AM</span></div>
            <div>وعليكم السلام ورحمة الله! أهلاً بك أحمد، تم التحقق من الاشتراك وتفعيله بنجاح.</div>
            <div class="embed">
                <strong>✅ حالة الطلب: مكتمل</strong>
                <p>تم شحن الرصيد والتفعيل تلقائياً.</p>
            </div>
        </div>
    </div>
</body>
</html>`;
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(sampleHtml);
});

// 10. Web Control Center API Endpoints (Settings, Roles, Logs Channel, Panels, Blacklist)
app.use("/api/control", requireAuth);

function runCliApi(command: string, args: object = {}): any {
  try {
    const pythonCmd = getPythonExecutable();
    const jsonStr = JSON.stringify(args);
    const rawResultStr = execFileSync(pythonCmd, ["bot/cli_api.py", command, jsonStr], {
      encoding: "utf-8",
      timeout: 30000,
      env: { ...process.env, PYTHONPATH: process.cwd() }
    });
    const lines = rawResultStr.trim().split("\n").map(l => l.trim()).filter(Boolean);
    for (let i = lines.length - 1; i >= 0; i--) {
      try {
        const parsed = JSON.parse(lines[i]);
        if (parsed && typeof parsed === "object") {
          return parsed;
        }
      } catch {
        // Ignore non-JSON lines (e.g. log output)
      }
    }
    return { success: false, error: rawResultStr };
  } catch (err: any) {
    return { success: false, error: err.message || "Failed to execute Python CLI API" };
  }
}

app.get("/api/control/bot-token", (req, res) => {
  const data = runCliApi("get_bot_token", {});
  res.json(data);
});

app.post("/api/control/bot-token", (req, res) => {
  const data = runCliApi("save_bot_token", req.body);
  res.json(data);
});

app.get("/api/control/guilds", (req, res) => {
  const data = runCliApi("get_guilds", {});
  res.json(data);
});

app.get("/api/control/guild-details", (req, res) => {
  const guild_id = req.query.guild_id || "0";
  const data = runCliApi("get_guild_details", { guild_id });
  res.json(data);
});

app.get("/api/control/settings", (req, res) => {
  const data = runCliApi("get_settings", { guild_id: 0 });
  res.json(data);
});

app.post("/api/control/settings", (req, res) => {
  const data = runCliApi("save_settings", { guild_id: 0, ...req.body });
  res.json(data);
});

app.get("/api/control/panels", (req, res) => {
  const data = runCliApi("get_panels", {});
  res.json(data);
});

app.post("/api/control/panels", (req, res) => {
  const data = runCliApi("save_panel", req.body);
  res.json(data);
});

app.post("/api/control/panels/delete", (req, res) => {
  const data = runCliApi("delete_panel", req.body);
  res.json(data);
});

app.post("/api/control/panels/dispatch", (req, res) => {
  const data = runCliApi("dispatch_panel", req.body);
  res.json(data);
});

app.get("/api/control/blacklist", (req, res) => {
  const data = runCliApi("get_blacklist", {});
  res.json(data);
});

app.post("/api/control/blacklist/add", (req, res) => {
  const data = runCliApi("add_blacklist", req.body);
  res.json(data);
});

app.post("/api/control/blacklist/remove", (req, res) => {
  const data = runCliApi("remove_blacklist", req.body);
  res.json(data);
});

// Explicit API 404 handler to prevent API requests from falling back to Vite HTML index.html
app.use("/api/*", (req, res) => {
  res.status(404).json({ error: `API route not found: ${req.originalUrl}` });
});

// Vite middleware
async function startServer() {
  // Start listening immediately to satisfy Cloud Run health check
  const server = app.listen(PORT, "0.0.0.0", () => {
    console.log(`Web server started on port ${PORT}`);
    console.log(`Server URL: http://0.0.0.0:${PORT}`);
    
    // Auto-launch bot if token is present
    if (process.env.DISCORD_BOT_TOKEN && process.env.DISCORD_BOT_TOKEN.trim().length > 10) {
      addLog("⚡ DISCORD_BOT_TOKEN detected on startup. Attempting auto-launch...");
      try {
        launchBotProcess();
      } catch (botError) {
        console.error("[System] Failed to launch bot process:", botError);
        addLog(`❌ Failed to launch bot: ${botError}`);
      }
    }
  });

  server.on('error', (err: any) => {
    if (err.code === 'EADDRINUSE') {
      console.error(`[System] Port ${PORT} is already in use.`);
    } else {
      console.error("[System] Server error:", err);
    }
  });

  // Setup middleware after starting to listen (non-blocking)
  try {
    if (process.env.NODE_ENV !== "production") {
      console.log("[System] Initializing Vite development middleware...");
      const vite = await createViteServer({
        server: { middlewareMode: true },
        appType: "spa",
      });
      app.use(vite.middlewares);
    } else {
      console.log("[System] Initializing production static file serving...");
      const distPath = path.join(process.cwd(), "dist");
      app.use(express.static(distPath));
      app.get("*", (req, res) => {
        res.sendFile(path.join(distPath, "index.html"));
      });
    }
    console.log("[System] Middleware initialization complete.");
  } catch (error) {
    console.error("[System] Failed to initialize middleware:", error);
  }
}

startServer().catch(err => {
  console.error("[System] Critical startup failure:", err);
});
