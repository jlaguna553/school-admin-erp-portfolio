/**
 * ISO-8601 weekday numbering: Monday is 1, Sunday is 7.
 *
 * The same numbering the API stores, on purpose. JavaScript's `Date.getDay()`
 * counts from Sunday and Django's own `WEEKDAYS` from Monday-as-zero, so there
 * are three conventions within reach of this code; picking the one the database
 * holds means a weekday never has to be converted on the way in or out.
 */
export const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7] as const;

/** Monday to Friday — what a timetable grid shows unless a school works Saturdays. */
export const SCHOOL_WEEK = [1, 2, 3, 4, 5] as const;

export function isoWeekday(date: Date): number {
  return date.getDay() === 0 ? 7 : date.getDay();
}

/** `HH:MM` from the API's `HH:MM:SS`. Seconds are noise on a timetable. */
export function toClock(time: string): string {
  return time.slice(0, 5);
}
