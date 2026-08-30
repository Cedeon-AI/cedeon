import { ValidationWorkspace } from "@/components/app/validation-workspace";

export const metadata = { title: "Validation workspace" };

export default async function ValidatePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ValidationWorkspace treatyId={id} />;
}
