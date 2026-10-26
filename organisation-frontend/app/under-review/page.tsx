import type { Metadata } from "next";
import UnderReview from "@/components/apply/UnderReview";

export const metadata: Metadata = {
  title: "TenaCare | Under review",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <UnderReview />;
}
