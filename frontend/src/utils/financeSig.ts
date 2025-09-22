// Reuse this type or adapt to your shape
export type FinancialRow = {
  id?: string | number;
  row_id?: string | number;
  variable_name?: string;
  current_amount?: number | string | null;
  previous_amount?: number | string | null;
  note?: string | number | null;
  children?: FinancialRow[];
  [k: string]: any;
};

const toNum = (v: any) => {
  if (v === null || v === undefined) return 0;
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0;
  if (typeof v === 'string') {
    const n = parseFloat(v.replace(/\s/g, '').replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
};

const q = (n: number) => n.toFixed(2); // quantize to 2 decimals to avoid float jitter

const rowSig = (r: FinancialRow): string => {
  const key = String(r.id ?? r.row_id ?? r.variable_name ?? '');
  const ca = q(toNum(r.current_amount));
  const pa = q(toNum(r.previous_amount));
  const vn = String(r.variable_name ?? '');
  const note = String(r.note ?? '');
  const child = Array.isArray(r.children) && r.children.length
    ? '|' + r.children.map(rowSig).join('')
    : '';
  return `${key}^${vn}^${ca}^${pa}^${note}${child}`;
};

// order-insensitive, content-sensitive hash
export function computeFinancialSig(rows: FinancialRow[] | undefined | null): string {
  const safe = Array.isArray(rows) ? rows : [];
  const normalized = [...safe]
    .sort((a, b) => {
      const ak = String(a.id ?? a.row_id ?? a.variable_name ?? '');
      const bk = String(b.id ?? b.row_id ?? b.variable_name ?? '');
      return ak.localeCompare(bk);
    })
    .map(rowSig)
    .join('|');

  // djb2 (xor variant), returns short stable token
  let h = 5381;
  for (let i = 0; i < normalized.length; i++) {
    h = ((h << 5) + h) ^ normalized.charCodeAt(i);
  }
  return `h${(h >>> 0).toString(36)}_${safe.length}`;
}

export function computeCombinedFinancialSig(
  rr: FinancialRow[] | undefined | null,
  br: FinancialRow[] | undefined | null
): string {
  return `${computeFinancialSig(br)}||${computeFinancialSig(rr)}`;
}
