/**
 * CRMCustomers.tsx
 * =================
 * CRM Customers Dashboard — Display all registered users/customers
 * with their status, visa applications, quotations, and bookings.
 */
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import {
  Users,
  MailIcon,
  PhoneIcon,
  MapPinIcon,
  ChevronRight,
  Loader2,
  AlertCircle,
  Download,
  Search,
} from 'lucide-react'
import { supabase } from '@/shared/services/supabase'

interface Customer {
  id: string
  auth_user_id: string
  email: string
  full_name: string
  phone?: string
  country?: string
  status: 'LEAD' | 'ACTIVE_CLIENT' | 'INACTIVE' | 'ARCHIVED'
  created_at: string
  updated_at: string
}

export function CRMCustomers() {
  const { t } = useTranslation()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

  // Fetch customers on mount
  useEffect(() => {
    const fetchCustomers = async () => {
      try {
        setLoading(true)
        setError(null)

        const { data: sessionData } = await supabase.auth.getSession()
        const session = sessionData.session
        if (!session?.access_token) {
          setError('Not authenticated')
          return
        }

        // Build query params
        const params = new URLSearchParams()
        if (statusFilter) {
          params.append('status_filter', statusFilter)
        }

        const res = await fetch(`${API_BASE}/crm/customers?${params.toString()}`, {
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        })

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`)
        }

        const data = await res.json()
        setCustomers(data.customers || [])
      } catch (err) {
        console.error('Failed to fetch customers:', err)
        setError(err instanceof Error ? err.message : 'Failed to load customers')
      } finally {
        setLoading(false)
      }
    }

    fetchCustomers()
  }, [statusFilter])

  // Filter customers by search query
  const filteredCustomers = customers.filter(c => {
    const q = searchQuery.toLowerCase()
    return (
      c.email.toLowerCase().includes(q) ||
      (c.full_name && c.full_name.toLowerCase().includes(q)) ||
      (c.phone && c.phone.includes(q))
    )
  })

  // Status badge color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'LEAD': return 'bg-yellow-100 text-yellow-800'
      case 'ACTIVE_CLIENT': return 'bg-green-100 text-green-800'
      case 'INACTIVE': return 'bg-gray-100 text-gray-800'
      case 'ARCHIVED': return 'bg-red-100 text-red-800'
      default: return 'bg-blue-100 text-blue-800'
    }
  }

  // Export to CSV
  const handleExport = () => {
    const csv = [
      ['Email', 'Full Name', 'Phone', 'Country', 'Status', 'Created At'],
      ...filteredCustomers.map(c => [
        c.email,
        c.full_name || '',
        c.phone || '',
        c.country || '',
        c.status,
        new Date(c.created_at).toLocaleString(),
      ]),
    ]
      .map(row => row.map(cell => `"${cell}"`).join(','))
      .join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `customers-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="h-6 w-6 text-blue-600" />
            {t('crm.customers') || 'Customers'}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {filteredCustomers.length} customer{filteredCustomers.length !== 1 ? 's' : ''} found
          </p>
        </div>
        <Button
          onClick={handleExport}
          variant="outline"
          size="sm"
          className="gap-2"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-3 flex-wrap">
        <div className="flex-1 min-w-[250px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search by email, name, or phone..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        <select
          value={statusFilter || ''}
          onChange={(e) => setStatusFilter(e.target.value || null)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="LEAD">Lead</option>
          <option value="ACTIVE_CLIENT">Active Client</option>
          <option value="INACTIVE">Inactive</option>
          <option value="ARCHIVED">Archived</option>
        </select>
      </div>

      {/* Error state */}
      {error && (
        <Card className="bg-red-50 border-red-200">
          <CardContent className="flex items-center gap-3 pt-6">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <div>
              <p className="font-medium text-red-900">{t('error.loadFailed') || 'Error'}</p>
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {loading && !error && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          <span className="ml-2 text-gray-600">Loading customers...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && filteredCustomers.length === 0 && (
        <Card className="bg-gray-50 border-gray-200">
          <CardContent className="text-center py-12">
            <Users className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-600 font-medium">{t('crm.noCustomers') || 'No customers found'}</p>
            <p className="text-sm text-gray-500 mt-1">Try adjusting your search filters</p>
          </CardContent>
        </Card>
      )}

      {/* Customers list */}
      {!loading && !error && filteredCustomers.length > 0 && (
        <div className="grid gap-3">
          {filteredCustomers.map(customer => (
            <Card key={customer.id} className="hover:shadow-md transition-shadow cursor-pointer">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between gap-4">
                  {/* Left: Customer info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 truncate">
                        {customer.full_name || customer.email}
                      </h3>
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${getStatusColor(customer.status)}`}
                      >
                        {customer.status}
                      </span>
                    </div>

                    <div className="space-y-1 text-sm text-gray-600">
                      <div className="flex items-center gap-2">
                        <MailIcon className="h-4 w-4 text-gray-400" />
                        <span className="truncate">{customer.email}</span>
                      </div>

                      {customer.phone && (
                        <div className="flex items-center gap-2">
                          <PhoneIcon className="h-4 w-4 text-gray-400" />
                          <span>{customer.phone}</span>
                        </div>
                      )}

                      {customer.country && (
                        <div className="flex items-center gap-2">
                          <MapPinIcon className="h-4 w-4 text-gray-400" />
                          <span>{customer.country}</span>
                        </div>
                      )}
                    </div>

                    <p className="text-xs text-gray-400 mt-2">
                      Joined {new Date(customer.created_at).toLocaleDateString()}
                    </p>
                  </div>

                  {/* Right: Action button */}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="shrink-0"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
