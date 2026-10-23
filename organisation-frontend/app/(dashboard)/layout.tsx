"use client";

import { useState, Suspense } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <>
      <Suspense fallback={null}>
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      </Suspense>
      <Header onMenuClick={() => setSidebarOpen(true)} />
      <div className="pl-0 lg:pl-64 flex flex-col min-h-screen">
        <main className="relative pt-16 w-full px-space-md sm:px-space-xl bg-surface flex-1">
          {children}
        </main>
      </div>
    </>
  );
}