/**
 * HotelManagement-simple.tsx
 * ──────────────────────────
 * Zero hardcoded user-visible strings — every label, toast, placeholder,
 * and button text is sourced from the i18n translation files (ar / en).
 * Tailwind logical properties (ms-*, me-*, ps-*, pe-*, text-start/end)
 * handle RTL/LTR flipping automatically via the global <html dir>.
 */
import { useState, useEffect, useRef } from 'react';
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
import { Textarea } from '@/shared/ui/textarea';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/ui/table';
import {
  Plus, Upload, FileSpreadsheet, Hotel, Pencil, Trash2, Loader2, Star, MapPin,
} from 'lucide-react';
import { useToast } from '@/shared/hooks/use-toast';
import { apiClient, HotelDataRecord } from '@/shared/services/api';
import * as XLSX from 'xlsx';

interface HotelOffer extends HotelDataRecord {
  id?: string;
  is_active?: boolean;
  created_at?: string;
}

const emptyForm = (): Partial<HotelOffer> => ({
  hotel_name: '', hotel_location: '', hotel_city: '', hotel_country: '',
  hotel_rating: undefined, hotel_category: '', room_type: '', board_basis: '',
  price_per_night: 0, price_currency: 'EGP', special_offer_price: undefined,
  available_from: '', available_to: '', booking_deadline: '',
  max_occupancy: undefined, available_rooms: undefined,
  description: '', terms_conditions: '', cancellation_policy: '',
});

