import { AcceptInvite } from "@/components/auth/accept-invite";
import { AuthCard } from "@/components/auth/auth-card";

export const metadata = { title: "Accept invitation" };

export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return (
    <AuthCard
      title="Join your team on Cedeon"
      subtitle="Accept the invitation to get access to your organization's reinsurance workspace."
    >
      <AcceptInvite token={token} />
    </AuthCard>
  );
}
