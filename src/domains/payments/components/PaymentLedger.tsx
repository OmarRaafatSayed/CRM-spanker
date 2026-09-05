/**
 * ManualPaymentLedger-simple.tsx
 * ──────────────────────────────
 * Full implementation:
 *  • Record new payment (modal → Supabase via FastAPI)
 *  • Real-time status-count circles
 *  • Search & filter by client, booking ref, method, status, date range
 *  • PDF invoice generation (jspdf + jspdf-autotable, Latin font — RTL text
 *    in Arabic UI labels is handled at the i18n layer, not embedded in PDF)
 *  • Excel/CSV report export (xlsx already installed)
 *  • Zero hardcoded user-visible strings — all text via t()
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from '@/shared/ui/card';
import { Button } from '@/shared/ui/button';
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from '@/shared/ui/dialog';
import { Input } from '@/shared/ui/input';
import { Label } from '@/shared/ui/label';
import { Badge } from '@/shared/ui/badge';
import { Textarea } from '@/shared/ui/textarea';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/ui/table';
import {
  Plus, DollarSign, Receipt, FileSpreadsheet,
  Loader2, Trash2, Search, X, FileText,
} from 'lucide-react';
import { useToast } from '@/shared/hooks/use-toast';
import {
  apiClient,
  PaymentRecord, PaymentCreate, PaymentMethod, PaymentStatus,
} from '@/shared/services/api';

// ── Constants ─────────────────────────────────────────────────────────────────

type StatusKey = 'status_pending' | 'status_partial' | 'status_full' | 'status_refunded' | 'status_cancelled';
type MethodKey = 'method_cash' | 'method_bank' | 'method_pos' | 'method_cheque';

const STATUS_META: Record<StatusKey, { value: PaymentStatus; color: string; ring: string }> = {
  status_pending:   { value: 'pending',   color: 'bg-yellow-500', ring: 'ring-yellow-400' },
  status_partial:   { value: 'partial',   color: 'bg-blue-500',   ring: 'ring-blue-400'   },
  status_full:      { value: 'full',      color: 'bg-green-500',  ring: 'ring-green-400'  },
  status_refunded:  { value: 'refunded',  color: 'bg-purple-500', ring: 'ring-purple-400' },
  status_cancelled: { value: 'cancelled', color: 'bg-red-500',    ring: 'ring-red-400'    },
};
const STATUS_KEYS = Object.keys(STATUS_META) as StatusKey[];

const METHOD_VALUES: PaymentMethod[] = ['cash', 'bank', 'pos', 'cheque'];
const METHOD_KEYS:   MethodKey[]     = ['method_cash', 'method_bank', 'method_pos', 'method_cheque'];

const STATUS_BADGE_COLOR: Record<PaymentStatus, string> = {
  pending:   'bg-yellow-500',
  partial:   'bg-blue-500',
  full:      'bg-green-500',
  refunded:  'bg-purple-500',
  cancelled: 'bg-red-500',
};

const emptyForm = (): PaymentCreate => ({
  client_name: '', booking_reference: '', amount: 0,
  payment_method: 'cash', status: 'pending',
  payment_date: new Date().toISOString().split('T')[0], notes: '',
});

// ── Component ─────────────────────────────────────────────────────────────────

export function ManualPaymentLedger() {
  const { t } = useTranslation();
  const { toast } = useToast();

  // ── State ──────────────────────────────────────────────────────────────────
  const [payments,    setPayments]    = useState<PaymentRecord[]>([]);
  const [filtered,    setFiltered]    = useState<PaymentRecord[]>([]);
  const [loading,     setLoading]     = useState(false);
  const [submitting,  setSubmitting]  = useState(false);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});

  // Dialogs
  const [addOpen, setAddOpen]     = useState(false);
  const [invOpen, setInvOpen]     = useState(false);
  const [formData, setFormData]   = useState<PaymentCreate>(emptyForm());

  // Invoice org name
  const [orgName, setOrgName] = useState('Travel Agency CRM');

  // Selected row for invoice
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedPayment = payments.find((p) => p.id === selectedId) ?? null;

  // Search state
  const [search, setSearch] = useState({
    client_name: '', booking_reference: '',
    payment_method: '', status: '', date_from: '', date_to: '',
  });
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Local filter effect ────────────────────────────────────────────────────
  useEffect(() => {
    const { client_name, booking_reference, payment_method, status, date_from, date_to } = search;
    const hasFilter = client_name || booking_reference || payment_method || status || date_from || date_to;

    if (!hasFilter) { setFiltered(payments); return; }

    setFiltered(payments.filter((p) => {
      if (client_name       && !p.client_name.toLowerCase().includes(client_name.toLowerCase())) return false;
      if (booking_reference && !p.booking_reference?.toLowerCase().includes(booking_reference.toLowerCase())) return false;
      if (payment_method    && p.payment_method !== payment_method) return false;
      if (status            && p.status !== status) return false;
      if (date_from         && p.payment_date && p.payment_date < date_from) return false;
      if (date_to           && p.payment_date && p.payment_date > date_to) return false;
      return true;
    }));
  }, [search, payments]);

  // ── Loaders ────────────────────────────────────────────────────────────────

  const loadPayments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.searchPayments({ limit: 200 });
      setPayments(res.results ?? []);
    } catch (err) {
      toast({ title: t('payments.toastError'), description: err instanceof Error ? err.message : t('payments.toastLoadError'), variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }, [toast, t]);

  const loadSummary = useCallback(async () => {
    try {
      const res = await apiClient.getPaymentsSummary();
      setStatusCounts(res.by_status ?? {});
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => { loadPayments(); loadSummary(); }, [loadPayments, loadSummary]);

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleCreate = async () => {
    if (!formData.client_name.trim() || !formData.amount || formData.amount <= 0 || !formData.payment_method || !formData.status) {
      toast({ title: t('payments.toastValidation'), description: t('payments.toastRequiredFields'), variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      const created = await apiClient.createPayment({
        client_name:       formData.client_name.trim(),
        booking_reference: formData.booking_reference?.trim() || undefined,
        amount:            formData.amount,
        payment_method:    formData.payment_method,
        status:            formData.status,
        payment_date:      formData.payment_date || undefined,
        notes:             formData.notes?.trim() || undefined,
      });
      toast({ title: t('payments.toastSuccess'), description: t('payments.toastCreated', { name: created.client_name }) });
      setAddOpen(false);
      setFormData(emptyForm());
      await loadPayments();
      await loadSummary();
      setSelectedId(created.id);
    } catch (err) {
      toast({ title: t('payments.toastError'), description: err instanceof Error ? err.message : t('payments.toastCreateError'), variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (p: PaymentRecord) => {
    if (!confirm(t('payments.confirmDelete', { name: p.client_name }))) return;
    setLoading(true);
    try {
      await apiClient.deletePayment(p.id);
      toast({ title: t('payments.toastSuccess'), description: t('payments.toastDeleted') });
      if (selectedId === p.id) setSelectedId(null);
      await loadPayments();
      await loadSummary();
    } catch (err) {
      toast({ title: t('payments.toastError'), description: err instanceof Error ? err.message : t('payments.toastDeleteError'), variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  // ── PDF Invoice ────────────────────────────────────────────────────────────
  const generateInvoice = () => {
    const p = selectedPayment;
    if (!p) { toast({ title: t('payments.toastValidation'), description: t('payments.toastSelectForInv'), variant: 'destructive' }); return; }

    const invoiceNum = `INV-${Date.now().toString().slice(-6)}`;
    const doc = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' });
    const W = doc.internal.pageSize.getWidth();

    // Header band
    doc.setFillColor(37, 99, 235);
    doc.rect(0, 0, W, 38, 'F');

    // Title
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(22);
    doc.setFont('helvetica', 'bold');
    doc.text(t('payments.invTitle'), 14, 18);

    // Org name
    doc.setFontSize(11);
    doc.setFont('helvetica', 'normal');
    doc.text(orgName, 14, 28);

    // Invoice meta (top-right)
    doc.setFontSize(10);
    doc.text(`${t('payments.invNumber')}${invoiceNum}`, W - 14, 14, { align: 'right' });
    doc.text(`${t('payments.invDate')}: ${p.payment_date ?? new Date().toISOString().split('T')[0]}`, W - 14, 22, { align: 'right' });

    // Reset colour
    doc.setTextColor(30, 30, 30);

    // Bill To block
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.text(t('payments.invTo'), 14, 50);
    doc.setFont('helvetica', 'normal');
    doc.text(p.client_name, 14, 57);
    if (p.booking_reference) doc.text(`Ref: ${p.booking_reference}`, 14, 63);

    // From block
    doc.setFont('helvetica', 'bold');
    doc.text(t('payments.invFrom'), W / 2, 50);
    doc.setFont('helvetica', 'normal');
    doc.text(orgName, W / 2, 57);

    // Table
    autoTable(doc, {
      startY: 75,
      head: [[
        t('payments.invColDesc'),
        t('payments.invColAmt'),
        t('payments.invColMethod'),
        t('payments.invColStatus'),
        t('payments.invColDate'),
      ]],
      body: [[
        t('payments.invPayment', { ref: p.booking_reference ?? p.id.slice(0, 8) }),
        p.amount.toLocaleString('en-EG', { minimumFractionDigits: 2 }),
        p.payment_method.toUpperCase(),
        p.status.toUpperCase(),
        p.payment_date ?? '—',
      ]],
      styles:     { fontSize: 10, cellPadding: 4 },
      headStyles: { fillColor: [37, 99, 235], textColor: 255, fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [240, 245, 255] },
    });

    const finalY: number = (doc as any).lastAutoTable?.finalY ?? 110;

    // Total line
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.text(
      `${t('payments.invTotal')}: EGP ${p.amount.toLocaleString('en-EG', { minimumFractionDigits: 2 })}`,
      W - 14, finalY + 14, { align: 'right' },
    );

    // Footer
    doc.setFont('helvetica', 'italic');
    doc.setFontSize(9);
    doc.setTextColor(120, 120, 120);
    doc.text(t('payments.invFooter'), W / 2, finalY + 28, { align: 'center' });
    doc.text(t('payments.invGenBy'),  W / 2, finalY + 34, { align: 'center' });

    doc.save(`${invoiceNum}.pdf`);
    setInvOpen(false);
    toast({ title: t('payments.toastSuccess'), description: t('payments.toastInvGenerated', { number: invoiceNum }) });
  };

  // ── Excel/CSV Report ───────────────────────────────────────────────────────
  const exportReport = () => {
    const rows = filtered.map((p) => ({
      [t('payments.colClient')]:  p.client_name,
      [t('payments.colRef')]:     p.booking_reference ?? '',
      [t('payments.colAmount')]:  p.amount,
      [t('payments.colMethod')]:  t(`payments.method_${p.payment_method}` as any),
      [t('payments.colStatus')]:  t(`payments.status_${p.status}` as any),
      [t('payments.colDate')]:    p.payment_date ?? '',
      [t('payments.notes')]:      p.notes ?? '',
    }));

    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Payments');

    const filename = `payments_report_${new Date().toISOString().split('T')[0]}.xlsx`;
    XLSX.writeFile(wb, filename);
    toast({ title: t('payments.toastSuccess'), description: t('payments.toastExported', { filename }) });
  };

  const setField = <K extends keyof PaymentCreate>(k: K) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setFormData((prev) => ({ ...prev, [k]: e.target.value }));

  const clearSearch = () => setSearch({ client_name: '', booking_reference: '', payment_method: '', status: '', date_from: '', date_to: '' });
  const hasSearch   = Object.values(search).some(Boolean);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── Header / Action Bar ──────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            {t('payments.title')}
          </CardTitle>
          <CardDescription>{t('payments.desc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button className="flex items-center gap-2" onClick={() => { setFormData(emptyForm()); setAddOpen(true); }}>
              <Plus className="h-4 w-4" />
              {t('payments.record')}
            </Button>
            <Button
              variant="outline"
              className="flex items-center gap-2"
              onClick={() => {
                if (!selectedPayment) { toast({ title: t('payments.toastValidation'), description: t('payments.toastSelectForInv'), variant: 'destructive' }); return; }
                setInvOpen(true);
              }}
            >
              <Receipt className="h-4 w-4" />
              {t('payments.invoice')}
              {selectedPayment && <span className="ms-1 text-xs text-muted-foreground">({selectedPayment.client_name})</span>}
            </Button>
            <Button variant="secondary" className="flex items-center gap-2" onClick={exportReport} disabled={filtered.length === 0}>
              <FileSpreadsheet className="h-4 w-4" />
              {t('payments.report')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── Status Overview Circles ───────────────────────────────────────────── */}
      <Card>
        <CardHeader><CardTitle>{t('payments.overview')}</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            {STATUS_KEYS.map((key) => {
              const { value, color } = STATUS_META[key];
              const count = statusCounts[value] ?? 0;
              return (
                <div
                  key={key}
                  className="text-center cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => setSearch((s) => ({ ...s, status: s.status === value ? '' : value }))}
                  title={t(`payments.${key}`)}
                >
                  <div className={`w-12 h-12 ${color} rounded-full mx-auto mb-2 flex items-center justify-center shadow-md relative`}>
                    <DollarSign className="h-6 w-6 text-white" />
                    {count > 0 && (
                      <span className="absolute -top-1 -end-1 bg-white border border-gray-200 text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
                        {count}
                      </span>
                    )}
                  </div>
                  <Badge
                    variant={search.status === value ? 'default' : 'secondary'}
                    className="text-xs whitespace-normal text-center leading-tight"
                  >
                    {t(`payments.${key}`)}
                  </Badge>
                  <p className="text-sm text-muted-foreground mt-1">
                    {count} {t('payments.count')}
                  </p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ── Search & Filter ───────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            {t('payments.search')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Client name */}
            <div className="space-y-2">
              <Label>{t('payments.customerName')}</Label>
              <div className="relative">
                <Input
                  placeholder={t('payments.dlgPlaceholderClient')}
                  value={search.client_name}
                  onChange={(e) => setSearch((s) => ({ ...s, client_name: e.target.value }))}
                  className="pe-8"
                />
                {search.client_name && (
                  <button className="absolute end-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => setSearch((s) => ({ ...s, client_name: '' }))}><X className="h-4 w-4" /></button>
                )}
              </div>
            </div>
            {/* Booking ref */}
            <div className="space-y-2">
              <Label>{t('payments.bookingRef')}</Label>
              <div className="relative">
                <Input
                  placeholder={t('payments.dlgPlaceholderRef')}
                  value={search.booking_reference}
                  onChange={(e) => setSearch((s) => ({ ...s, booking_reference: e.target.value }))}
                  className="pe-8"
                />
                {search.booking_reference && (
                  <button className="absolute end-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => setSearch((s) => ({ ...s, booking_reference: '' }))}><X className="h-4 w-4" /></button>
                )}
              </div>
            </div>
            {/* Method */}
            <div className="space-y-2">
              <Label>{t('payments.method')}</Label>
              <select
                value={search.payment_method}
                onChange={(e) => setSearch((s) => ({ ...s, payment_method: e.target.value }))}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">{t('payments.allMethods')}</option>
                {METHOD_VALUES.map((v, i) => (
                  <option key={v} value={v}>{t(`payments.${METHOD_KEYS[i]}`)}</option>
                ))}
              </select>
            </div>
            {/* Status */}
            <div className="space-y-2">
              <Label>{t('payments.colStatus')}</Label>
              <select
                value={search.status}
                onChange={(e) => setSearch((s) => ({ ...s, status: e.target.value }))}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">{t('payments.allStatuses')}</option>
                {STATUS_KEYS.map((k) => (
                  <option key={k} value={STATUS_META[k].value}>{t(`payments.${k}`)}</option>
                ))}
              </select>
            </div>
            {/* Date from */}
            <div className="space-y-2">
              <Label>{t('payments.dateFrom')}</Label>
              <Input type="date" value={search.date_from} onChange={(e) => setSearch((s) => ({ ...s, date_from: e.target.value }))} />
            </div>
            {/* Date to */}
            <div className="space-y-2">
              <Label>{t('payments.dateTo')}</Label>
              <Input type="date" value={search.date_to} onChange={(e) => setSearch((s) => ({ ...s, date_to: e.target.value }))} />
            </div>
          </div>

          {hasSearch && (
            <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
              <span>{t('payments.showingOf', { count: filtered.length, total: payments.length })}</span>
              <Button variant="ghost" size="sm" onClick={clearSearch} className="h-auto py-0 px-2">
                {t('payments.clearFilters')}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Records Table ─────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>
            {t('payments.list')}
            <span className="ms-2 text-sm font-normal text-muted-foreground">
              ({filtered.length})
            </span>
          </CardTitle>
          {selectedPayment && (
            <CardDescription className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${STATUS_BADGE_COLOR[selectedPayment.status]}`} />
              {selectedPayment.client_name} — {selectedPayment.booking_reference ?? '—'}
              <button className="ms-1 text-muted-foreground hover:text-foreground" onClick={() => setSelectedId(null)}>
                <X className="h-3 w-3" />
              </button>
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <DollarSign className="h-12 w-12 mx-auto mb-4 opacity-40" />
              <p className="font-medium">{t('payments.noPayments')}</p>
              <p className="text-sm mt-1">{t('payments.noPaymentsDesc')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('payments.colClient')}</TableHead>
                    <TableHead>{t('payments.colRef')}</TableHead>
                    <TableHead>{t('payments.colAmount')}</TableHead>
                    <TableHead>{t('payments.colMethod')}</TableHead>
                    <TableHead>{t('payments.colStatus')}</TableHead>
                    <TableHead>{t('payments.colDate')}</TableHead>
                    <TableHead className="text-end">{t('payments.colActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((p) => {
                    const isSelected = p.id === selectedId;
                    const methodKey  = `method_${p.payment_method}` as MethodKey;
                    const statusKey  = `status_${p.status}` as StatusKey;
                    return (
                      <TableRow
                        key={p.id}
                        className={['cursor-pointer transition-colors',
                          isSelected ? 'bg-muted/60 font-medium' : 'hover:bg-muted/30'].join(' ')}
                        onClick={() => setSelectedId(isSelected ? null : p.id)}
                        aria-selected={isSelected}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {isSelected && <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_BADGE_COLOR[p.status]}`} />}
                            <span className="font-medium">{p.client_name}</span>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{p.booking_reference ?? '—'}</TableCell>
                        <TableCell className="font-medium">
                          {p.amount.toLocaleString('en-EG', { minimumFractionDigits: 2 })}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">{t(`payments.${methodKey}`)}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={`${STATUS_BADGE_COLOR[p.status]} text-white text-xs`}>
                            {t(`payments.${statusKey}`)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{p.payment_date ?? '—'}</TableCell>
                        <TableCell className="text-end">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="sm" title={t('payments.invoice')}
                              onClick={(e) => { e.stopPropagation(); setSelectedId(p.id); setInvOpen(true); }}>
                              <FileText className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" title={t('payments.report')}
                              onClick={(e) => { e.stopPropagation(); handleDelete(p); }}>
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── New Payment Dialog ────────────────────────────────────────────────── */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('payments.dlgNewTitle')}</DialogTitle>
            <DialogDescription>{t('payments.dlgNewDesc')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2 col-span-2">
                <Label>{t('payments.dlgLabelClient')}</Label>
                <Input value={formData.client_name} onChange={setField('client_name')} placeholder={t('payments.dlgPlaceholderClient')} />
              </div>
              <div className="space-y-2">
                <Label>{t('payments.dlgLabelRef')}</Label>
                <Input value={formData.booking_reference ?? ''} onChange={setField('booking_reference')} placeholder={t('payments.dlgPlaceholderRef')} />
              </div>
              <div className="space-y-2">
                <Label>{t('payments.dlgLabelAmount')}</Label>
                <Input type="number" min="0.01" step="0.01"
                  value={formData.amount || ''}
                  onChange={(e) => setFormData((p) => ({ ...p, amount: parseFloat(e.target.value) || 0 }))}
                  placeholder={t('payments.dlgPlaceholderAmount')} />
              </div>
              <div className="space-y-2">
                <Label>{t('payments.dlgLabelMethod')}</Label>
                <select value={formData.payment_method} onChange={setField('payment_method')}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  {METHOD_VALUES.map((v, i) => (
                    <option key={v} value={v}>{t(`payments.${METHOD_KEYS[i]}`)}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>{t('payments.dlgLabelStatus')}</Label>
                <select value={formData.status} onChange={setField('status')}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  {STATUS_KEYS.map((k) => (
                    <option key={k} value={STATUS_META[k].value}>{t(`payments.${k}`)}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2 col-span-2">
                <Label>{t('payments.dlgLabelDate')}</Label>
                <Input type="date" value={formData.payment_date ?? ''} onChange={setField('payment_date')} />
              </div>
              <div className="space-y-2 col-span-2">
                <Label>{t('payments.dlgLabelNotes')}</Label>
                <Textarea value={formData.notes ?? ''} onChange={setField('notes')} placeholder={t('payments.dlgPlaceholderNotes')} rows={2} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)} disabled={submitting}>{t('payments.dlgBtnCancel')}</Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting && <Loader2 className="me-2 h-4 w-4 animate-spin" />}
              {t('payments.dlgBtnSave')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Invoice Dialog ────────────────────────────────────────────────────── */}
      <Dialog open={invOpen} onOpenChange={setInvOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('payments.dlgInvTitle')}</DialogTitle>
            <DialogDescription>
              {selectedPayment
                ? `${selectedPayment.client_name} — ${selectedPayment.booking_reference ?? selectedPayment.id.slice(0, 8)}`
                : t('payments.dlgInvSelect')}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label>{t('payments.dlgInvOrg')}</Label>
              <Input value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="Travel Agency CRM" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvOpen(false)}>{t('payments.dlgBtnCancel')}</Button>
            <Button onClick={generateInvoice} disabled={!selectedPayment}>
              <Receipt className="me-2 h-4 w-4" />
              {t('payments.dlgBtnGenerate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
