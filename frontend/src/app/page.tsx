"use client";

import dynamic from "next/dynamic";

const MissionControl = dynamic(() => import("@/components/MissionControl"), { ssr: false });

export default function Home() {
  return (
    <main className="min-h-screen bg-[#020617]">
      <MissionControl />
    </main>
  );
}

