'use client';

import Link from 'next/link';
import { useState } from 'react';
import Dialog from '@/components/Dialog';
import { Cancelled, usePortal } from '@/components/PortalShell';
import { ErrorBanner, NoticeBanner, StatusBadge, SuccessBanner, messageOf, useApi } from '@/components/ui';
import { apiFetch } from '@/lib/api';
import { formatDate, formatDateTime, formatEtb, initials, PAYOUT_LABELS } from '@/lib/format';
import type { Claim } from '@/lib/types';

export default function ClaimDetailClient({ id }: { id: string }) {
  const { runSensitive, refreshCounts } = usePortal();
  const { data: claim, error: loadError, setData } = useApi<Claim>(/^[0-9a-f]{32}$/.test(id) ? `claims/${id}` : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  if (!/^[0-9a-f]{32}$/.test(id)) return <NotFound />;
  if (loadError) return <NotFound message={loadError} />;
  if (!claim) return <p className='pt-space-lg font-body-sm text-body-sm text-on-surface-variant'>Loading claim…</p>;

  const assessment = claim.assessment;
  const act = async (call: () => Promise<Claim>, done: (c: Claim) => string) => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await runSensitive(call);
      setData(updated);
      setNotes(updated.notes ?? []);
      setSuccess(done(updated));
      refreshCounts();
      return true;
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, 'That did not work. Try again.'));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const approve = () =>
    act(
      () => apiFetch<Claim>(`claims/${claim.id}/approve`, { method: 'POST' }),
      (c) => `${c.code} is approved: ${formatEtb(c.approved_santim)} will be paid back to ${c.employee?.name ?? 'the employee'}.`
    );

  const reject = async () => {
    const ok = await act(
      () => apiFetch<Claim>(`claims/${claim.id}/reject`, { method: 'POST', body: { reason } }),
      (c) => `${c.code} is rejected.`
    );
    if (ok) setRejecting(false);
  };

  const payout = claim.employee?.payout_method ? PAYOUT_LABELS[claim.employee.payout_method] : 'No payout account yet';

  return (
    <div className='w-full max-w-5xl flex flex-col gap-space-md pb-space-2xl pt-space-lg'>
      <Link
        href='/claims'
        className='inline-flex items-center gap-1 font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors w-max'
      >
        <span aria-hidden="true" className='material-symbols-outlined text-[18px]'>arrow_back</span>
        Back to claims
      </Link>

      <header className='flex flex-col gap-1'>
        <div className='flex items-center gap-2 flex-wrap'>
          <h1 className='font-headline-lg text-headline-lg font-bold text-on-surface'>Claim #{claim.code}</h1>
          <StatusBadge status={claim.status} testId='claim-status' />
        </div>
        <p className='font-body-sm text-body-sm text-on-surface-variant'>
          Entered {formatDateTime(claim.created_at)} by HR
          {claim.reviewed_at ? ` · ${claim.status === 'rejected' ? 'rejected' : 'approved'} by ${claim.reviewer_name} on ${formatDateTime(claim.reviewed_at)}` : ''}
          {claim.batch ? ` · in ${claim.batch.code}${claim.batch.reference ? ` (ref ${claim.batch.reference})` : ''}` : ''}
        </p>
      </header>

      <SuccessBanner message={success} />
      {notes.map((note) => (
        <NoticeBanner key={note} testId='approval-note'>{note}</NoticeBanner>
      ))}
      <ErrorBanner message={error} />
      {claim.status === 'rejected' && claim.rejection_reason ? (
        <div className='rounded-xl bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container'>
          Reason given: <span data-testid='rejection-reason'>{claim.rejection_reason}</span>
        </div>
      ) : null}

      <section className='bg-surface-container-lowest rounded-xl border border-surface-container p-space-md flex flex-col gap-space-sm'>
        <div className='flex items-center gap-space-md'>
          <div className='w-12 h-12 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-[16px] shrink-0'>
            {initials(claim.employee?.name ?? '')}
          </div>
          <div className='flex flex-col min-w-0'>
            <span className='font-headline-sm text-headline-sm font-semibold text-on-surface truncate'>{claim.employee?.name}</span>
            <span className='font-body-sm text-body-sm text-on-surface-variant'>
              {claim.employee?.department} • ID: {claim.employee?.employee_number}
              {claim.employee && !claim.employee.active ? ' • not active' : ''}
            </span>
          </div>
          <span className='ml-auto px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm font-bold shrink-0'>
            {payout}
          </span>
        </div>

        <div className='grid grid-cols-1 sm:grid-cols-2 gap-space-sm pt-space-xs border-t border-surface-container'>
          <Detail label='Pharmacy' value={claim.pharmacy_name} sub={`TIN ${claim.pharmacy_tin}`} />
          <Detail label='Receipt' value={claim.receipt_number} sub={formatDate(claim.receipt_date)} />
          <Detail
            label='Medicine for'
            value={claim.dependant ? claim.dependant.name : claim.employee?.name ?? ''}
            sub={claim.dependant ? `Dependant (${claim.dependant.relationship})` : 'The employee'}
          />
          <Detail label='ENDOD ID' value={claim.employee?.endod_id ?? 'Not linked'} sub={claim.employee?.endod_id ? 'Endod health card' : undefined} />
        </div>
      </section>

      <section className='bg-surface-container-lowest rounded-xl border border-surface-container p-space-md flex flex-col gap-2'>
        <h2 className='font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold'>Medicines</h2>
        <table className='w-full text-left'>
          <thead>
            <tr className='font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant'>
              <th className='py-1'>Medicine</th>
              <th className='py-1 text-right'>Qty</th>
              <th className='py-1 text-right'>Unit price</th>
              <th className='py-1 text-right'>Line total</th>
            </tr>
          </thead>
          <tbody className='font-body-md text-body-md'>
            {claim.items?.map((item, index) => (
              <tr key={index} className='border-t border-surface-container'>
                <td className='py-1.5'>{item.medicine}</td>
                <td className='py-1.5 text-right'>{item.quantity}</td>
                <td className='py-1.5 text-right font-numeric-currency'>{formatEtb(item.unit_price_santim, false)}</td>
                <td className='py-1.5 text-right font-numeric-currency font-semibold'>{formatEtb(item.line_total_santim, false)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className='bg-surface-container-lowest rounded-xl border border-surface-container p-space-md flex flex-col gap-2'>
        <h2 className='font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold'>Financial Breakdown</h2>
        <Row label='Total Pharmacy Receipt' value={formatEtb(claim.total_santim)} bold />
        {claim.status === 'pending' && assessment ? (
          <>
            <Row label={`Employee Co-pay (${assessment.copay_percent}%)`} value={formatEtb(assessment.copay_santim)} muted />
            <Row label='Organisation Share' value={formatEtb(assessment.share_santim)} />
            <Row
              label={`Annual limit left (${formatDate(assessment.policy_year.start)} – ${formatDate(assessment.policy_year.end)})`}
              value={`${formatEtb(assessment.remaining_santim)} of ${formatEtb(assessment.annual_limit_santim)}`}
              muted
            />
            <div className='pt-2 mt-1 border-t border-surface-container flex justify-between items-center'>
              <span className='font-label-md text-label-md font-semibold text-on-surface'>
                Amount to Reimburse{assessment.capped ? ' (capped at the annual limit)' : ''}
              </span>
              <span data-testid='payable' className='font-numeric-currency text-numeric-currency font-bold text-primary'>
                {formatEtb(assessment.payable_santim)}
              </span>
            </div>
          </>
        ) : (
          <>
            {claim.copay_santim !== null && <Row label='Employee Co-pay' value={formatEtb(claim.copay_santim)} muted />}
            <div className='pt-2 mt-1 border-t border-surface-container flex justify-between items-center'>
              <span className='font-label-md text-label-md font-semibold text-on-surface'>
                {claim.status === 'rejected' ? 'Nothing is reimbursed' : claim.status === 'paid' ? 'Reimbursed' : 'Approved to reimburse'}
              </span>
              <span data-testid='payable' className='font-numeric-currency text-numeric-currency font-bold text-primary'>
                {formatEtb(claim.approved_santim ?? 0)}
              </span>
            </div>
          </>
        )}
      </section>

      {claim.status === 'pending' && assessment && assessment.problems.length > 0 ? (
        <section data-testid='problems' className='rounded-xl bg-error-container p-space-md flex flex-col gap-1 text-on-error-container'>
          <h2 className='font-label-md text-label-md uppercase tracking-wider font-semibold'>Cannot be approved</h2>
          {assessment.problems.map((p) => (
            <p key={p.code + p.message} className='font-body-sm text-body-sm'>
              {p.message}
            </p>
          ))}
        </section>
      ) : null}
      {claim.status === 'pending' && assessment?.capped && assessment.approvable ? (
        <NoticeBanner testId='cap-warning'>
          The organisation&apos;s share of {formatEtb(assessment.share_santim)} is more than is left of the annual limit; only{' '}
          {formatEtb(assessment.payable_santim)} will be reimbursed.
        </NoticeBanner>
      ) : null}

      <section className='bg-surface-container-lowest rounded-xl border border-surface-container p-space-md flex flex-col gap-space-sm'>
        <h2 className='font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold'>Attachments ({claim.has_receipt ? 1 : 0})</h2>
        {claim.receipt_file_id ? (
          <div className='flex items-center gap-2 p-2 rounded-lg bg-surface-container-low'>
            <span aria-hidden="true" className='material-symbols-outlined text-primary text-[20px]'>description</span>
            <div className='flex flex-col min-w-0 flex-1'>
              <span className='font-label-md text-label-md font-semibold text-on-surface truncate'>Pharmacy receipt</span>
              <span className='font-body-sm text-body-sm text-on-surface-variant truncate'>Entered with the claim</span>
            </div>
            <a
              href={`/api/receipts/${claim.receipt_file_id}`}
              target='_blank'
              rel='noopener noreferrer'
              className='font-label-sm text-label-sm text-primary hover:underline'
            >
              View
            </a>
            <a href={`/api/receipts/${claim.receipt_file_id}?download=1`} className='font-label-sm text-label-sm text-primary hover:underline'>
              Download
            </a>
          </div>
        ) : (
          <span className='font-body-sm text-body-sm text-on-surface-variant'>No receipt file.</span>
        )}
      </section>

      {claim.status === 'pending' ? (
        <div className='grid grid-cols-1 sm:grid-cols-2 gap-space-sm'>
          <button
            type='button'
            disabled={busy}
            onClick={() => {
              setReason('');
              setError(null);
              setRejecting(true);
            }}
            className='h-11 px-4 rounded-lg bg-surface-container-lowest hover:bg-error-container text-error font-label-lg text-label-lg font-semibold flex items-center justify-center gap-2 transition-colors border border-surface-container'
          >
            <span aria-hidden="true" className='material-symbols-outlined text-[18px]'>close</span>
            <span>Reject Claim</span>
          </button>
          <button
            type='button'
            onClick={() => void approve()}
            disabled={busy}
            className='h-11 px-4 rounded-lg bg-primary hover:bg-secondary text-on-primary font-label-lg text-label-lg font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-50'
          >
            <span aria-hidden="true" className='material-symbols-outlined text-[18px]'>check</span>
            <span>{busy ? 'Working…' : `Approve (${formatEtb(assessment?.payable_santim ?? 0)})`}</span>
          </button>
        </div>
      ) : null}

      {rejecting && (
        <Dialog
          testId='reject-dialog'
          title={`Reject ${claim.code}?`}
          description='The reason is kept with the claim; tell the employee what to fix if they can claim again.'
          confirmLabel='Reject'
          tone='danger'
          busy={busy}
          confirmDisabled={reason.trim().length < 3}
          error={error}
          onConfirm={() => void reject()}
          onCancel={() => setRejecting(false)}
        >
          <label className='flex flex-col gap-1'>
            <span className='font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold'>Reason (required)</span>
            <textarea
              className='w-full p-2.5 bg-surface-container-low rounded-lg font-body-sm text-body-sm text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary'
              placeholder='For example: the receipt has no pharmacy stamp.'
              rows={3}
              maxLength={1000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
        </Dialog>
      )}
    </div>
  );
}

function NotFound({ message }: { message?: string }) {
  return (
    <div className='pt-space-lg flex flex-col gap-space-sm'>
      <h1 className='font-headline-lg text-headline-lg font-bold text-on-surface'>Claim not found</h1>
      <p data-testid='not-found' className='font-body-md text-body-md text-on-surface-variant'>{message ?? 'Not found.'}</p>
      <Link href='/claims' className='font-label-md text-label-md text-primary hover:underline'>
        Back to claims
      </Link>
    </div>
  );
}

function Detail({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className='flex flex-col'>
      <span className='font-label-sm text-label-sm text-on-surface-variant'>{label}</span>
      <span className='font-body-md text-body-md font-semibold text-on-surface mt-0.5'>{value}</span>
      {sub && <span className='font-body-sm text-body-sm text-on-surface-variant'>{sub}</span>}
    </div>
  );
}

function Row({ label, value, bold, muted }: { label: string; value: string; bold?: boolean; muted?: boolean }) {
  return (
    <div className='flex justify-between items-center'>
      <span className={`font-body-sm text-body-sm ${muted ? 'text-on-surface-variant' : 'text-on-surface'}`}>{label}</span>
      <span className={`font-numeric-currency ${bold ? 'font-bold' : 'font-medium'} ${muted ? 'text-on-surface-variant' : 'text-on-surface'}`}>
        {value}
      </span>
    </div>
  );
}
