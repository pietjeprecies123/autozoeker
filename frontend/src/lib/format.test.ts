import { describe, expect, it } from "vitest";
import { dealLabel, euro, km } from "./format";

describe("format", () => {
  it("formats euros and km the Dutch way", () => {
    expect(euro(15950)).toBe("€ 15.950");
    expect(km(123456)).toBe("123.456 km");
    expect(euro(null)).toBe("–");
  });
  it("labels deals", () => {
    expect(dealLabel(0.12).tone).toBe("good");
    expect(dealLabel(0.0).text).toBe("Marktconform");
    expect(dealLabel(-0.1).tone).toBe("bad");
    expect(dealLabel(null).tone).toBe("none");
  });
});
