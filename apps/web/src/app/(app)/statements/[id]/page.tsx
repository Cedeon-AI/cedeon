import { StatementDetailView } from "@/components/app/statement-detail-view";

export const metadata = { title: "Statement" };

export default async function StatementPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StatementDetailView statementId={id} />;
}
