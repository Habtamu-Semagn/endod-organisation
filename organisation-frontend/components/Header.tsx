"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { initials } from "@/lib/format";
import type { Me } from "@/lib/types";

type HeaderProps = {
  onMenuClick?: () => void;
  me: Me | null;
  onSignOut: () => void;
};

export default function Header({ onMenuClick, me, onSignOut }: HeaderProps) {
  const router = useRouter();
  const [q, setQ] = useState("");

  return (
    <header className="fixed top-0 left-0 lg:left-64 right-0 h-16 bg-surface z-40 flex items-center justify-between px-space-md sm:px-space-xl gap-space-md sm:gap-space-lg">
      <button
        aria-label="Open menu"
        className="lg:hidden p-2 rounded-full hover:bg-surface-container-high text-on-surface-variant"
        onClick={onMenuClick}
        type="button"
      >
        <span aria-hidden="true" className="material-symbols-outlined text-[22px]">menu</span>
      </button>
      <form
        className="flex-1 max-w-xl"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          const term = q.trim();
          router.push(term ? `/claims?q=${encodeURIComponent(term)}` : "/claims");
        }}
      >
        <div className="relative flex items-center">
          <span aria-hidden="true" className="material-symbols-outlined absolute left-3 text-outline text-[20px]">search</span>
          <input
            aria-label="Search claims"
            className="w-full h-10 pl-10 pr-4 bg-surface-container-lowest rounded-lg font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary "
            placeholder="Search claims by employee, pharmacy, receipt or claim number..."
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </form>
      <div className="flex items-center gap-space-md sm:gap-space-lg">
        <div className="h-8 w-px bg-surface-container-high"></div>
        <div className="flex items-center gap-space-sm">
          <div className="w-8 h-8 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-[12px]">
            {me ? initials(me.admin.name) : ""}
          </div>
          <div className="hidden sm:flex flex-col text-left">
            <span data-testid="signed-in-name" className="font-label-md text-label-md text-on-surface font-semibold">
              {me?.admin.name ?? ""}
            </span>
            <span data-testid="signed-in-organisation" className="font-label-sm text-label-sm text-on-surface-variant">
              {me?.organisation.name ?? ""}
            </span>
          </div>
          <button
            type="button"
            onClick={onSignOut}
            className="ml-space-sm inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container-low hover:bg-surface-container-high text-on-surface-variant font-label-md text-label-md"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">logout</span>
            <span>Sign out</span>
          </button>
        </div>
      </div>
    </header>
  );
}
