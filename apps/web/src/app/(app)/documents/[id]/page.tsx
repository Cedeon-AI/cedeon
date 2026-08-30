import { DocumentDetailView } from "@/components/app/document-detail-view";

export const metadata = { title: "Document" };

export default async function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DocumentDetailView documentId={id} />;
}
