import { LossEventDetailView } from "@/components/app/loss-event-detail-view";

export const metadata = { title: "Loss event" };

export default async function LossEventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LossEventDetailView eventId={id} />;
}
