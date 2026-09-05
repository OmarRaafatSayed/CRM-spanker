/**
 * Flight Search Component – i18n ready (EN / AR)
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { Label } from '@/shared/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select';
import { Alert, AlertDescription } from '@/shared/ui/alert';
import { Badge } from '@/shared/ui/badge';
import { Loader2, Plane, Search, Clock, DollarSign, AlertCircle, CheckCircle, Globe } from 'lucide-react';
import { apiClient, FlightSearchParams, FlightSearchResponse } from '@/shared/services/api';
import { useToast } from '@/shared/hooks/use-toast';

interface FlightSearchFormData {
  origin: string;
  destination: string;
  departureDate: string;
  returnDate: string;
  passengerCount: number;
  travelClass: 'economy' | 'premium_economy' | 'business' | 'first';
}

export function FlightSearch() {
  const { t } = useTranslation();
  const { toast } = useToast();

  const LOADING_MESSAGES = [
    { icon: Globe,       text: t('flights.loading1'), duration: 3000 },
    { icon: Plane,       text: t('flights.loading2'), duration: 3000 },
    { icon: Search,      text: t('flights.loading3'), duration: 4000 },
    { icon: Clock,       text: t('flights.loading4'), duration: 4000 },
    { icon: DollarSign,  text: t('flights.loading5'), duration: 4000 },
    { icon: CheckCircle, text: t('flights.loading6'), duration: 3000 },
  ];

  const [formData, setFormData] = useState<FlightSearchFormData>({
    origin: 'CAI',
    destination: 'DXB',
    departureDate: '',
    returnDate: '',
    passengerCount: 1,
    travelClass: 'economy',
  });

  const [isSearching,          setIsSearching]          = useState(false);
  const [currentLoadingMessage,setCurrentLoadingMessage] = useState(0);
  const [searchResults,        setSearchResults]         = useState<FlightSearchResponse | null>(null);
  const [error,                setError]                 = useState<string | null>(null);

  React.useEffect(() => {
    if (!isSearching) return;
    const msg   = LOADING_MESSAGES[currentLoadingMessage];
    const timer = setTimeout(() => {
      if (currentLoadingMessage < LOADING_MESSAGES.length - 1)
        setCurrentLoadingMessage(c => c + 1);
    }, msg.duration);
    return () => clearTimeout(timer);
  }, [isSearching, currentLoadingMessage]);

  const handleInputChange = (field: keyof FlightSearchFormData, value: string | number) =>
    setFormData(prev => ({ ...prev, [field]: value }));

  const handleSearch = async () => {
    if (!formData.origin || !formData.destination) {
      toast({ title: t('flights.validationTitle'), description: t('flights.validationRoute'), variant: 'destructive' });
      return;
    }
    if (!formData.departureDate) {
      toast({ title: t('flights.validationTitle'), description: t('flights.validationDate'), variant: 'destructive' });
      return;
    }
    setIsSearching(true); setCurrentLoadingMessage(0); setError(null); setSearchResults(null);

    try {
      const params: FlightSearchParams = {
        origin:           formData.origin.toUpperCase(),
        destination:      formData.destination.toUpperCase(),
        departure_date:   formData.departureDate,
        return_date:      formData.returnDate || undefined,
        passenger_count:  formData.passengerCount,
        travel_class:     formData.travelClass,
      };
      const results = await apiClient.searchFlights(params);
      console.log('[FlightSearch] API response:', results);
      setSearchResults(results);

      if (results.success && results.flights.length > 0) {
        toast({
          title: t('flights.searchComplete'),
          description: `${t('flights.found')} ${results.total_results} ${results.cached ? t('flights.fromCache') : ''}`,
        });
      } else if (!results.success) {
        // Surface the real error — never silently show empty results
        const detail =
          results.error ?? t('flights.scraperDown');
        setError(detail);
        toast({
          title: t('flights.searchFailed'),
          description: detail,
          variant: 'destructive',
        });
      }
    } catch (err: any) {
      const msg = err.message || t('flights.searchFailed');
      setError(msg);
      toast({ title: t('flights.searchFailed'), description: msg, variant: 'destructive' });
    } finally {
      setIsSearching(false); setCurrentLoadingMessage(0);
    }
  };

  const formatPrice = (price?: number, currency?: string) => {
    if (!price) return t('flights.priceNA');
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD' }).format(price);
  };

  const formatTime = (timeString: string) => {
    try {
      if (timeString.includes('T')) {
        return new Date(timeString).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
      }
      return timeString;
    } catch { return timeString; }
  };

  const CurrentIcon = isSearching ? LOADING_MESSAGES[currentLoadingMessage].icon : Loader2;

  return (
    <div className="space-y-6">
      {/* Search Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plane className="h-5 w-5" />
            {t('flights.title')}
          </CardTitle>
          <CardDescription>{t('flights.desc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

            {/* Origin */}
            <div className="space-y-2">
              <Label htmlFor="origin">{t('flights.from')}</Label>
              <Input id="origin" placeholder="CAI" value={formData.origin}
                onChange={e => handleInputChange('origin', e.target.value.toUpperCase())}
                maxLength={3} disabled={isSearching} className="uppercase" />
              <p className="text-xs text-muted-foreground">{t('flights.iataHint')}</p>
            </div>

            {/* Destination */}
            <div className="space-y-2">
              <Label htmlFor="destination">{t('flights.to')}</Label>
              <Input id="destination" placeholder="DXB" value={formData.destination}
                onChange={e => handleInputChange('destination', e.target.value.toUpperCase())}
                maxLength={3} disabled={isSearching} className="uppercase" />
              <p className="text-xs text-muted-foreground">{t('flights.iataHint2')}</p>
            </div>

            {/* Departure Date */}
            <div className="space-y-2">
              <Label htmlFor="departureDate">{t('flights.departure')}</Label>
              <Input id="departureDate" type="date" value={formData.departureDate}
                onChange={e => handleInputChange('departureDate', e.target.value)}
                disabled={isSearching} min={new Date().toISOString().split('T')[0]} />
            </div>

            {/* Return Date */}
            <div className="space-y-2">
              <Label htmlFor="returnDate">{t('flights.return')}</Label>
              <Input id="returnDate" type="date" value={formData.returnDate}
                onChange={e => handleInputChange('returnDate', e.target.value)}
                disabled={isSearching}
                min={formData.departureDate || new Date().toISOString().split('T')[0]} />
            </div>

            {/* Passengers */}
            <div className="space-y-2">
              <Label>{t('flights.passengers')}</Label>
              <Select value={formData.passengerCount.toString()}
                onValueChange={v => handleInputChange('passengerCount', parseInt(v))}
                disabled={isSearching}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[1,2,3,4,5,6,7,8,9].map(n => (
                    <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Travel Class */}
            <div className="space-y-2">
              <Label>{t('flights.class')}</Label>
              <Select value={formData.travelClass}
                onValueChange={(v: any) => handleInputChange('travelClass', v)}
                disabled={isSearching}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="economy">{t('flights.economy')}</SelectItem>
                  <SelectItem value="premium_economy">{t('flights.premiumEconomy')}</SelectItem>
                  <SelectItem value="business">{t('flights.business')}</SelectItem>
                  <SelectItem value="first">{t('flights.first')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Search Button */}
          <div className="mt-6">
            <Button onClick={handleSearch} disabled={isSearching} size="lg" className="w-full md:w-auto">
              {isSearching ? (
                <><CurrentIcon className="me-2 h-4 w-4 animate-spin" />{LOADING_MESSAGES[currentLoadingMessage].text}</>
              ) : (
                <><Search className="me-2 h-4 w-4" />{t('flights.search')}</>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Loading */}
      {isSearching && (
        <Alert>
          <CurrentIcon className="h-4 w-4 animate-spin" />
          <AlertDescription>
            <div className="flex items-center justify-between">
              <span>{LOADING_MESSAGES[currentLoadingMessage].text}</span>
              <span className="text-xs text-muted-foreground">{t('flights.seconds')}</span>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Error */}
      {error && !isSearching && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Service Unavailable — real error from the scraper */}
      {searchResults && !isSearching && !searchResults.success && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <p className="font-medium">{t('flights.scraperDown')}</p>
            <p className="text-sm mt-1 opacity-80">{t('flights.scraperDownHint')}</p>
            {searchResults.error && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs opacity-70 hover:opacity-100">
                  Technical details
                </summary>
                <pre className="mt-1 text-xs whitespace-pre-wrap opacity-70">
                  {searchResults.error}
                </pre>
              </details>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Results — only shown when the scraper actually succeeded */}
      {searchResults && !isSearching && searchResults.success && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle>{t('flights.results')}</CardTitle>
                <CardDescription>
                  {searchResults.origin} → {searchResults.destination} · {searchResults.departure_date}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                {searchResults.cached && (
                  <Badge variant="secondary"><Clock className="h-3 w-3 me-1" />{t('flights.cached')}</Badge>
                )}
                <Badge variant="outline">{searchResults.total_results} {t('flights.found')}</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {searchResults.flights.length > 0 ? (
              <div className="space-y-4">
                {searchResults.flights.map((flight, idx) => (
                  <Card key={flight.flight_id || idx} className="overflow-hidden">
                    <CardContent className="p-0">
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 p-4">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">{t('flights.airline')}</p>
                          <p className="font-semibold">{flight.airline}</p>
                          {flight.flight_number && <p className="text-sm text-muted-foreground">{flight.flight_number}</p>}
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">{t('flights.dep')}</p>
                          <p className="font-semibold">{formatTime(flight.departure_time)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">{t('flights.arr')}</p>
                          <p className="font-semibold">{formatTime(flight.arrival_time)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">{t('flights.duration')}</p>
                          <p className="font-semibold">{flight.duration}</p>
                          <p className="text-sm text-muted-foreground">
                            {typeof flight.stops === 'number'
                              ? flight.stops === 0 ? t('flights.nonstop')
                              : `${flight.stops} ${flight.stops > 1 ? t('flights.stops') : t('flights.stop')}`
                              : flight.stops}
                          </p>
                        </div>
                        <div className="flex flex-col justify-center items-end col-span-2 md:col-span-1">
                          {flight.price ? (
                            <>
                              <p className="text-2xl font-bold text-primary">{formatPrice(flight.price, flight.price_currency)}</p>
                              <p className="text-xs text-muted-foreground">{t('flights.perPerson')}</p>
                            </>
                          ) : (
                            <p className="text-sm text-muted-foreground">{t('flights.priceNA')}</p>
                          )}
                        </div>
                      </div>
                      {flight.raw_text && flight.raw_text !== 'No data' && (
                        <div className="bg-muted p-3 text-xs text-muted-foreground border-t">
                          <details>
                            <summary className="cursor-pointer hover:text-foreground">{t('flights.viewRaw')}</summary>
                            <pre className="mt-2 whitespace-pre-wrap">{flight.raw_text}</pre>
                          </details>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <Plane className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>{t('flights.noFlights')}</p>
                <p className="text-sm mt-2">{t('flights.tryAgain')}</p>
              </div>
            )}
            <div className="mt-6 pt-6 border-t flex items-center justify-between text-sm text-muted-foreground flex-wrap gap-2">
              <span>{t('flights.poweredBy')}: <strong>{searchResults.provider}</strong></span>
              <span>{new Date(searchResults.timestamp).toLocaleString()}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
