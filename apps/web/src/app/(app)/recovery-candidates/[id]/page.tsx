import { RecoveryCandidateDetailView } from "@/components/app/recovery-candidate-detail-view";

export const metadata = { title: "Recovery" };

export default async function RecoveryCandidatePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RecoveryCandidateDetailView candidateId={id} />;
}
