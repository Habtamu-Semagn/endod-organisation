import { Suspense } from "react";
import ClaimDetailClient from "./ClaimDetailClient";

async function ClaimDetailContent({
  paramsPromise,
}: {
  paramsPromise: Promise<{ id: string }>;
}) {
  const { id } = await paramsPromise;
  return <ClaimDetailClient id={id} />;
}

export default function ClaimDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense fallback={<div className="p-8">Loading claim...</div>}>
      <ClaimDetailContent paramsPromise={params} />
    </Suspense>
  );
}