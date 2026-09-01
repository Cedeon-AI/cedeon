import type { ReactNode } from "react";
import { SettingsNav } from "@/components/app/settings-nav";
import { BackLink } from "@/components/ui/page-header";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <BackLink href="/dashboard">Home</BackLink>
      <div className="flex flex-col gap-8 lg:flex-row">
        <SettingsNav />
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}
