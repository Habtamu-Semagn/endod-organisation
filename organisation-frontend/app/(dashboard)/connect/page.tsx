import type { Metadata } from "next";
import ConnectPage from "@/components/connect/ConnectPage";

export const metadata: Metadata = {
  title: "TenaCare | Connect your system",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <ConnectPage />;
}
