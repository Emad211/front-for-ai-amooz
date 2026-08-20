'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { UserPlus, Building2, Check, X } from 'lucide-react';

import {
  AdvisoryService,
  type StudentInvite,
} from '@/services/advisory-service';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

/**
 * The student-side accept banner for advisor invites.
 *
 * Mounted once in the dashboard layout, so it must be *quiet*: it renders nothing
 * at all — no skeleton, no wrapper — until it knows there is an invite to show.
 * The overwhelming majority of students have none, and a placeholder that pushed
 * every dashboard page down by a banner's height on load would be a worse bug
 * than the feature is a benefit. A failed fetch is likewise swallowed: a student
 * mid-study should never see an advisory error they did not ask for.
 *
 * Accepting grants a stranger read access to this student's study log from today
 * on, so the button is theirs alone (the endpoint re-verifies the session against
 * the invited phone). Rejecting is terminal — the same advisor is blocked for 30
 * days — so it is gated behind a confirm dialog rather than a bare click.
 */
export function AdvisorInviteBanner() {
  const [invites, setInvites] = useState<StudentInvite[]>([]);
  // The invite id currently being accepted/rejected, so only its own buttons
  // disable — a student with two invites can still act on the other.
  const [busyId, setBusyId] = useState<number | null>(null);
  // The invite awaiting reject confirmation; null closes the dialog.
  const [confirmReject, setConfirmReject] = useState<StudentInvite | null>(null);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyEngagement()
      .then((data) => {
        if (active) setInvites(data.invites);
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  const removeInvite = (id: number) =>
    setInvites((prev) => prev.filter((inv) => inv.id !== id));

  const handleAccept = async (invite: StudentInvite) => {
    setBusyId(invite.id);
    try {
      await AdvisoryService.acceptInvite(invite.id);
      toast.success(`همکاری با «${invite.advisorName}» آغاز شد.`);
      // Drop it locally rather than refetching: the row is now ACTIVE and would
      // no longer appear in `invites` anyway, and this keeps the banner from
      // flashing empty→populated if the student has a second pending invite.
      removeInvite(invite.id);
    } catch (err: unknown) {
      // 404 (expired/mismatched) and 409 (already has an advisor) both surface
      // their Persian detail here; the student learns why without a code.
      toast.error(err instanceof Error ? err.message : 'پذیرش دعوت‌نامه ناموفق بود.');
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (invite: StudentInvite) => {
    setBusyId(invite.id);
    try {
      await AdvisoryService.rejectInvite(invite.id);
      toast.success('دعوت‌نامه رد شد.');
      removeInvite(invite.id);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'رد دعوت‌نامه ناموفق بود.');
    } finally {
      setBusyId(null);
      setConfirmReject(null);
    }
  };

  if (invites.length === 0) return null;

  return (
    <div dir="rtl" className="mx-auto w-full max-w-7xl px-4 pt-4 md:px-8">
      <div className="space-y-2">
        {invites.map((invite) => {
          const busy = busyId === invite.id;
          return (
            <div
              key={invite.id}
              className="flex flex-wrap items-center gap-3 rounded-xl border border-primary/30 bg-primary/5 p-3 sm:p-4"
            >
              <span className="rounded-lg bg-primary/10 p-2">
                <UserPlus className="h-5 w-5 text-primary" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  «{invite.advisorName}» شما را به همکاری مشاوره دعوت کرده است.
                </p>
                <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  {invite.mode === 'org' && invite.organizationName ? (
                    <span className="inline-flex items-center gap-1">
                      <Building2 className="h-3 w-3" />
                      {invite.organizationName}
                    </span>
                  ) : null}
                  <span>
                    با پذیرش، مشاور می‌تواند برنامهٔ مطالعهٔ شما را از امروز به بعد ببیند.
                  </span>
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => handleAccept(invite)}
                  disabled={busy}
                >
                  <Check className="ml-1.5 h-4 w-4" />
                  {busy ? '…' : 'پذیرش'}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setConfirmReject(invite)}
                  disabled={busy}
                >
                  <X className="ml-1.5 h-4 w-4" />
                  رد
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Reject is terminal — confirm before the 30-day block lands. */}
      <AlertDialog
        open={confirmReject !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmReject(null);
        }}
      >
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>رد دعوت‌نامه</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmReject
                ? `دعوت‌نامهٔ «${confirmReject.advisorName}» رد شود؟ این مشاور تا ۳۰ روز نمی‌تواند دوباره شما را دعوت کند.`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busyId !== null}>انصراف</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                // Keep the dialog mounted through the request; handleReject
                // closes it in its finally block so a failure keeps it open.
                e.preventDefault();
                if (confirmReject) handleReject(confirmReject);
              }}
              disabled={busyId !== null}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              رد دعوت‌نامه
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
