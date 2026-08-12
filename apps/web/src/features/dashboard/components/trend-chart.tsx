'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableWrapper,
} from '@/components/ui/table';
import type { TrendPoint } from '../api/dashboard-api';

interface TrendChartProps {
  title: string;
  data: TrendPoint[];
  /** Unit suffix for labels and tooltip, e.g. "%". */
  unit?: string;
  /**
   * Shown instead of the plot when there is nothing to draw.
   *
   * An empty series is the ordinary state of a school that has not started
   * taking the roll, and an axis with no line through it reads as a failure
   * rather than as an absence of data.
   */
  emptyLabel?: string;
}

/**
 * Single-series attendance trend.
 *
 * Chart decisions, all deliberate:
 * - **One series, so no legend** — the card title names the measure.
 * - **No y-axis** line, ticks or labels; four faint horizontal gridlines carry
 *   the scale, and the direct labels carry the values. The axis would be pure
 *   chrome here.
 * - **Selective labels, not one per point**: only the first, last and maximum
 *   are labelled. Labelling all seven turns the plot into a table with a line
 *   through it, so exact values for the rest come from the hover tooltip.
 * - **Crosshair + tooltip by default** — an SVG chart in a browser is
 *   interactive, and hover is how the unlabelled points stay readable.
 * - **Colour is `--chart-1`**, which is re-stepped per theme (validated: >= 3:1
 *   against both surfaces). The token does the theme switch, so there is no
 *   JS colour logic here.
 * - **A table view exists** for screen readers, print and anyone who needs the
 *   numbers rather than the shape.
 */
export function TrendChart({ title, data, unit = '', emptyLabel }: TrendChartProps) {
  const t = useTranslations('dashboard');
  const locale = useLocale();
  const [asTable, setAsTable] = useState(false);

  const weekdayFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' }),
    [locale],
  );
  const fullDateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }),
    [locale],
  );

  const rows = useMemo(
    () =>
      data.map((point) => ({
        ...point,
        label: weekdayFormatter.format(new Date(`${point.date}T00:00:00Z`)),
        fullLabel: fullDateFormatter.format(new Date(`${point.date}T00:00:00Z`)),
      })),
    [data, weekdayFormatter, fullDateFormatter],
  );

  // Indices that get a printed value: endpoints plus the peak.
  const labelledIndices = useMemo(() => {
    if (rows.length === 0) return new Set<number>();
    let maxIndex = 0;
    rows.forEach((row, index) => {
      if (row.value > (rows[maxIndex]?.value ?? -Infinity)) maxIndex = index;
    });
    return new Set([0, rows.length - 1, maxIndex]);
  }, [rows]);

  // Pad the domain so the line never touches the card edges.
  const domain = useMemo<[number, number]>(() => {
    const values = rows.map((row) => row.value);
    if (values.length === 0) return [0, 1];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = Math.max((max - min) * 0.35, 2);
    return [Math.max(0, min - pad), max + pad];
  }, [rows]);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>{title}</CardTitle>
        </div>
        {rows.length > 0 ? (
          <button
            type="button"
            onClick={() => setAsTable((previous) => !previous)}
            aria-pressed={asTable}
            className="shrink-0 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {asTable ? t('viewChart') : t('viewTable')}
          </button>
        ) : null}
      </CardHeader>

      {rows.length === 0 ? (
        <p className="px-5 py-14 text-center text-sm text-muted-foreground">
          {emptyLabel ?? t('noData')}
        </p>
      ) : asTable ? (
        <div className="px-5 pb-5 pt-4">
          <TableWrapper>
            <Table>
              <caption className="sr-only">{title}</caption>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">{t('day')}</TableHead>
                  <TableHead scope="col" className="text-right">
                    {t('value')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.date}>
                    <TableCell>{row.fullLabel}</TableCell>
                    <TableCell className="tabular text-right font-medium">
                      {row.value}
                      {unit}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableWrapper>
        </div>
      ) : (
        <div className="h-64 px-2 pb-4 pt-6">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} margin={{ top: 16, right: 20, bottom: 4, left: 12 }}>
              <defs>
                {/* Area fades to nothing so the fill reads as emphasis, not mass. */}
                <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.22} />
                  <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid
                vertical={false}
                stroke="var(--chart-grid)"
                strokeWidth={1}
              />

              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={false}
                tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
                dy={6}
                // Render every weekday. Recharts' default tick thinning drops
                // whichever label it thinks would collide, and after the
                // table -> chart toggle re-measures the container it silently
                // dropped Monday. Seven short labels always fit, so opt out.
                interval={0}
                minTickGap={0}
              />
              {/* Hidden: the scale is carried by gridlines and direct labels. */}
              <YAxis hide domain={domain} />

              <Tooltip
                cursor={{
                  stroke: 'var(--muted-foreground)',
                  strokeWidth: 1,
                  strokeDasharray: '3 3',
                }}
                // Params are inferred from Recharts' own signature; the narrow
                // props below describe only the fields actually read.
                content={({ active, payload }) => (
                  <TrendTooltip
                    active={Boolean(active)}
                    payload={payload as TrendTooltipProps['payload']}
                    unit={unit}
                  />
                )}
              />

              <Area
                type="monotone"
                dataKey="value"
                stroke="var(--chart-1)"
                strokeWidth={2}
                fill="url(#trend-fill)"
                // A 2px surface ring keeps the dot legible over the fill.
                activeDot={{
                  r: 5,
                  fill: 'var(--chart-1)',
                  stroke: 'var(--card)',
                  strokeWidth: 2,
                }}
                dot={false}
                label={(props: unknown) => (
                  <SelectiveLabel
                    {...(props as SelectiveLabelProps)}
                    labelledIndices={labelledIndices}
                    unit={unit}
                  />
                )}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

interface SelectiveLabelProps {
  x?: number;
  y?: number;
  index?: number;
  value?: number;
}

/** Prints a value only for the endpoints and the peak. */
function SelectiveLabel({
  x,
  y,
  index,
  value,
  labelledIndices,
  unit,
}: SelectiveLabelProps & { labelledIndices: Set<number>; unit: string }) {
  if (
    x === undefined ||
    y === undefined ||
    index === undefined ||
    value === undefined ||
    !labelledIndices.has(index)
  ) {
    return null;
  }

  return (
    <text
      x={x}
      y={y - 10}
      textAnchor="middle"
      // Labels wear text ink, never the series colour.
      fill="var(--muted-foreground)"
      fontSize={11}
      fontWeight={500}
    >
      {value}
      {unit}
    </text>
  );
}

interface TrendTooltipProps {
  active: boolean;
  /** Readonly to match Recharts' own `TooltipPayload`. */
  payload?: ReadonlyArray<{ payload?: { fullLabel?: string; value?: number } }>;
  unit: string;
}

function TrendTooltip({ active, payload, unit }: TrendTooltipProps) {
  if (!active || !payload?.length) return null;

  const point = payload[0]?.payload;
  if (!point || point.value === undefined || point.fullLabel === undefined) return null;

  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      <p className="text-muted-foreground">{point.fullLabel}</p>
      <p className="tabular mt-0.5 flex items-center gap-1.5 font-semibold text-foreground">
        <span
          aria-hidden
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: 'var(--chart-1)' }}
        />
        {point.value}
        {unit}
      </p>
    </div>
  );
}
