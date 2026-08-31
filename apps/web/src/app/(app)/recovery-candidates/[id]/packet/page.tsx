import { redirect } from "next/navigation";

export default async function PacketRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/recovery-candidates/${id}?section=packet`);
}
