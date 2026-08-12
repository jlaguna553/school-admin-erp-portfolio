'use client';

import { Loader2, Plus, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FormField } from '@/components/ui/form-field';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toApiError } from '@/lib/api-client';
import type { PlatformIdentity } from '@erp/api-types';

import { useAssignableRoles, useInstitutions } from '../api/use-platform';
import { useGrantMembership, useRevokeMembership } from '../api/use-identities';

interface IdentitySchoolsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  identity: PlatformIdentity | null;
}

/**
 * Which schools a person may sign in to, and as what.
 *
 * Each row is a membership: the fact that grants access. Revoking one blocks
 * sign-in at that school on the next attempt but leaves the school's own user
 * row intact, so the invoices they issued still name them.
 */
export function IdentitySchoolsDialog({
  open,
  onOpenChange,
  identity,
}: IdentitySchoolsDialogProps) {
  const t = useTranslations('platform');
  const tc = useTranslations('common');
  const tu = useTranslations('users');

  const { data: institutions } = useInstitutions({ page_size: 200, ordering: 'name' });
  const { data: roles = [] } = useAssignableRoles();
  const grant = useGrantMembership();
  const revoke = useRevokeMembership();

  const [tenant, setTenant] = useState('');
  const [role, setRole] = useState('school_admin');

  const memberships = (identity?.memberships ?? []).filter((m) => m.is_active);
  const grantedIds = new Set(memberships.map((m) => m.tenant));
  const available = (institutions?.results ?? []).filter(
    (institution) => institution.is_active && !grantedIds.has(institution.id),
  );

  async function onGrant() {
    if (!identity || !tenant) return;
    try {
      await grant.mutateAsync({ identityId: identity.id, tenant, role });
      toast.success(t('accessGranted'));
      setTenant('');
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  async function onRevoke(membershipId: string) {
    if (!identity) return;
    try {
      await revoke.mutateAsync({ identityId: identity.id, membershipId });
      toast.success(t('accessRevoked'));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={tc('close')}>
        <DialogHeader>
          <DialogTitle>{t('schoolsFor', { name: identity?.full_name ?? '' })}</DialogTitle>
          <DialogDescription>{t('schoolsForHint')}</DialogDescription>
        </DialogHeader>

        <ul className="space-y-2">
          {memberships.length === 0 ? (
            <li className="rounded-md border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
              {t('noSchoolsYet')}
            </li>
          ) : (
            memberships.map((membership) => (
              <li
                key={membership.id}
                className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{membership.tenant_name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {membership.tenant_schema}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Badge variant="outline">{tu(`roles.${membership.role}`)}</Badge>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`${t('revokeAccess')}: ${membership.tenant_name}`}
                    disabled={revoke.isPending}
                    onClick={() => onRevoke(membership.id)}
                  >
                    <X aria-hidden />
                  </Button>
                </div>
              </li>
            ))
          )}
        </ul>

        <div className="grid gap-2 border-t border-border pt-4 sm:grid-cols-[1fr_auto_auto]">
          <FormField id="grant_tenant" label={t('grantSchool')}>
            <Select value={tenant} onValueChange={setTenant}>
              <SelectTrigger id="grant_tenant">
                <SelectValue placeholder={t('selectSchool')} />
              </SelectTrigger>
              <SelectContent>
                {available.map((institution) => (
                  <SelectItem key={institution.id} value={institution.id}>
                    {institution.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <FormField id="grant_role" label={tu('role')}>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger id="grant_role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {roles.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <div className="flex items-end pb-1">
            <Button type="button" onClick={onGrant} disabled={!tenant || grant.isPending}>
              {grant.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Plus aria-hidden />}
              {t('grant')}
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {tc('close')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
