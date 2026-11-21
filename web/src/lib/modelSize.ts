export const MIN_RECOMMENDED_B = 9;

export function paramBillions(model: string): number | null {
  const re = /(?:^|[:\-_ /])([ea]?)(\d+(?:\.\d+)?)([bm])(?![a-z0-9])/gi;
  const sizes: number[] = [];
  for (const m of model.matchAll(re)) {
    if (m[1].toLowerCase() === "a") continue;
    const n = parseFloat(m[2]);
    sizes.push(m[3].toLowerCase() === "m" ? n / 1000 : n);
  }
  return sizes.length ? Math.max(...sizes) : null;
}

export function looksTooSmall(model: string): boolean {
  const b = paramBillions(model);
  return b !== null && b < MIN_RECOMMENDED_B;
}