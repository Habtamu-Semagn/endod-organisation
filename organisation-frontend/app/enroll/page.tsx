import { Suspense } from "react";
import type { Metadata } from "next";
import EnrollForm from "@/components/auth/EnrollForm";

export const metadata: Metadata = {
  title: "TenaCare | Two-step verification",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <EnrollForm />
    </Suspense>
  );
}
