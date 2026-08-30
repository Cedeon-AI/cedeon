import { RecoveryPacketView } from "@/components/app/recovery-packet-view";

export const metadata = { title: "Recovery packet" };

export default async function RecoveryPacketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RecoveryPacketView candidateId={id} />;
}
