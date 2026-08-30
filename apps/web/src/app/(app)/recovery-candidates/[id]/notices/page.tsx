import { RecoveryNoticesView } from "@/components/app/recovery-notices-view";

export const metadata = { title: "Notices" };

export default async function RecoveryNoticesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RecoveryNoticesView candidateId={id} />;
}
