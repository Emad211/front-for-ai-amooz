'use client';

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  ArrowLeftRight,
  CalendarCheck2,
  ChevronDown,
  Download,
  GraduationCap,
  Link2,
  Loader2,
  NotebookPen,
  RefreshCw,
  Target,
  Timer,
  UserRoundCheck,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';

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
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useWorkspace } from '@/hooks/use-workspace';
import { formatPersianNumber, toPersianDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import {
  downloadOrgAdvisorReportXlsx,
  getOrgAdvisorReport,
  getOrgOverview,
  reassignEngagement,
  type OrgAdvisorReport,
  type OrgAdvisorRow,
  type OrgAdvisorStudentRow,
  type OrgOverview,
} from '@/services/advisory-org';
import {
  startImpersonation,
  targetLandingFor,
} from '@/services/impersonation-service';

/**
 * The thin org-manager advisory panel (risman step 3) at /org/advisory.
 *
 * Three backend reads + one write, exactly: overview counters, the
 * per-advisor report over a window (۷/۳۰/۹۲-day chips), the Excel export of
 * that same report, and the single guarded write — moving a student to
 * another advisor. Plus the step-4 entry: the «ورود مستقیم» mint.
 *
 * The backend resolves tenancy from the manager's own ACTIVE admin/deputy
 * membership, so this component only needs the org id for the impersonation
 * start; every panel request is id-free.
 */

const PRESETS: { days: number; label: string }[] = [
  { days: 7, label: '۷ روز گذشته' },
  { days: 30, label: '۳۰ روز گذشته' },
  { days: 92, label: '۹۲ روز گذشته' },
];

/** Local-time ISO date (`YYYY-MM-DD`) — never `toISOString`, whose UTC shift
 * answers «yesterday» for any evening request west of Greenwich. */
function isoOf(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Inclusive window of the last `days` days ending today. */
function windowFor(days: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to);
  from.setDate(from.getDate() - (days - 1));
  return { from: isoOf(from), to: isoOf(to) };
}

function coverageLabel(value: number | null): string {
  // Quiet-null doctrine: «ثبت نشده», never a fake 0٪.
  return value === null ? 'ثبت نشده' : `${toPersianDigits(value)}٪`;
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

export function OrgAdvisoryPanel() {
  const { workspaces, activeWorkspace, isLoading: workspaceLoading } = useWorkspace();

  // The org this manager oversees — the impersonation start needs its id.
  const managedOrgId = useMemo(() => {
    const managed = workspaces.find(
      (w) => w.orgRole === 'admin' || w.orgRole === 'deputy',
    );
    if (managed) return managed.id;
    if (
      activeWorkspace &&
      (activeWorkspace.orgRole === 'admin' || activeWorkspace.orgRole === 'deputy')
    ) {
      return activeWorkspace.id;
    }
    return null;
  }, [workspaces, activeWorkspace]);

  const [presetDays, setPresetDays] = useState<number>(7);
  const [range, setRange] = useState(() => windowFor(7));
  const [overview, setOverview] = useState<OrgOverview | null>(null);
  const [report, setReport] = useState<OrgAdvisorReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedAdvisorId, setExpandedAdvisorId] = useState<number | null>(null);

  // Excel state
  const [downloading, setDownloading] = useState(false);

  // Reassign-dialog state
  const [reassignTarget, setReassignTarget] = useState<{
    advisor: OrgAdvisorRow;
    student: OrgAdvisorStudentRow;
  } | null>(null);
  const [chosenAdvisorId, setChosenAdvisorId] = useState<string>('');
  const [reassigning, setReassigning] = useState(false);

  // Impersonation-confirm state
  const [impTarget, setImpTarget] = useState<OrgAdvisorRow | null>(null);
  const [impStarting, setImpStarting] = useState(false);

  // A preset change re-derives the window; the load effect follows the range.
  useEffect(() => {
    setRange(windowFor(presetDays));
  }, [presetDays]);

  const load = useCallback(async () => {
    // The backend resolves tenancy from the manager's own membership, so the
    // data calls need no org id at all — only the impersonation start does.
    setLoading(true);
    setError(null);
    try {
      const [ov, rep] = await Promise.all([
        getOrgOverview(),
        getOrgAdvisorReport(range.from, range.to),
      ]);
      setOverview(ov);
      setReport(rep);
    } catch (err) {
      setError(errorMessage(err, 'دریافت اطلاعات ناموفق بود.'));
    } finally {
      setLoading(false);
    }
  }, [range.from, range.to]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleExcel = async () => {
    setDownloading(true);
    try {
      await downloadOrgAdvisorReportXlsx(range.from, range.to);
      toast.success('خروجی اکسل دانلود شد.');
    } catch (err) {
      toast.error(errorMessage(err, 'دریافت خروجی اکسل ناموفق بود.'));
    } finally {
      setDownloading(false);
    }
  };

  const handleReassign = async () => {
    if (!reassignTarget || !chosenAdvisorId) return;
    setReassigning(true);
    try {
      const result = await reassignEngagement(
        reassignTarget.student.engagementId,
        Number(chosenAdvisorId),
      );
      toast.success(`«${result.studentName}» به «${result.advisorName}» جابجا شد.`);
      setReassignTarget(null);
      await load();
    } catch (err) {
      toast.error(errorMessage(err, 'جابجایی ناموفق بود.'));
    } finally {
      setReassigning(false);
    }
  };

  const handleStartImpersonation = async () => {
    if (!impTarget || !managedOrgId) return;
    setImpStarting(true);
    try {
      const session = await startImpersonation({
        orgId: managedOrgId,
        targetUserId: impTarget.advisorId,
        targetName: impTarget.advisorName,
        targetRole: 'ADVISOR',
      });
      // Full navigation: every provider must re-read the swapped identity.
      window.location.href = targetLandingFor(session.targetRole);
    } catch (err) {
      toast.error(errorMessage(err, 'شروع ورود مستقیم ناموفق بود.'));
      setImpStarting(false);
      setImpTarget(null);
    }
  };

  return (
    <PanelShell
      loading={loading}
      error={error}
      overview={overview}
      report={report}
      range={range}
      presetDays={presetDays}
      expandedAdvisorId={expandedAdvisorId}
      downloading={downloading}
      onPresetChange={setPresetDays}
      onRefresh={() => void load()}
      onExcel={handleExcel}
      onToggleAdvisor={(id) => setExpandedAdvisorId((current) => (current === id ? null : id))}
      onImpersonate={(advisor) => setImpTarget(advisor)}
      onReassign={(advisor, student) => {
        setReassignTarget({ advisor, student });
        setChosenAdvisorId('');
      }}
      impTarget={impTarget}
      impStarting={impStarting}
      onImpOpenChange={(open) => {
        if (!open && !impStarting) setImpTarget(null);
      }}
      onImpConfirm={handleStartImpersonation}
      reassignTarget={reassignTarget}
      chosenAdvisorId={chosenAdvisorId}
      reassigning={reassigning}
      onReassignOpenChange={(open) => {
        if (!open && !reassigning) setReassignTarget(null);
      }}
      onChosenAdvisorChange={setChosenAdvisorId}
      onReassignConfirm={handleReassign}
      onReassignCancel={() => setReassignTarget(null)}
    />
  );
}
/* ── presentational pieces ─────────────────────────────────────────────────── */

type PanelShellProps = {
  loading: boolean;
  error: string | null;
  overview: OrgOverview | null;
  report: OrgAdvisorReport | null;
  range: { from: string; to: string };
  presetDays: number;
  expandedAdvisorId: number | null;
  downloading: boolean;
  onPresetChange: (days: number) => void;
  onRefresh: () => void;
  onExcel: () => void;
  onToggleAdvisor: (advisorId: number) => void;
  onImpersonate: (advisor: OrgAdvisorRow) => void;
  onReassign: (advisor: OrgAdvisorRow, student: OrgAdvisorStudentRow) => void;
  impTarget: OrgAdvisorRow | null;
  impStarting: boolean;
  onImpOpenChange: (open: boolean) => void;
  onImpConfirm: () => void;
  reassignTarget: {
    advisor: OrgAdvisorRow;
    student: OrgAdvisorStudentRow;
  } | null;
  chosenAdvisorId: string;
  reassigning: boolean;
  onReassignOpenChange: (open: boolean) => void;
  onChosenAdvisorChange: (value: string) => void;
  onReassignConfirm: () => void;
  onReassignCancel: () => void;
};

function PanelShell(props: PanelShellProps) {
  const {
    loading,
    error,
    overview,
    report,
    range,
    presetDays,
    downloading,
    onPresetChange,
    onRefresh,
    onExcel,
    expandedAdvisorId,
    onToggleAdvisor,
    onImpersonate,
    onReassign,
    impTarget,
    impStarting,
    onImpOpenChange,
    onImpConfirm,
    reassignTarget,
    chosenAdvisorId,
    reassigning,
    onReassignOpenChange,
    onChosenAdvisorChange,
    onReassignConfirm,
    onReassignCancel,
  } = props;

  return (
    <div className="space-y-6" dir="rtl">
      {/* ── header ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-black sm:text-2xl">مشاوره و همکاری‌ها</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            گزارش مشاوران و مدیریت همکاری‌ها
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading} className="gap-1.5">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            به‌روزرسانی
          </Button>
          <Button size="sm" onClick={onExcel} disabled={downloading || loading} className="gap-1.5">
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            خروجی اکسل
          </Button>
        </div>
      </div>

      {/* ── window chips ───────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.map((preset) => (
          <Button
            key={preset.days}
            variant={presetDays === preset.days ? 'default' : 'outline'}
            size="sm"
            onClick={() => onPresetChange(preset.days)}
          >
            {preset.label}
          </Button>
        ))}
        <span className="mr-auto text-xs text-muted-foreground">
          بازه: از {formatPersianDate(range.from)} تا {formatPersianDate(range.to)}
        </span>
      </div>

      {error ? (
        <Card className="border-destructive/40">
          <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
            <p className="text-sm font-bold text-destructive">{error}</p>
            <Button variant="outline" size="sm" onClick={onRefresh}>
              تلاش مجدد
            </Button>
          </CardContent>
        </Card>
      ) : loading && !report ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 7 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-72 rounded-xl" />
        </div>
      ) : (
        <>
          <StatCards overview={overview} loading={loading} />
          <AdvisorTable
            report={report}
            loading={loading}
            expandedAdvisorId={expandedAdvisorId}
            onToggleAdvisor={onToggleAdvisor}
            onImpersonate={onImpersonate}
            onReassign={onReassign}
          />
        </>
      )}

      <ImpersonationConfirmDialog
        target={impTarget}
        starting={impStarting}
        onOpenChange={onImpOpenChange}
        onConfirm={onImpConfirm}
      />

      <ReassignDialog
        target={reassignTarget}
        chosenAdvisorId={chosenAdvisorId}
        reassigning={reassigning}
        allAdvisors={report?.advisors ?? []}
        onOpenChange={onReassignOpenChange}
        onChosenAdvisorChange={onChosenAdvisorChange}
        onConfirm={onReassignConfirm}
        onCancel={onReassignCancel}
      />
    </div>
  );
}

function StatCards({
  overview,
  loading,
}: {
  overview: OrgOverview | null;
  loading: boolean;
}) {
  if (loading && !overview) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
    );
  }

  const cards: { key: string; label: string; value: string; icon: ReactNode }[] = [];
  if (overview) {
    cards.push(
      {
        key: 'students',
        label: 'دانش‌آموزان فعال',
        value: formatPersianNumber(overview.activeStudents),
        icon: <Users className="h-4 w-4 text-primary" />,
      },
      {
        key: 'advisors',
        label: 'مشاوران فعال',
        value: formatPersianNumber(overview.activeAdvisors),
        icon: <GraduationCap className="h-4 w-4 text-primary" />,
      },
      {
        key: 'engagements',
        label: 'همکاری‌های فعال',
        value: formatPersianNumber(overview.activeEngagements),
        icon: <Link2 className="h-4 w-4 text-primary" />,
      },
      {
        key: 'weekPlans',
        label: 'برنامه‌های این هفته',
        value: formatPersianNumber(overview.weekPlansPublished),
        icon: <CalendarCheck2 className="h-4 w-4 text-primary" />,
      },
      {
        key: 'logsToday',
        label: 'گزارش‌های امروز',
        value: formatPersianNumber(overview.logsToday),
        icon: <NotebookPen className="h-4 w-4 text-primary" />,
      },
      {
        key: 'minutesToday',
        label: 'دقیقهٔ مطالعهٔ امروز',
        value: formatPersianNumber(overview.minutesToday),
        icon: <Timer className="h-4 w-4 text-primary" />,
      },
      {
        key: 'coverage',
        label: 'میانگین اجرای هفته',
        value:
          overview.avgCommitmentPercent === null
            ? 'ثبت نشده'
            : `${toPersianDigits(overview.avgCommitmentPercent)}٪`,
        icon: <Target className="h-4 w-4 text-primary" />,
      },
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.key}>
          <CardContent className="flex items-center justify-between gap-2 p-4">
            <div className="min-w-0">
              <p className="truncate text-xs text-muted-foreground">{card.label}</p>
              <p className="mt-1 truncate text-2xl font-black tabular-nums sm:text-3xl">
                {card.value}
              </p>
            </div>
            <div className="shrink-0 rounded-lg bg-primary/10 p-2">{card.icon}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

type AdvisorTableProps = {
  report: OrgAdvisorReport | null;
  loading: boolean;
  expandedAdvisorId: number | null;
  onToggleAdvisor: (advisorId: number) => void;
  onImpersonate: (advisor: OrgAdvisorRow) => void;
  onReassign: (advisor: OrgAdvisorRow, student: OrgAdvisorStudentRow) => void;
};

function AdvisorTable({
  report,
  loading,
  expandedAdvisorId,
  onToggleAdvisor,
  onImpersonate,
  onReassign,
}: AdvisorTableProps) {
  const advisors = report?.advisors ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="h-4 w-4" />
          گزارش مشاوران
        </CardTitle>
        <CardDescription>
          بر اساس میانگین اجرای گروه، برنامه‌ها و ارزیابی‌های هر مشاور در بازهٔ انتخابی
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-64 rounded-lg" />
        ) : advisors.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            هیچ همکاری فعال سازمانی پیدا نشد.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>مشاور</TableHead>
                  <TableHead>دانش‌آموزان</TableHead>
                  <TableHead>برنامه (دقیقه)</TableHead>
                  <TableHead>مطالعه (دقیقه)</TableHead>
                  <TableHead>اجرا</TableHead>
                  <TableHead>برنامه‌های منتشرشده</TableHead>
                  <TableHead>ارزیابی</TableHead>
                  <TableHead className="text-left">ورود مستقیم</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {advisors.map((advisor) => (
                  <AdvisorRow
                    key={advisor.advisorId}
                    advisor={advisor}
                    expanded={expandedAdvisorId === advisor.advisorId}
                    onToggle={() => onToggleAdvisor(advisor.advisorId)}
                    onImpersonate={() => onImpersonate(advisor)}
                    onReassign={onReassign}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
type AdvisorRowProps = {
  advisor: OrgAdvisorRow;
  expanded: boolean;
  onToggle: () => void;
  onImpersonate: () => void;
  onReassign: (advisor: OrgAdvisorRow, student: OrgAdvisorStudentRow) => void;
};

function AdvisorRow({
  advisor,
  expanded,
  onToggle,
  onImpersonate,
  onReassign,
}: AdvisorRowProps) {
  return (
    <>
      <TableRow
        className="cursor-pointer"
        onClick={onToggle}
        tabIndex={0}
        role="button"
        aria-expanded={expanded}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onToggle();
          }
        }}
      >
        <TableCell>
          <ChevronDown
            className={`h-4 w-4 text-muted-foreground transition-transform ${
              expanded ? 'rotate-180' : ''
            }`}
          />
        </TableCell>
        <TableCell className="font-bold">{advisor.advisorName}</TableCell>
        <TableCell>{toPersianDigits(advisor.studentCount)}</TableCell>
        <TableCell className="tabular-nums">{formatPersianNumber(advisor.planned)}</TableCell>
        <TableCell className="tabular-nums">{formatPersianNumber(advisor.actual)}</TableCell>
        <TableCell>
          <CoverageBadge value={advisor.coveragePercent} />
        </TableCell>
        <TableCell className="tabular-nums">{toPersianDigits(advisor.plansPublished)}</TableCell>
        <TableCell className="tabular-nums">{toPersianDigits(advisor.assessmentsWritten)}</TableCell>
        <TableCell className="text-left">
          <Button
            variant="outline"
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              onImpersonate();
            }}
            className="gap-1"
          >
            <UserRoundCheck className="h-3.5 w-3.5" />
            ورود
          </Button>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={9} className="bg-muted/40 p-4">
            <div className="space-y-2">
              {advisor.students.length === 0 ? (
                <p className="text-sm text-muted-foreground">دانش‌آموزی ثبت نشده است.</p>
              ) : (
                advisor.students.map((student) => (
                  <div
                    key={student.engagementId}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2"
                  >
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                      <span className="font-semibold">{student.studentName}</span>
                      <span className="text-muted-foreground">
                        برنامه: {formatPersianNumber(student.planned)} دقیقه
                      </span>
                      <span className="text-muted-foreground">
                        مطالعه: {formatPersianNumber(student.actual)} دقیقه
                      </span>
                      <span className="text-muted-foreground">
                        آزمون‌ها: {toPersianDigits(student.testsTaken)}
                      </span>
                      <CoverageBadge value={student.coveragePercent} />
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onReassign(advisor, student)}
                      className="gap-1"
                    >
                      <ArrowLeftRight className="h-3.5 w-3.5" />
                      جابجایی
                    </Button>
                  </div>
                ))
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function CoverageBadge({ value }: { value: number | null }) {
  const tone =
    value === null
      ? 'bg-muted text-muted-foreground'
      : value >= 80
        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
        : value >= 50
          ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
          : 'bg-red-500/10 text-red-700 dark:text-red-400';

  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold tabular-nums ${tone}`}
    >
      {coverageLabel(value)}
    </span>
  );
}
type ReassignDialogProps = {
  target: {
    advisor: OrgAdvisorRow;
    student: OrgAdvisorStudentRow;
  } | null;
  chosenAdvisorId: string;
  reassigning: boolean;
  allAdvisors: OrgAdvisorRow[];
  onOpenChange: (open: boolean) => void;
  onChosenAdvisorChange: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
};

function ReassignDialog({
  target,
  chosenAdvisorId,
  reassigning,
  allAdvisors,
  onOpenChange,
  onChosenAdvisorChange,
  onConfirm,
  onCancel,
}: ReassignDialogProps) {
  const candidates = target
    ? allAdvisors.filter((advisor) => advisor.advisorId !== target.advisor.advisorId)
    : [];

  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent dir="rtl" className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>جابجایی دانش‌آموز</DialogTitle>
          <DialogDescription>
            «{target?.student.studentName}» از مشاور «{target?.advisor.advisorName}» به
            مشاور دیگری از همین سازمان منتقل می‌شود.
          </DialogDescription>
        </DialogHeader>
        <Select value={chosenAdvisorId} onValueChange={onChosenAdvisorChange} dir="rtl">
          <SelectTrigger className="w-full">
            <SelectValue placeholder="مشاور مقصد را انتخاب کنید" />
          </SelectTrigger>
          <SelectContent>
            {candidates.map((advisor) => (
              <SelectItem key={advisor.advisorId} value={String(advisor.advisorId)}>
                {advisor.advisorName} ({toPersianDigits(advisor.studentCount)} دانش‌آموز)
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" disabled={reassigning} onClick={onCancel}>
            انصراف
          </Button>
          <Button disabled={!chosenAdvisorId || reassigning} onClick={onConfirm} className="gap-1.5">
            {reassigning ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowLeftRight className="h-4 w-4" />}
            جابجایی
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type ImpersonationConfirmDialogProps = {
  target: OrgAdvisorRow | null;
  starting: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
};

function ImpersonationConfirmDialog({
  target,
  starting,
  onOpenChange,
  onConfirm,
}: ImpersonationConfirmDialogProps) {
  const advisorName = target?.advisorName ?? '';

  return (
    <AlertDialog open={target !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent dir="rtl">
        <AlertDialogHeader>
          <AlertDialogTitle>ورود مستقیم به حساب مشاور</AlertDialogTitle>
          <AlertDialogDescription>
            شما با حساب «{advisorName}» وارد پنل مشاور می‌شوید و تا ۳۰ دقیقه
            همه‌چیز را دقیقاً همان‌طور که او می‌بیند خواهید دید. پس از پایان،
            دکمهٔ «پایان جلسه» شما را به همین صفحه برمی‌گرداند. تمام اقدامات در
            این حالت با هویت خودِ او ثبت می‌شود.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={starting}>انصراف</AlertDialogCancel>
          <AlertDialogAction
            disabled={starting}
            onClick={(event) => {
              event.preventDefault();
              onConfirm();
            }}
            className="gap-1.5"
          >
            {starting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <UserRoundCheck className="h-4 w-4" />
            )}
            ورود به حساب
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}