'use client';

import Link from 'next/link';
import { useState } from 'react';

export default function ClaimDetailClient({ id }: { id: string }) {
  const [approveState, setApproveState] = useState<'idle' | 'processing' | 'done'>('idle');
  const [rejectState, setRejectState] = useState<'idle' | 'done'>('idle');

  const handleApprove = () => {
    setApproveState('processing');
    setTimeout(() => setApproveState('done'), 1200);
  };

  const handleReject = () => {
    const reason = window.prompt(
      'Please specify rejection reason to notify the employee:',
      'Missing official rubber stamp from pharmacy'
    );
    if (reason) setRejectState('done');
  };

  return (
    <div className='w-full max-w-5xl flex flex-col gap-space-md pb-space-2xl'>
      <Link
        href='/claims'
        className='inline-flex items-center gap-1 font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors w-max'
      >
        <span className='material-symbols-outlined text-[18px]'>arrow_back</span>
        Back to claims
      </Link>

      <header className='flex flex-col gap-1'>
        <div className='flex items-center gap-2 flex-wrap'>
          <h1 className='font-headline-lg text-headline-lg font-bold text-on-surface'>
            Claim #{id}
          </h1>
          <span className='inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 font-label-sm text-label-sm font-semibold'>
            <span className='w-1.5 h-1.5 rounded-full bg-amber-600' />
            Pending
          </span>
        </div>
        <p className='font-body-sm text-body-sm text-on-surface-variant'>
          Submitted 2 hours ago via TenaCare Mobile
        </p>
      </header>

      <section className='bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-space-md flex flex-col gap-space-sm'>
        <div className='flex items-center gap-space-md'>
          <img
            className='w-12 h-12 rounded-full object-cover shrink-0'
            alt='Dawit Bekele'
            src='https://lh3.googleusercontent.com/aida-public/AB6AXuBG8pNlN6KtNs8wj_i5gR6M88E3nglCrFzDC6LIg_xVqWBL1TYjm0Gc024IYEL8b3gCntms0fdZzNRKRFBBgsRdCm44TIovM4WZAfejE0H_3h0ZV0O2ocubb0VuRRU-ihJsW9YLHBOGCRH9KZGsvDhDvnegzkL2g-s19QPLTZniAwdelopLE3s8mhLzLkFXQUkIY6RyT-rqhPV4xx8Lapwo0LfU2v4lFn4Www6Nf6dzWmy5C7D1ttbf'
          />
          <div className='flex flex-col min-w-0'>
            <span className='font-headline-sm text-headline-sm font-semibold text-on-surface truncate'>
              Dawit Bekele
            </span>
            <span className='font-body-sm text-body-sm text-on-surface-variant'>
              Senior Backend Dev • ID: ET-0492
            </span>
          </div>
          <span className='ml-auto px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm font-bold shrink-0'>
            Unlimited Plan
          </span>
        </div>

        <div className='grid grid-cols-1 sm:grid-cols-2 gap-space-sm pt-space-xs border-t border-surface-container'>
          <Detail label='Pharmacy' value='Kenema Pharmacy #4' sub='Bole Medhanialem • TIN 0048192831' />
          <Detail label='Medication' value='Insulin Glargine + Test Strips' sub='Chronic / Diabetes' />
          <Detail label='Prescriber' value='Dr. Tewodros Kassahun' sub='Hayat Hospital' />
          <Detail label='DEDAN ID' value='DE-00492' sub='Verified' />
        </div>
      </section>

      <section className='bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-space-md flex flex-col gap-2'>
        <h2 className='font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold'>
          Financial Breakdown
        </h2>
        <Row label='Total Pharmacy Invoice' value='ETB 5,200.00' bold />
        <Row label='Employee Co-pay (0%)' value='ETB 0.00' muted />
        <Row label='Insurer Share (SHI)' value='ETB 1,040.00' />
        <Row label='Organisation Share' value='ETB 4,160.00' bold accent />
        <div className='pt-2 mt-1 border-t border-surface-container flex justify-between items-center'>
          <span className='font-label-md text-label-md font-semibold text-on-surface'>Amount to Disburse</span>
          <span className='font-numeric-currency text-numeric-currency font-bold text-primary'>ETB 5,200.00</span>
        </div>
      </section>

      <section className='bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-space-md flex flex-col gap-space-sm'>
        <div className='flex items-center justify-between'>
          <h2 className='font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold'>
            Attachments (2)
          </h2>
          <button className='font-label-sm text-label-sm text-primary hover:underline'>
            View high-res
          </button>
        </div>
        <div className='grid grid-cols-1 sm:grid-cols-2 gap-space-sm'>
          <Attachment name='Rx-Hayat-892.pdf' meta='Prescription • 1.4 MB' />
          <Attachment name='Kenema-Inv-4819.jpg' meta='Stamped Invoice • TIN Verified' />
        </div>
      </section>

      <section className='bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-space-md flex flex-col gap-2'>
        <label className='font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold'>
          Audit Note (optional)
        </label>
        <textarea
          className='w-full p-2.5 bg-surface-container-low rounded-lg font-body-sm text-body-sm text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary'
          placeholder='Provide context if requesting clarification or issuing a denial...'
          rows={2}
        />
      </section>

      <div className='grid grid-cols-1 sm:grid-cols-2 gap-space-sm'>
        <button
          id='rejectBtn'
          type='button'
          onClick={handleReject}
          className={
            rejectState === 'done'
              ? 'h-11 px-4 rounded-lg bg-error text-on-error font-label-lg text-label-lg font-semibold shadow-sm flex items-center justify-center gap-2 pointer-events-none'
              : 'h-11 px-4 rounded-lg bg-surface-container-lowest hover:bg-error-container text-error font-label-lg text-label-lg font-semibold shadow-sm flex items-center justify-center gap-2 transition-colors'
          }
        >
          <span className='material-symbols-outlined text-[18px]'>
            {rejectState === 'done' ? 'done' : 'close'}
          </span>
          <span>{rejectState === 'done' ? 'Marked as Rejected' : 'Reject Claim'}</span>
        </button>
        <button
          id='approveBtn'
          type='button'
          onClick={handleApprove}
          disabled={approveState !== 'idle'}
          className={
            approveState === 'done'
              ? 'h-11 px-4 rounded-lg bg-tertiary text-on-primary font-label-lg text-label-lg font-bold shadow-md flex items-center justify-center gap-2'
              : 'h-11 px-4 rounded-lg bg-primary hover:bg-secondary text-on-primary font-label-lg text-label-lg font-bold shadow-md flex items-center justify-center gap-2 transition-colors'
          }
        >
          {approveState === 'processing' ? (
            <>
              <span className='material-symbols-outlined text-[18px] animate-spin'>refresh</span>
              <span>Processing...</span>
            </>
          ) : approveState === 'done' ? (
            <>
              <span className='material-symbols-outlined text-[18px]'>verified</span>
              <span>Disbursed to Telebirr</span>
            </>
          ) : (
            <>
              <span className='material-symbols-outlined text-[18px]'>check</span>
              <span>Approve (ETB 5,200.00)</span>
            </>
          )}
        </button>
      </div>
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

function Row({
  label,
  value,
  bold,
  muted,
  accent,
}: {
  label: string;
  value: string;
  bold?: boolean;
  muted?: boolean;
  accent?: boolean;
}) {
  return (
    <div className='flex justify-between items-center'>
      <span className={`font-body-sm text-body-sm ${muted ? 'text-on-surface-variant' : 'text-on-surface'}`}>
        {label}
      </span>
      <span
        className={`font-numeric-currency ${bold ? 'font-bold' : 'font-medium'} ${
          accent ? 'text-primary' : 'text-on-surface'
        } ${muted ? 'text-on-surface-variant' : ''}`}
      >
        {value}
      </span>
    </div>
  );
}

function Attachment({ name, meta }: { name: string; meta: string }) {
  return (
    <div className='flex items-center gap-2 p-2 rounded-lg bg-surface-container-low hover:bg-surface-container transition-colors cursor-pointer'>
      <span className='material-symbols-outlined text-primary text-[20px]'>description</span>
      <div className='flex flex-col min-w-0'>
        <span className='font-label-md text-label-md font-semibold text-on-surface truncate'>{name}</span>
        <span className='font-body-sm text-body-sm text-on-surface-variant truncate'>{meta}</span>
      </div>
    </div>
  );
}
