import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthCard } from "@/components/auth/auth-card";
import { RegisterForm } from "@/components/auth/register-form";
import { getSignupMode } from "@/lib/auth-config";
import { getSession } from "@/lib/session";

export const metadata = { title: "Create an organization" };

export default async function RegisterPage() {
  if (await getSession()) redirect("/dashboard");
  const signupMode = await getSignupMode();

  if (signupMode === "closed") {
    return (
      <AuthCard
        title="Cedeon is invite-only"
        subtitle="We're onboarding teams one at a time right now."
        footer={
          <>
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </>
        }
      >
        <p className="text-sm text-muted-foreground">
          To request access, email{" "}
          <a href="mailto:access@cedeon.ai" className="font-medium text-primary hover:underline">
            access@cedeon.ai
          </a>
          . If a colleague already uses Cedeon, ask them to invite you.
        </p>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create your organization's workspace"
      subtitle="You'll start as an admin. Invite your team once you're set up."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <RegisterForm needsCode={signupMode === "code"} />
    </AuthCard>
  );
}
