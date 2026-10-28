"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type SidebarProps = {
  open: boolean;
  onClose: () => void;
  pendingCount: number | null;
};

const navItems = [
  { path: "overview", label: "Overview", icon: "dashboard", href: "/" },
  { path: "claims", label: "Claims", icon: "fact_check", href: "/claims" },
  { path: "payments", label: "Payments", icon: "credit_card", href: "/payments" },
  { path: "employees", label: "Employees", icon: "group", href: "/employees" },
  { path: "reports", label: "Reports", icon: "bar_chart", href: "/reports" },
  { path: "settings", label: "Policy & Settings", icon: "tune", href: "/settings" },
  { path: "connect", label: "Connect your system", icon: "hub", href: "/connect" },
];

function activePathFrom(pathname: string) {
  if (pathname === "/") return "overview";
  const seg = pathname.split("/")[1];
  return seg || "overview";
}

export default function Sidebar({ open, onClose, pendingCount }: SidebarProps) {
  const pathname = usePathname();
  const active = activePathFrom(pathname);

  return (
    <>
      {open ? (
        <button
          aria-label="Close menu"
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={onClose}
          type="button"
        />
      ) : null}
      <aside
        className={`fixed left-0 top-0 h-full w-64 bg-surface-container-low  z-50 flex flex-col justify-between transform transition-transform duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex flex-col">
          <div className="h-16 px-space-lg flex items-center gap-space-sm">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt="Endod Health Logo" className="h-8 w-auto object-contain" src="/endod_logo.jpeg" />
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-primary tracking-tight">Endod Health</span>
            </div>
          </div>
          <div className="px-space-md py-space-sm">
            <nav className="flex flex-col gap-space-xs">
              {navItems.map((item) => {
                const isActive = active === item.path;
                const base = "group flex items-center justify-between px-space-md py-2.5 transition-all rounded-lg";
                const cls = isActive
                  ? `${base} bg-primary text-on-primary font-semibold`
                  : `${base} text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface`;
                const badge = item.path === "claims" && pendingCount ? String(pendingCount) : null;
                return (
                  <Link
                    key={item.path}
                    href={item.href}
                    aria-current={isActive ? "page" : undefined}
                    className={cls}
                    onClick={onClose}
                  >
                    <div className="flex items-center gap-space-md">
                      <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{item.icon}</span>
                      <span className="font-label-lg text-label-lg">{item.label}</span>
                    </div>
                    {badge ? (
                      <span
                        data-testid="pending-badge"
                        className="bg-secondary-container text-on-secondary-container font-label-sm text-label-sm px-2 py-0.5 rounded-full"
                      >
                        {badge}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      </aside>
    </>
  );
}
