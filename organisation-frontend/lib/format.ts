/**
 * Money is an integer number of santim everywhere (1 ETB = 100 santim): it is
 * shown by integer division and typed amounts are parsed digit by digit, so
 * no float ever holds an amount.
 */

const GROUP = /\B(?=(\d{3})+(?!\d))/g;

/** 123450 -> "1,234.50"; with `currency`, "ETB 1,234.50". */
export function formatEtb(santim: number | null | undefined, currency = true): string {
  const value = Number.isSafeInteger(santim) ? (santim as number) : 0;
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  const whole = ((abs - (abs % 100)) / 100).toString().replace(GROUP, ",");
  const fraction = (abs % 100).toString().padStart(2, "0");
  return `${currency ? "ETB " : ""}${sign}${whole}.${fraction}`;
}

/** "1,234.5" -> 123450; null when it is not an amount in birr (at most 2 decimals). */
export function parseEtb(text: string): number | null {
  const cleaned = text.trim().replace(/,/g, "").replace(/^ETB\s*/i, "");
  const match = /^(\d{1,11})(?:\.(\d{1,2}))?$/.exec(cleaned);
  if (!match) return null;
  const santim = Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
  return Number.isSafeInteger(santim) ? santim : null;
}

/** 123450 -> "1234.50", for an input box. */
export function santimToInput(santim: number): string {
  return formatEtb(santim, false).replace(/,/g, "");
}

const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "Africa/Addis_Ababa" });
const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Africa/Addis_Ababa",
});

/** "2026-10-20" or an ISO timestamp -> "20 Oct 2026". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00+03:00`) : new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : DATE.format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : `${DATE_TIME.format(date)} EAT`;
}

/** "2026-03" -> "Mar 2026". */
export function formatMonth(value: string): string {
  const [year, month] = value.split("-");
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${names[Number(month) - 1] ?? month} ${year}`;
}

/** Today in Addis Ababa, as YYYY-MM-DD. */
export function todayIso(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Addis_Ababa" }).format(new Date());
}

export function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "?"
  );
}

/** A share of a whole as a whole percent (for bars); integers only. */
export function percentOf(part: number, whole: number): number {
  if (!whole) return 0;
  return Math.round((part * 100) / whole);
}

export const PAYOUT_LABELS: Record<string, string> = {
  cbe: "Commercial Bank of Ethiopia",
  awash: "Awash Bank",
  dashen: "Dashen Bank",
  telebirr: "Telebirr",
};
