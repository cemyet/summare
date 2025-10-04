'use client';
import React, { useMemo } from 'react';

/**
 * PrintAnnualReport
 * A print-only component that mirrors the data already shown in the Preview,
 * without triggering any recalculations. It renders in the exact order required
 * and hides any rows/notes that are hidden/zeroed per current visibility rules.
 *
 * Order (each with a hard page break between):
 * 1) Förvaltningsberättelse
 * 2) Resultaträkning
 * 3) Balansräkning (tillgångar)
 * 4) Balansräkning (Eget kapital och skulder)
 * 5) Noter
 */

export type RRRow = {
  id?: string;
  label: string;
  current_amount: number | null;
  previous_amount: number | null;
  level?: number;
  section?: string; // 'RR'
  bold?: boolean;
  style?: string;
  block_group?: string;
  variable_name?: string;
  show_tag?: boolean;
  always_show?: boolean | null;
  note_number?: number;
};

export type BRRow = {
  id?: string;
  label: string;
  current_amount: number | null;
  previous_amount: number | null;
  level?: number;
  section?: string; // 'BR'
  type: 'asset' | 'liability' | 'equity';
  bold?: boolean;
  style?: string;
  block_group?: string;
  variable_name?: string;
  show_tag?: boolean;
  always_show?: boolean | null;
  note_number?: number;
};

export type NoteRow = {
  row_id: number;
  row_title: string;
  current_amount: number;
  previous_amount: number;
  variable_name: string;
  show_tag: boolean;
  accounts_included: string;
  account_details?: Array<{ account_id: string; account_text: string; balance: number; }>;
  block: string; // e.g., 'NOT1', 'NOT2', 'MASKIN', etc.
  always_show: boolean;
  toggle_show: boolean;
  style: string;
  variable_text?: string;
};

function fmtSEK(n: number | null | undefined) {
  if (n === null || n === undefined) return '';
  const v = Math.round(n);
  return new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(v);
}

function useVisibleRows<T extends { always_show?: boolean | null; current_amount?: any; previous_amount?: any }>(rows: T[] | undefined) {
  return useMemo(() => {
    if (!rows || !rows.length) return [] as T[];
    return rows.filter((r: any) => {
      // Respect always_show; otherwise require a non-zero current or previous amount
      if (r.always_show) return true;
      const ca = Number(r.current_amount || 0);
      const pa = Number(r.previous_amount || 0);
      return (ca !== 0 && !Number.isNaN(ca)) || (pa !== 0 && !Number.isNaN(pa));
    });
  }, [rows]);
}

