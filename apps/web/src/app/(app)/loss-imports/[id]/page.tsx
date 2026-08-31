import { LossImportDetailView } from "@/components/app/loss-import-detail-view";

export const metadata = { title: "Claim import" };

export default async function LossImportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LossImportDetailView importId={id} />;
}
