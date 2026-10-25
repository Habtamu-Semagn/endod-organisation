import { Suspense } from "react";
import type { Metadata } from "next";
import SetupForm from "@/components/auth/SetupForm";

export const metadata: Metadata = {
  title: "TenaCare | Set up your account",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <SetupForm />
    </Suspense>
  );
}
