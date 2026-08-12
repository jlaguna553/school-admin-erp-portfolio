'use client';

import { CalendarRange, Loader2, Plus, Save } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useAllPrograms } from '@/features/academic/api/use-academic';
import { useSubjects } from '@/features/academic/api/use-academic';
import { toApiError } from '@/lib/api-client';

import { useGradebook, useRecordGrades, useTermOptions } from '../api/use-grades';
import { AssessmentFormDialog } from './assessment-form-dialog';
import { TermFormDialog } from './term-form-dialog';

/**
 * One subject, one period: every enrolled student down, every assessment across.
 *
 * Marks are edited a column at a time and saved a column at a time, because
 * that is how marking is actually done — a teacher sits with one exam and works
 * down the list. It also means a dropped connection leaves a column either
 * saved or not, instead of half of it.
 *
 * An empty cell is not a zero. The two are different claims about a student, so
 * an unmarked cell stays blank and the average is over what has been marked so
 * far — labelled as such, rather than showing everyone failing until the last
 * exam is in.
 */
export function GradebookView() {
  const t = useTranslations('grades');
  const tc = useTranslations('common');
  const locale = useLocale();

  const { data: terms = [] } = useTermOptions();
  const { data: programs = [] } = useAllPrograms();
  const [subject, setSubject] = useState('');
  const [term, setTerm] = useState('');

  const { data: subjectPage } = useSubjects({ page_size: 200, ordering: 'code' });
  const subjects = useMemo(() => subjectPage?.results ?? [], [subjectPage]);

  // Open on the period the school is actually in, and the first subject, so the
  // screen is useful before anything is chosen.
  useEffect(() => {
    if (!term && terms.length) setTerm((terms.find((row) => row.is_current) ?? terms[0]!).id);
  }, [terms, term]);
  useEffect(() => {
    if (!subject && subjects.length) setSubject(subjects[0]!.id);
  }, [subjects, subject]);

  const { data: book, isPending } = useGradebook(subject, term);
  const record = useRecordGrades();

  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});
  const [addingAssessment, setAddingAssessment] = useState(false);
  const [addingTerm, setAddingTerm] = useState(false);

  // Anything typed is dropped when the grid underneath changes, rather than
  // being written to whichever column now sits in that position.
  useEffect(() => setDraft({}), [subject, term]);

  const numberFormat = useMemo(
    () => new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    [locale],
  );

  async function saveColumn(assessmentId: string) {
    const column = draft[assessmentId];
    if (!column) return;

    const entries = Object.entries(column).map(([enrollmentId, value]) => ({
      enrollment_id: enrollmentId,
      // Empty clears the mark; it is not a zero.
      score: value.trim() === '' ? null : value.trim(),
    }));

    try {
      await record.mutateAsync({ assessmentId, entries });
      setDraft((current) => {
        const next = { ...current };
        delete next[assessmentId];
        return next;
      });
      toast.success(t('columnSaved'));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const canEdit = book?.can_edit ?? false;
  const programName = programs.find(
    (p) => p.id === subjects.find((s) => s.id === subject)?.program,
  )?.name;

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setAddingTerm(true)}>
              <CalendarRange aria-hidden />
              {t('newTerm')}
            </Button>
            {canEdit && subject && term ? (
              <Button onClick={() => setAddingAssessment(true)}>
                <Plus aria-hidden />
                {t('newAssessment')}
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <label htmlFor="gb-subject" className="mb-1 block text-xs text-muted-foreground">
            {t('subject')}
          </label>
          <Select value={subject} onValueChange={setSubject}>
            <SelectTrigger id="gb-subject">
              <SelectValue placeholder={t('selectSubject')} />
            </SelectTrigger>
            <SelectContent>
              {subjects.map((row) => (
                <SelectItem key={row.id} value={row.id}>
                  {row.code} · {row.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="min-w-56">
          <label htmlFor="gb-term" className="mb-1 block text-xs text-muted-foreground">
            {t('term')}
          </label>
          <Select value={term} onValueChange={setTerm}>
            <SelectTrigger id="gb-term">
              <SelectValue placeholder={t('selectTerm')} />
            </SelectTrigger>
            <SelectContent>
              {terms.map((row) => (
                <SelectItem key={row.id} value={row.id}>
                  {row.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {programName ? <Badge variant="outline">{programName}</Badge> : null}
        {!canEdit && book ? <Badge variant="neutral">{t('readOnly')}</Badge> : null}
      </div>

      {isPending ? (
        <Skeleton className="h-72" />
      ) : terms.length === 0 ? (
        <p className="rounded-md border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {t('noTerms')}
        </p>
      ) : !book || book.assessments.length === 0 ? (
        <p className="rounded-md border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {t('noAssessments')}
        </p>
      ) : (
        <div className="w-full overflow-x-auto rounded-md border border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="w-full max-w-0 px-3 py-2 text-left font-medium">{t('student')}</th>
                {book.assessments.map((assessment) => (
                  <th key={assessment.id} className="whitespace-nowrap px-3 py-2 text-left">
                    <span className="block font-medium">{assessment.name}</span>
                    <span className="block text-xs font-normal text-muted-foreground">
                      /{assessment.max_score} · ×{assessment.weight}
                    </span>
                    {canEdit && draft[assessment.id] ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-1"
                        disabled={record.isPending}
                        onClick={() => saveColumn(assessment.id)}
                      >
                        {record.isPending ? (
                          <Loader2 className="animate-spin" aria-hidden />
                        ) : (
                          <Save aria-hidden />
                        )}
                        {tc('save')}
                      </Button>
                    ) : null}
                  </th>
                ))}
                <th className="whitespace-nowrap px-3 py-2 text-right font-medium">
                  {t('average')}
                  <span className="block text-xs font-normal text-muted-foreground">
                    /{book.average_scale}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {book.rows.map((row) => (
                <tr key={row.enrollment_id} className="border-b border-border last:border-0">
                  <td className="w-full max-w-0 px-3 py-1.5">
                    <span className="block truncate">{row.student_name}</span>
                  </td>
                  {book.assessments.map((assessment) => {
                    const saved = row.scores[assessment.id] ?? '';
                    const typed = draft[assessment.id]?.[row.enrollment_id];
                    return (
                      <td key={assessment.id} className="px-3 py-1.5">
                        {canEdit ? (
                          <Input
                            inputMode="decimal"
                            className="h-8 w-20 text-right"
                            aria-label={`${assessment.name} · ${row.student_name}`}
                            value={typed ?? String(saved)}
                            onChange={(event) =>
                              setDraft((current) => ({
                                ...current,
                                [assessment.id]: {
                                  ...current[assessment.id],
                                  [row.enrollment_id]: event.target.value,
                                },
                              }))
                            }
                          />
                        ) : (
                          <span className="tabular-nums">{saved || '—'}</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="whitespace-nowrap px-3 py-1.5 text-right font-medium tabular-nums">
                    {row.average === null ? (
                      // Not a zero: nothing has been marked yet.
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      numberFormat.format(Number(row.average))
                    )}
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      ({row.graded_count})
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {book ? (
        <p className="text-xs text-muted-foreground">{t('averageNote')}</p>
      ) : null}

      <TermFormDialog open={addingTerm} onOpenChange={setAddingTerm} />

      <AssessmentFormDialog
        open={addingAssessment}
        onOpenChange={setAddingAssessment}
        subjectId={subject}
        termId={term}
      />
    </div>
  );
}
