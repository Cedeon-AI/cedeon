"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import {
  asProblem,
  changeMemberRole,
  createInvitation,
  getCurrentUser,
  listInvitations,
  listMembers,
  removeMember,
  resendInvitation,
  revokeInvitation,
} from "@/lib/api";

export function SettingsMembersView() {
  const queryClient = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [error, setError] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);

  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => (await getCurrentUser({ throwOnError: true })).data,
  });
  const isAdmin = me.data?.role === "admin";

  const members = useQuery({
    queryKey: ["memberships"],
    queryFn: async () => (await listMembers({ throwOnError: true })).data.members,
  });
  const invitations = useQuery({
    queryKey: ["invitations"],
    enabled: isAdmin,
    queryFn: async () => (await listInvitations({ throwOnError: true })).data.invitations,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["memberships"] });
    queryClient.invalidateQueries({ queryKey: ["invitations"] });
  };

  const invite = useMutation({
    mutationFn: async () => {
      const result = await createInvitation({
        body: { email: inviteEmail.trim(), role: inviteRole as "admin" | "member" },
      });
      if (result.error) throw result.error;
      return result.data;
    },
    onSuccess: (data) => {
      setError(null);
      setInviteEmail("");
      setDevLink(data?.accept_url ?? null);
      refresh();
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not send the invitation."),
  });

  const changeRole = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => {
      const result = await changeMemberRole({
        path: { user_id: userId },
        body: { role: role as "admin" | "member" },
      });
      if (result.error) throw result.error;
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not change the role."),
    onSuccess: () => {
      setError(null);
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: async (userId: string) => {
      const result = await removeMember({ path: { user_id: userId } });
      if (result.error) throw result.error;
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not remove the member."),
    onSuccess: () => {
      setError(null);
      refresh();
    },
  });

  const resend = useMutation({
    mutationFn: async (id: string) => {
      const result = await resendInvitation({ path: { invitation_id: id } });
      if (result.error) throw result.error;
      return result.data;
    },
    onSuccess: (data) => {
      setDevLink(data?.accept_url ?? null);
      refresh();
    },
  });

  const revoke = useMutation({
    mutationFn: async (id: string) => {
      const result = await revokeInvitation({ path: { invitation_id: id } });
      if (result.error) throw result.error;
    },
    onSuccess: refresh,
  });

  const busy = invite.isPending || changeRole.isPending || remove.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Members"
        description="Everyone with access to this Cedeon organization. Admins can invite teammates, change roles, and remove access."
      />

      {isAdmin ? (
        <Card>
          <CardHeader>
            <CardTitle>Invite a teammate</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Work email" htmlFor="invite-email">
                <Input
                  id="invite-email"
                  type="email"
                  placeholder="teammate@yourcompany.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-72"
                />
              </Field>
              <Field label="Role" htmlFor="invite-role">
                <Select
                  id="invite-role"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </Select>
              </Field>
              <Button
                onClick={() => invite.mutate()}
                disabled={invite.isPending || inviteEmail.trim() === ""}
              >
                <Plus /> {invite.isPending ? "Sending…" : "Send invitation"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">Member</span> — day-to-day reinsurance work.{" "}
              <span className="font-medium">Admin</span> — also manages the organization and its
              people.
            </p>
            {devLink ? (
              <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs">
                No mail provider is configured — share this link directly:{" "}
                <span className="break-all font-mono">{devLink}</span>
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {error ? (
        <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Active members</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <tbody>
              {(members.data ?? []).map((m) => (
                <tr key={m.user_id} className="border-b border-border/60 last:border-0">
                  <td className="px-4 py-3">
                    <span className="font-medium">{m.name}</span>
                    {m.is_self ? (
                      <span className="ml-1.5 text-xs text-muted-foreground">(you)</span>
                    ) : null}
                    <span className="block text-xs text-muted-foreground">{m.email}</span>
                  </td>
                  <td className="px-2 py-3">
                    {isAdmin ? (
                      <Select
                        aria-label={`Role for ${m.name}`}
                        value={m.role}
                        disabled={busy}
                        onChange={(e) =>
                          changeRole.mutate({ userId: m.user_id, role: e.target.value })
                        }
                        className="w-28"
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </Select>
                    ) : (
                      <Badge tone="neutral">{m.role}</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isAdmin ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              m.is_self
                                ? "Leave this organization? You'll lose access immediately."
                                : `Remove ${m.name}? They lose access immediately; their work and audit history stay.`,
                            )
                          ) {
                            remove.mutate(m.user_id);
                          }
                        }}
                      >
                        {m.is_self ? "Leave" : "Remove"}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {isAdmin && (invitations.data?.length ?? 0) > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Pending invitations</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <tbody>
                {invitations.data?.map((inv) => (
                  <tr key={inv.id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-3">
                      <span className="font-medium">{inv.email}</span>
                      <span className="block text-xs text-muted-foreground">
                        {inv.role} · invited {new Date(inv.created_at).toLocaleDateString()} ·
                        expires {new Date(inv.expires_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => resend.mutate(inv.id)}
                        disabled={resend.isPending}
                      >
                        Resend
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => revoke.mutate(inv.id)}
                        disabled={revoke.isPending}
                      >
                        Cancel
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
