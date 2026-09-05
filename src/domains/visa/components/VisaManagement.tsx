/**
 * VisaManagement-simple.tsx
 * ─────────────────────────
 * Fully internationalised — zero hardcoded user-visible strings.
 * All text is sourced from the i18n translation files (ar / en).
 * Layout direction (RTL / LTR) is applied by the global <html dir>
 * set in src/i18n/index.ts; Tailwind logical properties (ms-*, me-*, ps-*, pe-*)
 * handle per-element flipping automatically.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
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
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/ui/table';
import { Textarea } from '@/shared/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import { Checkbox } from '@/shared/ui/checkbox';
import {
  Plus, FileText, Calendar, Loader2, Trash2, Clock, Search, X,
  MoreVertical, Edit, CheckSquare,
} from 'lucide-react';
import { useToast } from '@/shared/hooks/use-toast';
import { apiClient, VisaApplication, VisaApplicationCreate } from '@/shared/services/api';

// ── Status config ────────────────────────────────────────────────────────────

type VisaStatusKey =
  | 'status_docs'
  | 'status_review'
  | 'status_embassy'
  | 'status_consulate'
  | 'status_approved'
  | 'status_rejected'
  | 'status_cancelled';

const VISA_STATUS_KEYS: VisaStatusKey[] = [
  'status_docs',
  'status_review',
  'status_embassy',
  'status_consulate',
  'status_approved',
  'status_rejected',
  'status_cancelled',
];

const STATUS_COLORS: Record<number, { bg: string; ring: string }> = {
  1: { bg: 'bg-blue-500',   ring: 'ring-blue-400'   },
  2: { bg: 'bg-yellow-500', ring: 'ring-yellow-400' },
  3: { bg: 'bg-purple-500', ring: 'ring-purple-400' },
  4: { bg: 'bg-orange-500', ring: 'ring-orange-400' },
  5: { bg: 'bg-green-500',  ring: 'ring-green-400'  },
  6: { bg: 'bg-red-500',    ring: 'ring-red-400'    },
  7: { bg: 'bg-gray-500',   ring: 'ring-gray-400'   },
};

// ── Component ────────────────────────────────────────────────────────────────

export function VisaManagement() {
  const { t } = useTranslation();
  const { toast } = useToast();

  // ── Core data ─────────────────────────────────────────────────────────────
  const [applications, setApplications]     = useState<VisaApplication[]>([]);
  const [filtered, setFiltered]             = useState<VisaApplication[]>([]);
  const [loading, setLoading]               = useState(false);
  const [statusUpdatingId, setStatusUpdatingId] = useState<string | null>(null);
  const [statusSummary, setStatusSummary]   = useState<Record<number, number>>({});

  // ── Selection ─────────────────────────────────────────────────────────────
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedApp = applications.find((a) => a.id === selectedId) ?? null;

  // ── Dialog state ──────────────────────────────────────────────────────────
  const [addDialogOpen,         setAddDialogOpen]         = useState(false);
  const [appointmentDialogOpen, setAppointmentDialogOpen] = useState(false);
  const [apptTarget,            setApptTarget]            = useState<VisaApplication | null>(null);

  // ── Form state ────────────────────────────────────────────────────────────
  const emptyForm = (): Partial<VisaApplicationCreate> => ({
    client_name: '', passport_number: '', destination_country: '',
    email: '', phone: '', visa_type: '', application_notes: '', status: 1,
  });
  const [formData,    setFormData]    = useState<Partial<VisaApplicationCreate>>(emptyForm());
  const [submitting,  setSubmitting]  = useState(false);
  const [apptDate,    setApptDate]    = useState('');
  const [apptNotes,   setApptNotes]   = useState('');

  // ── Real-time search ──────────────────────────────────────────────────────
  const [search, setSearch] = useState({ client_name: '', passport_number: '' });
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const name     = search.client_name.toLowerCase().trim();
    const passport = search.passport_number.toLowerCase().trim();
    if (!name && !passport) { setFiltered(applications); return; }
    setFiltered(
      applications.filter((a) =>
        (!name     || a.client_name.toLowerCase().includes(name)) &&
        (!passport || a.passport_number.toLowerCase().includes(passport)),
      ),
    );
  }, [search, applications]);

  // ── Data loaders ──────────────────────────────────────────────────────────

  const loadApplications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.searchVisaApplications({ limit: 200 });
      setApplications(res.results ?? []);
    } catch (err) {
      toast({
        title: t('visa.toastError'),
        description: err instanceof Error ? err.message : t('visa.toastLoadError'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [toast, t]);

  const loadSummary = useCallback(async () => {
    try {
      const res = await apiClient.getVisaStatusSummary();
      setStatusSummary(res.status_counts ?? {});
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => { loadApplications(); loadSummary(); }, [loadApplications, loadSummary]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleCreateApplication = async () => {
    if (!formData.client_name?.trim() || !formData.passport_number?.trim() || !formData.destination_country?.trim()) {
      toast({ title: t('visa.toastValidation'), description: t('visa.toastRequiredFields'), variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      const created = await apiClient.createVisaApplication({
        client_name:         formData.client_name.trim(),
        passport_number:     formData.passport_number.trim(),
        destination_country: formData.destination_country.trim(),
        email:               formData.email?.trim()             || undefined,
        phone:               formData.phone?.trim()             || undefined,
        visa_type:           formData.visa_type?.trim()         || undefined,
        application_notes:   formData.application_notes?.trim() || undefined,
        status: 1,
      });
      toast({ title: t('visa.toastStatusUpdated'), description: t('visa.toastCreateSuccess', { name: created.client_name }) });
      setAddDialogOpen(false);
      setFormData(emptyForm());
      await loadApplications();
      await loadSummary();
      setSelectedId(created.id);
    } catch (err) {
      toast({ title: t('visa.toastError'), description: err instanceof Error ? err.message : t('visa.toastCreateError'), variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusClick = async (stepNum: number) => {
    if (!selectedApp) {
      toast({ title: t('visa.toastNoSelection'), description: t('visa.toastNoSelectionDesc'), variant: 'destructive' });
      return;
    }
    if (selectedApp.status === stepNum) return;
    setStatusUpdatingId(selectedApp.id);
    try {
      await apiClient.updateVisaStatus(selectedApp.id, stepNum);
      toast({
        title: t('visa.toastStatusUpdated'),
        description: t('visa.toastStatusMovedTo', { step: stepNum, label: t(`visa.${VISA_STATUS_KEYS[stepNum - 1]}`) }),
      });
      await loadApplications();
      await loadSummary();
    } catch (err) {
      toast({ title: t('visa.toastError'), description: err instanceof Error ? err.message : t('visa.toastStatusError'), variant: 'destructive' });
    } finally {
      setStatusUpdatingId(null);
    }
  };

  const openAppointmentDialog = (app: VisaApplication) => {
    setApptTarget(app);
    setApptDate(app.appointment_date ?? '');
    setApptNotes(app.appointment_notes ?? '');
    setAppointmentDialogOpen(true);
  };

  const handleScheduleAppointment = async () => {
    if (!apptTarget || !apptDate) {
      toast({ title: t('visa.toastValidation'), description: t('visa.toastSelectDate'), variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.updateVisaAppointment(apptTarget.id, apptDate, apptNotes || undefined);
      toast({ title: t('visa.toastStatusUpdated'), description: t('visa.toastApptSuccess', { date: apptDate }) });
      setAppointmentDialogOpen(false);
      setApptTarget(null); setApptDate(''); setApptNotes('');
      await loadApplications();
    } catch (err) {
      toast({ title: t('visa.toastError'), description: err instanceof Error ? err.message : t('visa.toastApptError'), variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteApplication = async (app: VisaApplication) => {
    if (!confirm(t('visa.confirmDelete', { name: app.client_name }))) return;
    setLoading(true);
    try {
      await apiClient.deleteVisaApplication(app.id);
      toast({ title: t('visa.toastDeletedTitle'), description: t('visa.toastDeletedDesc', { name: app.client_name }) });
      if (selectedId === app.id) setSelectedId(null);
      await loadApplications();
      await loadSummary();
    } catch (err) {
      toast({ title: t('visa.toastError'), description: err instanceof Error ? err.message : t('visa.toastDeleteError'), variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const handleSearchChange = (field: keyof typeof search, value: string) => {
    setSearch((prev) => ({ ...prev, [field]: value }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {}, 300);
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('visa.title')}
          </CardTitle>
          <CardDescription>{t('visa.desc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Button
              className="flex items-center gap-2"
              onClick={() => { setFormData(emptyForm()); setAddDialogOpen(true); }}
            >
              <Plus className="h-4 w-4" />
              {t('visa.newApp')}
            </Button>
            <Button
              variant="outline"
              className="flex items-center gap-2"
              disabled={!selectedApp}
              onClick={() => selectedApp && openAppointmentDialog(selectedApp)}
              title={!selectedApp ? t('visa.tooltipSelectFirst') : undefined}
            >
              <Calendar className="h-4 w-4" />
              {t('visa.scheduleAppt')}
              {selectedApp && (
                <span className="ms-1 text-xs text-muted-foreground">({selectedApp.client_name})</span>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── Status Overview ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>{t('visa.overview')}</CardTitle>
          <CardDescription>
            {selectedApp
              ? t('visa.overviewHintSelected', { name: selectedApp.client_name })
              : t('visa.overviewHintIdle')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {VISA_STATUS_KEYS.map((key, i) => {
              const stepNum  = i + 1;
              const count    = statusSummary[stepNum] ?? 0;
              const colors   = STATUS_COLORS[stepNum];
              const isActive = selectedApp?.status === stepNum;
              const isBusy   = statusUpdatingId === selectedApp?.id;
              const canClick = !!selectedApp && !isBusy;

              return (
                <div
                  key={key}
                  role="button"
                  aria-label={t('visa.tooltipSchedule')}
                  aria-pressed={isActive}
                  tabIndex={canClick ? 0 : -1}
                  className={[
                    'text-center rounded-lg p-2 transition-all select-none',
                    canClick ? 'cursor-pointer hover:bg-muted/60' : 'cursor-default opacity-60',
                    isActive ? `ring-2 ring-offset-2 ${colors.ring} bg-muted/40` : '',
                  ].join(' ')}
                  onClick={() => canClick && handleStatusClick(stepNum)}
                  onKeyDown={(e) => e.key === 'Enter' && canClick && handleStatusClick(stepNum)}
                >
                  <div className={`w-10 h-10 ${colors.bg} rounded-full mx-auto mb-2 flex items-center justify-center shadow-md relative`}>
                    {isBusy && isActive
                      ? <Loader2 className="h-4 w-4 animate-spin text-white" />
                      : <span className="text-white text-sm font-bold">{stepNum}</span>
                    }
                    {count > 0 && (
                      <span className="absolute -top-1 -end-1 bg-white border border-gray-200 text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
                        {count}
                      </span>
                    )}
                  </div>
                  <Badge
                    variant={isActive ? 'default' : 'secondary'}
                    className="text-xs whitespace-normal text-center leading-tight"
                  >
                    {t(`visa.${key}`)}
                  </Badge>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ── Real-Time Search ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            {t('visa.searchApps')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Client name */}
            <div className="space-y-2">
              <Label htmlFor="search-name">{t('visa.customerName')}</Label>
              <div className="relative">
                <Input
                  id="search-name"
                  placeholder={t('visa.searchHintName')}
                  value={search.client_name}
                  onChange={(e) => handleSearchChange('client_name', e.target.value)}
                  className="pe-8"
                />
                {search.client_name && (
                  <button
                    className="absolute end-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => handleSearchChange('client_name', '')}
                    aria-label={t('visa.deselect')}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
            {/* Passport */}
            <div className="space-y-2">
              <Label htmlFor="search-passport">{t('visa.passport')}</Label>
              <div className="relative">
                <Input
                  id="search-passport"
                  placeholder={t('visa.searchHintPassport')}
                  value={search.passport_number}
                  onChange={(e) => handleSearchChange('passport_number', e.target.value)}
                  className="pe-8"
                />
                {search.passport_number && (
                  <button
                    className="absolute end-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => handleSearchChange('passport_number', '')}
                    aria-label={t('visa.deselect')}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
          {(search.client_name || search.passport_number) && (
            <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
              <span>{t('visa.showingOf', { count: filtered.length, total: applications.length })}</span>
              <Button
                variant="ghost" size="sm"
                onClick={() => setSearch({ client_name: '', passport_number: '' })}
                className="h-auto py-0 px-2"
              >
                {t('visa.clearFilters')}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Applications Table ────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>
            {t('visa.appList')}
            <span className="ms-2 text-sm font-normal text-muted-foreground">({filtered.length})</span>
          </CardTitle>
          {selectedApp && (
            <CardDescription className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[selectedApp.status].bg}`} />
              {t('visa.selected')}: <strong>{selectedApp.client_name}</strong> — {selectedApp.passport_number}
              <button
                className="ms-1 text-muted-foreground hover:text-foreground"
                onClick={() => setSelectedId(null)}
                aria-label={t('visa.deselect')}
              >
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
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-40" />
              <p className="font-medium">{t('visa.noApps')}</p>
              <p className="text-sm mt-1">{t('visa.noAppsDesc')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('visa.customerName')}</TableHead>
                    <TableHead>{t('visa.passport')}</TableHead>
                    <TableHead>{t('visa.destination')}</TableHead>
                    <TableHead>{t('visa.colStatus')}</TableHead>
                    <TableHead>{t('visa.colAppointment')}</TableHead>
                    <TableHead className="text-end">{t('visa.colActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((app) => {
                    const colors     = STATUS_COLORS[app.status];
                    const isSelected = app.id === selectedId;
                    return (
                      <TableRow
                        key={app.id}
                        className={[
                          'cursor-pointer transition-colors',
                          isSelected ? 'bg-muted/60 font-medium' : 'hover:bg-muted/30',
                        ].join(' ')}
                        onClick={() => setSelectedId(isSelected ? null : app.id)}
                        aria-selected={isSelected}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {isSelected && <span className={`w-2 h-2 rounded-full flex-shrink-0 ${colors.bg}`} />}
                            <div>
                              <p className="font-medium">{app.client_name}</p>
                              {app.email && <p className="text-xs text-muted-foreground">{app.email}</p>}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{app.passport_number}</TableCell>
                        <TableCell>{app.destination_country}</TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Select
                            value={String(app.status)}
                            onValueChange={async (val) => {
                              const newStatus = parseInt(val);
                              if (newStatus === app.status) return;
                              
                              setStatusUpdatingId(app.id);
                              try {
                                await apiClient.updateVisaStatus(app.id, newStatus);
                                toast({ 
                                  title: t('visa.toastStatusUpdated'), 
                                  description: `${t('visa.toastStatusMovedTo', { step: newStatus, label: t(`visa.${VISA_STATUS_KEYS[newStatus - 1]}`) })}` 
                                });
                                await loadApplications();
                                await loadSummary();
                              } catch (err) {
                                toast({ 
                                  title: t('visa.toastError'), 
                                  description: err instanceof Error ? err.message : t('visa.toastStatusError'), 
                                  variant: 'destructive' 
                                });
                              } finally {
                                setStatusUpdatingId(null);
                              }
                            }}
                            disabled={statusUpdatingId === app.id}
                          >
                            <SelectTrigger className="w-[180px] h-8 border-0 shadow-none hover:bg-muted/50 transition-colors">
                              <SelectValue>
                                {statusUpdatingId === app.id ? (
                                  <div className="flex items-center gap-2">
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                    <span className="text-xs">{t('visa.updating')}...</span>
                                  </div>
                                ) : (
                                  <Badge className={`${colors.bg} text-white text-xs cursor-pointer hover:opacity-90`}>
                                    {app.status}. {app.status_name ?? t(`visa.${VISA_STATUS_KEYS[app.status - 1]}`)}
                                  </Badge>
                                )}
                              </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              {VISA_STATUS_KEYS.map((key, i) => {
                                const num = i + 1;
                                const statusColors = STATUS_COLORS[num];
                                return (
                                  <SelectItem key={key} value={String(num)}>
                                    <div className="flex items-center gap-2">
                                      <span className={`w-3 h-3 rounded-full ${statusColors.bg}`} />
                                      <span>{num}. {t(`visa.${key}`)}</span>
                                    </div>
                                  </SelectItem>
                                );
                              })}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          {app.appointment_date ? (
                            <div className="flex items-center gap-1 text-sm">
                              <Calendar className="h-3 w-3 text-muted-foreground" />
                              {app.appointment_date}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">{t('visa.noAppointment')}</span>
                          )}
                        </TableCell>
                        <TableCell className="text-end" onClick={(e) => e.stopPropagation()}>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-48">
                              <DropdownMenuItem onClick={() => openAppointmentDialog(app)}>
                                <Calendar className="me-2 h-4 w-4" />
                                {t('visa.scheduleAppt')}
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => setSelectedId(app.id)}>
                                <Edit className="me-2 h-4 w-4" />
                                {t('visa.viewDetails')}
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem 
                                onClick={() => handleDeleteApplication(app)}
                                className="text-red-600 focus:text-red-600"
                              >
                                <Trash2 className="me-2 h-4 w-4" />
                                {t('visa.tooltipDelete')}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
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

      {/* ── New Application Dialog ────────────────────────────────────────────── */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('visa.dlgNewTitle')}</DialogTitle>
            <DialogDescription>{t('visa.dlgNewDesc')}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="dlg-client-name">{t('visa.dlgLabelName')}</Label>
                <Input
                  id="dlg-client-name"
                  value={formData.client_name}
                  onChange={(e) => setFormData({ ...formData, client_name: e.target.value })}
                  placeholder={t('visa.dlgPlaceholderName')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dlg-passport">{t('visa.dlgLabelPassport')}</Label>
                <Input
                  id="dlg-passport"
                  value={formData.passport_number}
                  onChange={(e) => setFormData({ ...formData, passport_number: e.target.value })}
                  placeholder={t('visa.dlgPlaceholderPassport')}
                  className="font-mono"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="dlg-destination">{t('visa.dlgLabelDestination')}</Label>
              <Input
                id="dlg-destination"
                value={formData.destination_country}
                onChange={(e) => setFormData({ ...formData, destination_country: e.target.value })}
                placeholder={t('visa.dlgPlaceholderDestination')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="dlg-email">{t('visa.dlgLabelEmail')}</Label>
                <Input
                  id="dlg-email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder={t('visa.dlgPlaceholderEmail')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dlg-phone">{t('visa.dlgLabelPhone')}</Label>
                <Input
                  id="dlg-phone"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder={t('visa.dlgPlaceholderPhone')}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="dlg-visa-type">{t('visa.dlgLabelVisaType')}</Label>
              <Input
                id="dlg-visa-type"
                value={formData.visa_type}
                onChange={(e) => setFormData({ ...formData, visa_type: e.target.value })}
                placeholder={t('visa.dlgPlaceholderVisaType')}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="dlg-notes">{t('visa.dlgLabelNotes')}</Label>
              <Textarea
                id="dlg-notes"
                value={formData.application_notes}
                onChange={(e) => setFormData({ ...formData, application_notes: e.target.value })}
                placeholder={t('visa.dlgPlaceholderNotes')}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)} disabled={submitting}>
              {t('visa.dlgBtnCancel')}
            </Button>
            <Button onClick={handleCreateApplication} disabled={submitting}>
              {submitting && <Loader2 className="me-2 h-4 w-4 animate-spin" />}
              {t('visa.dlgBtnCreate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Appointment Dialog ────────────────────────────────────────────────── */}
      <Dialog open={appointmentDialogOpen} onOpenChange={setAppointmentDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('visa.dlgApptTitle')}</DialogTitle>
            <DialogDescription>
              {apptTarget && t('visa.dlgApptDesc', { name: apptTarget.client_name, passport: apptTarget.passport_number })}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="dlg-appt-date">{t('visa.dlgLabelApptDate')}</Label>
              <Input
                id="dlg-appt-date"
                type="date"
                value={apptDate}
                onChange={(e) => setApptDate(e.target.value)}
                min={new Date().toISOString().split('T')[0]}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dlg-appt-notes">{t('visa.dlgLabelApptNotes')}</Label>
              <Textarea
                id="dlg-appt-notes"
                value={apptNotes}
                onChange={(e) => setApptNotes(e.target.value)}
                placeholder={t('visa.dlgPlaceholderApptNotes')}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAppointmentDialogOpen(false)} disabled={submitting}>
              {t('visa.dlgBtnCancel')}
            </Button>
            <Button onClick={handleScheduleAppointment} disabled={submitting || !apptDate}>
              {submitting && <Loader2 className="me-2 h-4 w-4 animate-spin" />}
              {t('visa.dlgBtnSaveAppt')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
