import { describe, expect, it } from "vitest";
import { cn, formatMoney } from "@/lib/utils";

describe("cn", () => {
  it("joins truthy classes", () => {
    expect(cn("a", false, null, undefined, "b")).toBe("a b");
  });
});

describe("formatMoney", () => {
  it("formats USD to two decimals with grouping", () => {
    expect(formatMoney("8700000.00", "USD")).toBe("$8,700,000.00");
  });
  it("accepts lowercase currency", () => {
    expect(formatMoney(1740000, "usd")).toBe("$1,740,000.00");
  });
});