export default function PrintAnnualReport({
  companyData,
  rrData,
  brData,
  noterData,
}: {
  companyData: any;
  rrData: RRRow[];
  brData: BRRow[];
  noterData: NoteRow[];
}) {
  const visibleRR = useVisibleRows<RRRow>(rrData);
  const visibleBR = useVisibleRows<BRRow>(brData);

  const assets = useMemo(() => visibleBR.filter(r => r.type === 'asset'), [visibleBR]);
  const equityLiab = useMemo(() => visibleBR.filter(r => r.type === 'equity' || r.type === 'liability'), [visibleBR]);

  const visibleNotes = useMemo(() => {
    if (!noterData || !noterData.length) return [] as NoteRow[];
    return noterData.filter(n => {
      // If explicitly hidden in UI, never include
      if (n.toggle_show === false) return false;
      if (n.always_show) return true;
      const ca = Number(n.current_amount || 0);
      const pa = Number(n.previous_amount || 0);
      return ca !== 0 || pa !== 0;
    });
  }, [noterData]);

  const header = companyData?.seFileData?.company_info || companyData?.seFileData?.annualReport?.header || {};
  const org = header.organization_number || companyData?.organizationNumber || companyData?.organization_number || '';
  const fiscalYear = header.fiscal_year || companyData?.fiscalYear || companyData?.fiscal_year;

  return (
    <div id="print-annual-report" className="print-only text-sm leading-tight">
      {/* Simple print stylesheet */}
      <style>{`
        @media screen { .print-only { display: none; } }
        @media print {
          #print-annual-report { width: 210mm; }
          .page-break { break-before: page; page-break-before: always; }
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          table { width: 100%; border-collapse: collapse; }
          th, td { padding: 4px 6px; vertical-align: top; }
          thead th { border-bottom: 1px solid #000; }
          tfoot td { border-top: 1px solid #000; font-weight: 600; }
        }
      `}</style>

      {/* 1) Förvaltningsberättelse */}
      <section>
        <h1 className="text-xl font-bold">Förvaltningsberättelse</h1>
        {/** Minimal subset mirroring the on-screen text fields (we assume these strings are already finalized in preview state) */}
        <h2 className="mt-3 font-semibold">Allmänt om verksamheten</h2>
        <p>{companyData?.forvaltningsberattelse?.allmant_om_verksamheten || companyData?.verksamhetsbeskrivning || ''}</p>

        <h2 className="mt-3 font-semibold">Väsentliga händelser under räkenskapsåret</h2>
        <p>{companyData?.forvaltningsberattelse?.vasentliga_handelser || companyData?.significantEvents || 'Inga väsentliga händelser under året.'}</p>

        {/* Flerårsöversikt (optional, if present in preview) */}
        {companyData?.flerarsoversikt && (
          <div className="mt-4">
            <h2 className="font-semibold">Flerårsöversikt (tkr)</h2>
            <table>
              <thead>
                <tr>
                  <th></th>
                  {companyData.flerarsoversikt.years?.map((y: any) => (
                    <th key={y} className="text-right">{y}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {companyData.flerarsoversikt.rows?.map((row: any, idx: number) => (
                  <tr key={idx}>
                    <td>{row.label}</td>
                    {row.values.map((v: number, j: number) => (
                      <td key={j} className="text-right">{fmtSEK(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 2) Resultaträkning */}
      <section className="page-break">
        <h1 className="text-xl font-bold">Resultaträkning</h1>
        <table>
          <thead>
            <tr>
              <th>Not</th>
              <th>Post</th>
              <th className="text-right">{fiscalYear || ''}</th>
              <th className="text-right">{(fiscalYear && Number(fiscalYear) - 1) || ''}</th>
            </tr>
          </thead>
          <tbody>
            {visibleRR.map((r, i) => (
              <tr key={i}>
                <td className="w-[6%]">{r.note_number || ''}</td>
                <td>{r.label}</td>
                <td className="text-right">{fmtSEK(r.current_amount)}</td>
                <td className="text-right">{fmtSEK(r.previous_amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* 3) Balansräkning (Tillgångar) */}
      <section className="page-break">
        <h1 className="text-xl font-bold">Balansräkning (Tillgångar)</h1>
        <table>
          <thead>
            <tr>
              <th>Not</th>
              <th>Post</th>
              <th className="text-right">{fiscalYear || ''}</th>
              <th className="text-right">{(fiscalYear && Number(fiscalYear) - 1) || ''}</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((r, i) => (
              <tr key={i}>
                <td className="w-[6%]">{r.note_number || ''}</td>
                <td>{r.label}</td>
                <td className="text-right">{fmtSEK(r.current_amount)}</td>
                <td className="text-right">{fmtSEK(r.previous_amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* 4) Balansräkning (Eget kapital och skulder) */}
      <section className="page-break">
        <h1 className="text-xl font-bold">Balansräkning (Eget kapital och skulder)</h1>
        <table>
          <thead>
            <tr>
              <th>Not</th>
              <th>Post</th>
              <th className="text-right">{fiscalYear || ''}</th>
              <th className="text-right">{(fiscalYear && Number(fiscalYear) - 1) || ''}</th>
            </tr>
          </thead>
          <tbody>
            {equityLiab.map((r, i) => (
              <tr key={i}>
                <td className="w-[6%]">{r.note_number || ''}</td>
                <td>{r.label}</td>
                <td className="text-right">{fmtSEK(r.current_amount)}</td>
                <td className="text-right">{fmtSEK(r.previous_amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* 5) Noter */}
      {visibleNotes.length > 0 && (
        <section className="page-break">
          <h1 className="text-xl font-bold">Noter</h1>

          {/* NOT1/NOT2 (principer & medelantal) first if present */}
          {['NOT1', 'NOT2'].map(key => (
            <NoteBlock key={key} blockKey={key} notes={visibleNotes} fiscalYear={fiscalYear} />
          ))}

          {/* Then all remaining blocks by their block name order */}
          {Array.from(new Set(visibleNotes
            .map(n => n.block)
            .filter(b => b !== 'NOT1' && b !== 'NOT2'))).map(blockKey => (
            <NoteBlock key={blockKey} blockKey={blockKey} notes={visibleNotes} fiscalYear={fiscalYear} />
          ))}
        </section>
      )}
    </div>
  );
}

function NoteBlock({ blockKey, notes, fiscalYear }: { blockKey: string; notes: NoteRow[]; fiscalYear?: number }) {
  const rows = notes.filter(n => n.block === blockKey);
  if (!rows.length) return null;
  return (
    <div className="mt-4">
      <h2 className="font-semibold">{labelForBlock(blockKey)}</h2>
      <table>
        <thead>
          <tr>
            <th>Post</th>
            <th className="text-right">{fiscalYear || ''}</th>
            <th className="text-right">{(fiscalYear && Number(fiscalYear) - 1) || ''}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.row_title}</td>
              <td className="text-right">{fmtSEK(r.current_amount)}</td>
              <td className="text-right">{fmtSEK(r.previous_amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function labelForBlock(block: string) {
  // Minimal mapping; can be expanded to friendly Swedish labels if needed
  const map: Record<string, string> = {
    NOT1: 'Redovisningsprinciper',
    NOT2: 'Medeltal anställda',
  };
  return map[block] || `Not – ${block}`;
}

// -----------------------------------------------------------------------------
// Client-side PDF generation using html2pdf (clone to avoid display:none)
// -----------------------------------------------------------------------------
export async function generatePdfFromPreview(companyData: any) {
  const src = document.getElementById('print-annual-report');
  if (!src) throw new Error('Kunde inte hitta förhandsgranskningen för utskrift.');

  const html2pdfMod: any = await import('html2pdf.js');
  const html2pdf = (html2pdfMod.default || (html2pdfMod as any));

  // Clone the hidden print tree and make it renderable off-screen
  const clone = src.cloneNode(true) as HTMLElement;
  clone.id = 'print-annual-report__tmp';
  clone.classList.remove('print-only');  // avoid display:none in @media screen
  Object.assign(clone.style, {
    position: 'fixed',
    left: '-10000px',
    top: '0',
    width: '210mm',       // A4 content width
    background: '#ffffff',
    // Do NOT set display:none or visibility:hidden, html2canvas won't render those
    zIndex: '0',
  });
  document.body.appendChild(clone);

  const filename =
    `arsredovisning_${companyData?.company_name
      || companyData?.seFileData?.company_info?.company_name
      || 'bolag'}_${companyData?.fiscal_year
      || companyData?.seFileData?.company_info?.fiscal_year
      || new Date().getFullYear()}.pdf`;

  const opt = {
    margin: [10, 12, 14, 12], // mm: top, right, bottom, left
    filename,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, letterRendering: true },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
    pagebreak: { mode: ['css', 'legacy'] }, // honors .page-break and overflows
  } as const;

  window.scrollTo({ top: 0 });
  await html2pdf().set(opt).from(clone).save();

  // Clean up
  clone.remove();
}