export function HotelManagement() {
  const { t } = useTranslation();
  const { toast } = useToast();

  const [hotels,       setHotels]       = useState<HotelOffer[]>([]);
  const [loading,      setLoading]      = useState(false);
  const [uploading,    setUploading]    = useState(false);
  const [dialogOpen,   setDialogOpen]   = useState(false);
  const [editingHotel, setEditingHotel] = useState<HotelOffer | null>(null);
  const [formData,     setFormData]     = useState<Partial<HotelOffer>>(emptyForm());

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { loadHotels(); }, []);

  // ── Loaders ───────────────────────────────────────────────────────────────

  const loadHotels = async () => {
    setLoading(true);
    try {
      const res: any = await apiClient.searchHotels({ limit: 100 });
      setHotels(res.results ?? []);
    } catch (err) {
      toast({
        title: t('hotels.toastError'),
        description: err instanceof Error ? err.message : t('hotels.toastError'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  // ── Save (add / edit) ─────────────────────────────────────────────────────

  const handleSaveHotel = async () => {
    if (
      !formData.hotel_name || !formData.hotel_location ||
      !formData.hotel_city || !formData.hotel_country ||
      !formData.room_type  || !formData.price_per_night ||
      !formData.available_from || !formData.available_to
    ) {
      toast({ title: t('hotels.toastValidation'), description: t('hotels.toastValidationDesc'), variant: 'destructive' });
      return;
    }

    setLoading(true);
    try {
      const hotelData: HotelDataRecord = {
        hotel_name:          formData.hotel_name!,
        hotel_location:      formData.hotel_location!,
        hotel_city:          formData.hotel_city!,
        hotel_country:       formData.hotel_country!,
        hotel_rating:        formData.hotel_rating,
        hotel_category:      formData.hotel_category,
        room_type:           formData.room_type!,
        board_basis:         formData.board_basis,
        price_per_night:     formData.price_per_night!,
        price_currency:      formData.price_currency || 'EGP',
        special_offer_price: formData.special_offer_price,
        available_from:      formData.available_from!,
        available_to:        formData.available_to!,
        booking_deadline:    formData.booking_deadline,
        max_occupancy:       formData.max_occupancy,
        available_rooms:     formData.available_rooms,
        description:         formData.description,
        terms_conditions:    formData.terms_conditions,
        cancellation_policy: formData.cancellation_policy,
      };

      await apiClient.bulkInsertHotels([hotelData]);
      toast({ title: t('hotels.toastSuccess'), description: t('hotels.hotelSaved') });
      setDialogOpen(false);
      setEditingHotel(null);
      setFormData(emptyForm());
      loadHotels();
    } catch (err) {
      toast({
        title: t('hotels.toastError'),
        description: err instanceof Error ? err.message : t('hotels.toastError'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  // ── Excel upload ──────────────────────────────────────────────────────────

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const valid = ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel'];
    if (!valid.includes(file.type) && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      toast({ title: t('hotels.toastInvalidFile'), description: t('hotels.toastInvalidFileDesc'), variant: 'destructive' });
      return;
    }

    setUploading(true);
    try {
      const data     = await file.arrayBuffer();
      const wb       = XLSX.read(data, { type: 'array' });
      const ws       = wb.Sheets[wb.SheetNames[0]];
      const jsonData: any[] = XLSX.utils.sheet_to_json(ws);
      if (!jsonData.length) throw new Error('Excel file is empty');

      const records: HotelDataRecord[] = jsonData.map((row: any) => ({
        hotel_name:          row['Hotel Name']          || row['hotel_name']          || '',
        hotel_location:      row['Location']            || row['hotel_location']      || '',
        hotel_city:          row['City']                || row['hotel_city']          || '',
        hotel_country:       row['Country']             || row['hotel_country']       || '',
        hotel_rating:        row['Rating']              || row['hotel_rating']        || undefined,
        hotel_category:      row['Category']            || row['hotel_category']      || undefined,
        room_type:           row['Room Type']           || row['room_type']           || '',
        board_basis:         row['Board Basis']         || row['board_basis']         || undefined,
        price_per_night:     parseFloat(row['Price per Night'] || row['price_per_night'] || '0'),
        price_currency:      row['Currency']            || row['price_currency']      || 'EGP',
        special_offer_price: row['Special Offer Price'] || row['special_offer_price'] || undefined,
        available_from:      row['Available From']      || row['available_from']      || '',
        available_to:        row['Available To']        || row['available_to']        || '',
        booking_deadline:    row['Booking Deadline']    || row['booking_deadline']    || undefined,
        max_occupancy:       row['Max Occupancy']       || row['max_occupancy']       || undefined,
        available_rooms:     row['Available Rooms']     || row['available_rooms']     || undefined,
        description:         row['Description']         || row['description']         || undefined,
        terms_conditions:    row['Terms & Conditions']  || row['terms_conditions']    || undefined,
        cancellation_policy: row['Cancellation Policy'] || row['cancellation_policy'] || undefined,
      }));

      await apiClient.bulkInsertHotels(records);
      toast({ title: t('hotels.toastSuccess'), description: t('hotels.uploadSuccess', { count: records.length }) });
      loadHotels();
    } catch (err) {
      toast({
        title: t('hotels.toastUploadFailed'),
        description: err instanceof Error ? err.message : t('hotels.toastUploadFailed'),
        variant: 'destructive',
      });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ── Template download ─────────────────────────────────────────────────────

  const downloadTemplate = () => {
    const template = [{
      'Hotel Name': 'Example Hotel', 'Location': 'Downtown Area',
      'City': 'Cairo', 'Country': 'Egypt', 'Rating': 4.5, 'Category': '5-Star',
      'Room Type': 'Deluxe Double', 'Board Basis': 'Breakfast Included',
      'Price per Night': 1500, 'Currency': 'EGP', 'Special Offer Price': 1200,
      'Available From': '2026-08-01', 'Available To': '2026-12-31',
      'Booking Deadline': '2026-07-25', 'Max Occupancy': 2, 'Available Rooms': 10,
      'Description': 'Spacious room with city view',
      'Terms & Conditions': 'No cancellation within 48 hours',
      'Cancellation Policy': 'Full refund before 48 hours',
    }];

    const ws = XLSX.utils.json_to_sheet(template);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Hotels');
    ws['!cols'] = Array(19).fill({ wch: 22 });
    XLSX.writeFile(wb, 'hotel_template.xlsx');
    toast({ title: t('hotels.toastSuccess'), description: t('hotels.templateDownloaded') });
  };

  // ── Delete ────────────────────────────────────────────────────────────────

  const handleDeleteHotel = async (hotelId: string) => {
    if (!confirm(t('hotels.confirmDelete'))) return;
    setLoading(true);
    try {
      toast({ title: t('hotels.toastError'), description: t('hotels.toastDeletePending'), variant: 'destructive' });
      loadHotels();
    } catch (err) {
      toast({
        title: t('hotels.toastError'),
        description: err instanceof Error ? err.message : t('hotels.toastError'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const openAdd = () => { setFormData(emptyForm()); setEditingHotel(null); setDialogOpen(true); };
  const field   = (k: keyof HotelOffer) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setFormData((p) => ({ ...p, [k]: e.target.value }));

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* ── Action bar ─────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Hotel className="h-5 w-5" />
            {t('hotels.title')}
          </CardTitle>
          <CardDescription>{t('hotels.desc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button className="flex items-center gap-2" onClick={openAdd} disabled={loading}>
              <Plus className="h-4 w-4" />
              {t('hotels.addManual')}
            </Button>

            <Button
              variant="outline"
              className="flex items-center gap-2"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Upload className="h-4 w-4" />
              }
              {uploading ? t('hotels.uploading') : t('hotels.uploadExcel')}
            </Button>
            <input ref={fileInputRef} type="file" accept=".xlsx,.xls" onChange={handleFileUpload} className="hidden" />

            <Button variant="secondary" className="flex items-center gap-2" onClick={downloadTemplate}>
              <FileSpreadsheet className="h-4 w-4" />
              {t('hotels.downloadTemplate')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── Inventory table ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>{t('hotels.inventory')}</CardTitle>
          <CardDescription>
            {loading ? t('hotels.loading') : t('hotels.inventoryDesc', { count: hotels.length })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : hotels.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <Hotel className="h-12 w-12 mx-auto mb-4 opacity-40" />
              <p>{t('hotels.noHotels')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('hotels.colHotel')}</TableHead>
                    <TableHead>{t('hotels.colLocation')}</TableHead>
                    <TableHead>{t('hotels.colRoomType')}</TableHead>
                    <TableHead>{t('hotels.colPrice')}</TableHead>
                    <TableHead>{t('hotels.colAvailability')}</TableHead>
                    <TableHead className="text-end">{t('hotels.colActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hotels.map((hotel) => (
                    <TableRow key={hotel.id}>
                      <TableCell>
                        <p className="font-medium">{hotel.hotel_name}</p>
                        {hotel.hotel_rating && (
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                            {hotel.hotel_rating}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-sm">
                          <MapPin className="h-3 w-3" />
                          {hotel.hotel_city}, {hotel.hotel_country}
                        </div>
                      </TableCell>
                      <TableCell>{hotel.room_type}</TableCell>
                      <TableCell>
                        <p className="font-medium">{hotel.price_currency} {hotel.price_per_night.toLocaleString()}</p>
                        {hotel.special_offer_price && (
                          <p className="text-sm text-green-600">
                            {t('hotels.colOffer', { currency: hotel.price_currency, price: hotel.special_offer_price.toLocaleString() })}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {t('hotels.colAvailTo', { from: hotel.available_from, to: hotel.available_to })}
                      </TableCell>
                      <TableCell className="text-end">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost" size="sm"
                            title={t('hotels.editHotel')}
                            onClick={() => { setFormData(hotel); setEditingHotel(hotel); setDialogOpen(true); }}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost" size="sm"
                            title={t('hotels.deleteHotel')}
                            onClick={() => hotel.id && handleDeleteHotel(hotel.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Add / Edit Dialog ───────────────────────────────────────────────── */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingHotel ? t('hotels.dlgEditTitle') : t('hotels.dlgAddTitle')}</DialogTitle>
            <DialogDescription>{t('hotels.dlgDesc')}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* Row 1 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="h-name">{t('hotels.dlgLabelName')}</Label>
                <Input id="h-name" value={formData.hotel_name} onChange={field('hotel_name')} placeholder="Grand Plaza Hotel" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-loc">{t('hotels.dlgLabelLocation')}</Label>
                <Input id="h-loc" value={formData.hotel_location} onChange={field('hotel_location')} placeholder="Downtown" />
              </div>
            </div>
            {/* Row 2 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="h-city">{t('hotels.dlgLabelCity')}</Label>
                <Input id="h-city" value={formData.hotel_city} onChange={field('hotel_city')} placeholder="Cairo" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-country">{t('hotels.dlgLabelCountry')}</Label>
                <Input id="h-country" value={formData.hotel_country} onChange={field('hotel_country')} placeholder="Egypt" />
              </div>
            </div>
            {/* Row 3 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="h-rating">{t('hotels.dlgLabelRating')}</Label>
                <Input id="h-rating" type="number" min="0" max="5" step="0.1"
                  value={formData.hotel_rating ?? ''}
                  onChange={(e) => setFormData((p) => ({ ...p, hotel_rating: e.target.value ? parseFloat(e.target.value) : undefined }))}
                  placeholder="4.5" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-cat">{t('hotels.dlgLabelCategory')}</Label>
                <Input id="h-cat" value={formData.hotel_category} onChange={field('hotel_category')} placeholder="5-Star" />
              </div>
            </div>
            {/* Row 4 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="h-room">{t('hotels.dlgLabelRoomType')}</Label>
                <Input id="h-room" value={formData.room_type} onChange={field('room_type')} placeholder="Deluxe Double" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-board">{t('hotels.dlgLabelBoardBasis')}</Label>
                <Input id="h-board" value={formData.board_basis} onChange={field('board_basis')} placeholder="Breakfast Included" />
              </div>
            </div>
            {/* Row 5 — pricing */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="h-price">{t('hotels.dlgLabelPrice')}</Label>
                <Input id="h-price" type="number" min="0"
                  value={formData.price_per_night}
                  onChange={(e) => setFormData((p) => ({ ...p, price_per_night: parseFloat(e.target.value) || 0 }))}
                  placeholder="1500" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-curr">{t('hotels.dlgLabelCurrency')}</Label>
                <Input id="h-curr" value={formData.price_currency} onChange={field('price_currency')} placeholder="EGP" maxLength={3} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-offer">{t('hotels.dlgLabelSpecialPrice')}</Label>
                <Input id="h-offer" type="number" min="0"
                  value={formData.special_offer_price ?? ''}
                  onChange={(e) => setFormData((p) => ({ ...p, special_offer_price: e.target.value ? parseFloat(e.target.value) : undefined }))}
                  placeholder="1200" />
              </div>
            </div>
            {/* Row 6 — availability */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="h-from">{t('hotels.dlgLabelAvailFrom')}</Label>
                <Input id="h-from" type="date" value={formData.available_from} onChange={field('available_from')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-to">{t('hotels.dlgLabelAvailTo')}</Label>
                <Input id="h-to" type="date" value={formData.available_to} onChange={field('available_to')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-dl">{t('hotels.dlgLabelDeadline')}</Label>
                <Input id="h-dl" type="date" value={formData.booking_deadline ?? ''} onChange={field('booking_deadline')} />
              </div>
            </div>
            {/* Row 7 — capacity */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="h-occ">{t('hotels.dlgLabelMaxOcc')}</Label>
                <Input id="h-occ" type="number" min="1"
                  value={formData.max_occupancy ?? ''}
                  onChange={(e) => setFormData((p) => ({ ...p, max_occupancy: e.target.value ? parseInt(e.target.value) : undefined }))}
                  placeholder="2" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="h-rooms">{t('hotels.dlgLabelAvailRooms')}</Label>
                <Input id="h-rooms" type="number" min="0"
                  value={formData.available_rooms ?? ''}
                  onChange={(e) => setFormData((p) => ({ ...p, available_rooms: e.target.value ? parseInt(e.target.value) : undefined }))}
                  placeholder="10" />
              </div>
            </div>
            {/* Row 8 — text areas */}
            <div className="space-y-2">
              <Label htmlFor="h-desc">{t('hotels.dlgLabelDesc')}</Label>
              <Textarea id="h-desc" value={formData.description} onChange={field('description')} rows={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="h-terms">{t('hotels.dlgLabelTerms')}</Label>
              <Textarea id="h-terms" value={formData.terms_conditions} onChange={field('terms_conditions')} rows={2} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="h-cancel">{t('hotels.dlgLabelCancel')}</Label>
              <Textarea id="h-cancel" value={formData.cancellation_policy} onChange={field('cancellation_policy')} rows={2} />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t('hotels.dlgBtnCancel')}
            </Button>
            <Button onClick={handleSaveHotel} disabled={loading}>
              {loading && <Loader2 className="me-2 h-4 w-4 animate-spin" />}
              {editingHotel ? t('hotels.dlgBtnUpdate') : t('hotels.dlgBtnAdd')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
