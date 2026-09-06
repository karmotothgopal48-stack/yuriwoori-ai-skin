"use client";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import Link from "next/link";
export default function Home() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    getHealth()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));
  }, []);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 text-center">
      <span className="text-sm tracking-widest uppercase text-brand-muted mb-4">
        YuriWoori
      </span>
      <h1 className="font-display text-5xl md:text-6xl text-brand-text mb-6">
        Understand your skin.
      </h1>
      <p className="text-brand-muted max-w-md mb-6">
        A camera that becomes a mirror — AI skin analysis, personalized routines,
        and real Korean skincare, matched to you.
      </p>

      <div className="flex items-center gap-2 mb-10 text-sm">
        <span
          className={`w-2 h-2 rounded-full ${
            backendStatus === "online"
              ? "bg-brand-mint"
              : backendStatus === "offline"
              ? "bg-red-400"
              : "bg-brand-sage animate-pulse"
          }`}
        />
        <span className="text-brand-muted">
          {backendStatus === "checking" && "Connecting to backend…"}
          {backendStatus === "online" && "Backend connected"}
          {backendStatus === "offline" && "Backend offline — is uvicorn running?"}
        </span>
      </div>

      <div className="flex gap-4">
        <Link
  href="/scan/camera"
  className="bg-brand-primary text-white px-6 py-3 rounded-full hover:bg-brand-primary-light transition"
>
  Start Skin Scan
</Link>
        <button className="border border-border-soft text-brand-text px-6 py-3 rounded-full hover:bg-bg-cream-alt transition">
          Explore Products
        </button>
      </div>
    </main>
  );
}