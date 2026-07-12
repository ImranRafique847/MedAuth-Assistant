"use client";
import { useState } from "react";

export default function AgentCard({ name, data }: { name: string; data: any }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-panelLine rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm hover:bg-panel/40 transition"
      >
        <span className="font-mono-data text-paper/80 capitalize">{name} agent</span>
        <span className="text-muted text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <pre className="px-4 pb-4 text-xs text-muted font-mono-data overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
