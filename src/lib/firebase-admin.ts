import { initializeApp, getApps, getApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

let firebaseConfig: any = null;
try {
  const configPath = join(process.cwd(), 'firebase-applet-config.json');
  if (existsSync(configPath)) {
    firebaseConfig = JSON.parse(readFileSync(configPath, 'utf8'));
  }
} catch (e: any) {
  console.warn("[Firebase] Could not load config:", e.message);
}

let auth: any = null;

if (getApps().length > 0) {
  auth = getAuth(getApp());
} else if (firebaseConfig?.projectId) {
  try {
    const app = initializeApp({
      projectId: firebaseConfig.projectId,
    });
    auth = getAuth(app);
    console.log("[Firebase] Admin SDK initialized successfully.");
  } catch (e: any) {
    console.error("[Firebase] Initialization error:", e.message);
  }
} else {
  console.warn("[Firebase] No Project ID found or config missing. Authentication will be disabled.");
}

export const adminAuth = auth;
