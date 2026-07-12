"use client";
import { useState } from "react";
import UploadTab from "@/components/UploadTab";
import ManualTab from "@/components/ManualTab";
import QueueTab from "@/components/QueueTab";

const TABS = [
  { key: "upload", label: "Upload prescription" },
  { key: "manual", label: "Manual entry" },
  { key: "queue", label: "Review queue" },
];

export default function Home() {
  const [tab, setTab] = useState("upload");

  return (
    <main className="min-h-screen">
      <header className="border-b border-panelLine">
        <div className="max-w-5xl mx-auto px-6 py-10">
          <p className="font-mono-data text-xs text-signal-accent tracking-widest uppercase mb-3">
            Payer-side prior authorization
          </p>
          <h1 className="font-display text-4xl md:text-5xl italic font-medium">
            MedAuth Assistant
          </h1>
          <p className="text-muted mt-3 max-w-xl">
            Five agents read every request in sequence — eligibility, compliance,
            clinical necessity, coverage — before a human signs off.
          </p>
        </div>
      </header>

      <nav className="max-w-5xl mx-auto px-6 pt-6">
        <div className="flex gap-1 border-b border-panelLine">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-sm font-mono-data tracking-wide border-b-2 transition-colors ${
                tab === t.key
                  ? "border-signal-accent text-paper"
                  : "border-transparent text-muted hover:text-paper/80"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      <section className="max-w-5xl mx-auto px-6 py-10">
        {tab === "upload" && <UploadTab />}
        {tab === "manual" && <ManualTab />}
        {tab === "queue" && <QueueTab />}
      </section>

      <footer className="max-w-5xl mx-auto px-6 py-10 text-xs text-muted font-mono-data">
        Draft recommendations only — final decisions require human review.
      </footer>
    </main>
  );
}
