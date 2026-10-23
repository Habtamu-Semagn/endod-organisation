"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type SidebarProps = {
  open: boolean;
  onClose: () => void;
};

const navItems = [
  { path: "overview", label: "Overview", icon: "dashboard", href: "/", badge: null },
  { path: "claims", label: "Claims", icon: "fact_check", href: "/claims", badge: "8" },
  { path: "payments", label: "Payments", icon: "credit_card", href: "/payments", badge: null },
  { path: "employees", label: "Employees", icon: "group", href: "/employees", badge: null },
  { path: "reports", label: "Reports", icon: "bar_chart", href: "/reports", badge: null },
  { path: "settings", label: "Settings", icon: "settings", href: "#", badge: null },
];

function activePathFrom(pathname: string) {
  if (pathname === "/") return "overview";
  const seg = pathname.split("/")[1];
  return seg || "overview";
}

export default function Sidebar({ open, onClose }: SidebarProps) {
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
        className={`fixed left-0 top-0 h-full w-64 bg-surface-container-low shadow-[0_1px_8px_rgba(0,0,0,0.04)] z-50 flex flex-col justify-between transform transition-transform duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex flex-col">
          <div className="h-16 px-space-lg flex items-center gap-space-sm">
            <img
              alt="Endod Health Logo"
              className="h-8 w-auto object-contain"
              src="/endod_logo.jpeg"
            />
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-primary tracking-tight">
                Endod Health
              </span>
            </div>
          </div>
          <div className="px-space-md py-space-sm">
            <nav className="flex flex-col gap-space-xs">
              {navItems.map((item) => {
                const isActive = active === item.path;
                const base =
                  "group flex items-center justify-between px-space-md py-2.5 transition-all rounded-lg";
                const cls = isActive
                  ? `${base} bg-primary-container text-on-primary-container font-semibold shadow-sm`
                  : `${base} text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface`;
                return (
                  <Link
                    key={item.path}
                    href={item.href}
                    aria-current={isActive ? "page" : undefined}
                    className={cls}
                    onClick={onClose}
                  >
                    <div className="flex items-center gap-space-md">
                      <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                      <span className="font-label-lg text-label-lg">{item.label}</span>
                    </div>
                    {item.badge ? (
                      <span className="bg-secondary-container text-on-secondary-container font-label-sm text-label-sm px-2 py-0.5 rounded-full">
                        {item.badge}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
        <div className="p-space-md m-space-md rounded-xl bg-surface-container-lowest shadow-[0_1px_3px_0_rgba(15,23,42,0.04)]">
          <div className="flex items-center gap-space-sm mb-1">
            <span className="material-symbols-outlined text-primary text-[18px]">verified</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              Addis Ababa Clinical Net
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Tier-1 direct billing active for Kenema &amp; Bole Hubs.
          </p>
        </div>
      </aside>
    </>
  );
}