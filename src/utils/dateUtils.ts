export function parseISO(dateStr: string): Date {
  return new Date(dateStr);
}

export function differenceInMonths(later: Date, earlier: Date): number {
  return (
    (later.getFullYear() - earlier.getFullYear()) * 12 +
    (later.getMonth() - earlier.getMonth())
  );
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
}
