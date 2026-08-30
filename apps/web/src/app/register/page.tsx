import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthCard } from "@/components/auth/auth-card";
import { RegisterForm } from "@/components/auth/register-form";
import { getSession } from "@/lib/session";

export const metadata = { title: "Create an organization" };

export default async function RegisterPage() {
  if (await getSession()) redirect("/dashboard");
  return (
    <AuthCard
      title="Create your organization"
      subtitle="You'll be the owner. Add colleagues once you're in."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <RegisterForm />
    </AuthCard>
  );
}
