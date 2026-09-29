'use client';

import React, { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, ShieldAlert, ShieldCheck, FileText, ExternalLink, Cpu } from 'lucide-react';
import { DocumentItem } from '@/types';
import { fetchDocumentBlob } from '@/lib/api';

interface DocumentReviewProps {
  doc: DocumentItem;
  remarks: string;
  onRemarksChange: (value: string) => void;
  onVerify: (status: 'Verified' | 'Mismatch') => void;
}

const flagStyle = {
  CLEAN: { label: 'Clean', badge: 'bg-emerald-100 text-emerald-800', box: 'border-emerald-200 bg-emerald-50', Icon: ShieldCheck },
  SUSPICIOUS: { label: 'Suspicious', badge: 'bg-amber-100 text-amber-800', box: 'border-amber-200 bg-amber-50', Icon: ShieldAlert },
  HIGH_RISK: { label: 'High risk', badge: 'bg-red-100 text-red-800', box: 'border-red-200 bg-red-50', Icon: ShieldAlert },
} as const;

export const DocumentReview: React.FC<DocumentReviewProps> = ({ doc, remarks, onRemarksChange, onVerify }) => {
  const [url, setUrl] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(false);

  const isImage = (doc.mime_type || '').startsWith('image/');
  const isPdf = doc.mime_type === 'application/pdf' || /\.pdf$/i.test(doc.file_name);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setUrl(null);
    setLoadError(null);
    fetchDocumentBlob(doc.id)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch((err) => !cancelled && setLoadError(err.message || 'Could not load the file'));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [doc.id]);

  const flag = doc.fraud_flag ? flagStyle[doc.fraud_flag] : null;
  const pct = doc.fraud_score != null ? Math.round(doc.fraud_score * 100) : null;

  return (
    <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1] space-y-3">
      <div className="flex flex-col sm:flex-row gap-4">
        {/* The uploaded file itself */}
        <div className="sm:w-56 shrink-0">
          <div className="h-40 rounded-lg border border-[#E5E9E1] bg-white overflow-hidden flex items-center justify-center">
            {url && isImage ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={url} alt={doc.file_name} className="max-h-full max-w-full object-contain cursor-zoom-in" onClick={() => setZoom(true)} />
            ) : url && isPdf ? (
              <iframe src={url} title={doc.file_name} className="w-full h-full" />
            ) : url ? (
              <div className="text-center text-xs text-[#5e6d65] px-2">
                <FileText className="w-8 h-8 mx-auto mb-1 text-[#8eb494]" />
                No inline preview for this file type
              </div>
            ) : loadError ? (
              <div className="text-center text-xs text-red-700 px-2">{loadError}</div>
            ) : (
              <div className="w-6 h-6 border-2 border-[#0C3B2E] border-t-transparent rounded-full animate-spin" />
            )}
          </div>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-[#0C3B2E] hover:underline"
            >
              <ExternalLink className="w-3 h-3" /> Open full size
            </a>
          )}
        </div>

        {/* Details and ML result */}
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center flex-wrap gap-2">
            <span className="font-bold text-xs text-[#0C3B2E]">{doc.document_type}</span>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                doc.status === 'Verified'
                  ? 'bg-emerald-100 text-emerald-800'
                  : doc.status === 'Mismatch'
                  ? 'bg-red-100 text-red-800'
                  : 'bg-amber-100 text-amber-800'
              }`}
            >
              {doc.status}
            </span>
          </div>
          <p className="text-xs text-[#5e6d65] font-mono break-all">
            {doc.file_name} • {(doc.file_size / 1024).toFixed(0)} KB
          </p>
          <p className="text-[10px] text-[#5e6d65] font-mono break-all">SHA-256: {doc.file_hash}</p>
          {doc.remarks && <p className="text-xs text-[#0C3B2E] font-medium">Remark: {doc.remarks}</p>}

          <div className={`rounded-lg border p-3 ${flag ? flag.box : 'border-[#E5E9E1] bg-white'}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-[#0C3B2E]">
                <Cpu className="w-3.5 h-3.5" /> Fraud detection model
              </div>
              {flag ? (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${flag.badge}`}>
                  {flag.label}
                  {pct != null ? ` • ${pct}%` : ''}
                </span>
              ) : (
                <span className="text-[10px] text-[#5e6d65]">Not analysed (uploaded before analysis was enabled)</span>
              )}
            </div>
            {doc.fraud_findings && doc.fraud_findings.length > 0 && (
              <ul className="mt-2 space-y-1">
                {doc.fraud_findings.map((f, i) => (
                  <li key={i} className="text-[11px] text-[#3b5346] flex gap-1.5">
                    <span>•</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[10px] text-[#5e6d65]">Advisory only. The officer makes the final decision.</p>
          </div>
        </div>
      </div>

      {/* Verification actions */}
      <div className="pt-3 border-t border-[#E5E9E1] flex flex-col sm:flex-row items-center justify-between gap-3">
        <input
          type="text"
          placeholder="Add underwriter remarks..."
          value={remarks}
          onChange={(e) => onRemarksChange(e.target.value)}
          className="w-full sm:w-auto flex-1 text-xs px-3 py-1.5 rounded-lg border border-[#E5E9E1] bg-white outline-none"
        />
        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={() => onVerify('Verified')}
            className="px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-700 text-white hover:bg-emerald-800 transition-all flex items-center space-x-1"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Verify</span>
          </button>
          <button
            onClick={() => onVerify('Mismatch')}
            className="px-3 py-1.5 text-xs font-bold rounded-lg bg-red-700 text-white hover:bg-red-800 transition-all flex items-center space-x-1"
          >
            <XCircle className="w-3.5 h-3.5" />
            <span>Reject</span>
          </button>
        </div>
      </div>

      {zoom && url && isImage && (
        <div
          className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-6 cursor-zoom-out"
          onClick={() => setZoom(false)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt={doc.file_name} className="max-h-full max-w-full object-contain" />
        </div>
      )}
    </div>
  );
};
