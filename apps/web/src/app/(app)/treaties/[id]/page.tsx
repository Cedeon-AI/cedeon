import { TreatyDetailView } from "@/components/app/treaty-detail-view";

export const metadata = { title: "Treaty" };

export default async function TreatyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TreatyDetailView treatyId={id} />;
}
