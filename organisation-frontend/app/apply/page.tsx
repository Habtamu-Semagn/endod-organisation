import type { Metadata } from "next";
import ApplyWizard from "@/components/apply/ApplyWizard";

export const metadata: Metadata = {
  title: "TenaCare | Apply as a company",
  description: "Apply to give your employees medication benefits through Endod.",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <ApplyWizard />;
}
