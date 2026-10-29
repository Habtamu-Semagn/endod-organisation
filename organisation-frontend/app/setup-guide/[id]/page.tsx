import { Suspense } from "react";
import type { Metadata } from "next";
import SetupGuide from "@/components/connect/SetupGuide";

export const metadata: Metadata = {
  title: "TenaCare | Setup guide",
  robots: { index: false, follow: false },
};

async function Content({ paramsPromise }: { paramsPromise: Promise<{ id: string }> }) {
  const { id } = await paramsPromise;
  return <SetupGuide id={id} />;
}

/** A printable page for the company's IT team (never the secret). */
export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<p className="p-8">Preparing the setup guide…</p>}>
      <Content paramsPromise={params} />
    </Suspense>
  );
}
