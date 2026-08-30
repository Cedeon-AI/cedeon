export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

const currencyFormatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(amount: string | number, currency: string): string {
  const key = currency.toUpperCase();
  let formatter = currencyFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: key,
      maximumFractionDigits: 2,
    });
    currencyFormatters.set(key, formatter);
  }
  return formatter.format(typeof amount === "string" ? Number(amount) : amount);
}
