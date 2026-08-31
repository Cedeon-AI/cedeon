import { redirect } from "next/navigation";

export default async function NoticesRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/recovery-candidates/${id}?section=notice`);
}
