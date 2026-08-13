"""
TASK 9: CRM Dashboard with Micro-Interactions

Demonstrates:
- Glassmorphic data tables
- Animated status badges
- Smooth page transitions
- High-contrast typography
- Real-time metrics
- Responsive design
"""

'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  PageHeader,
  MetricCard,
  GlassmorphicTable,
  StatusBadge,
  containerVariants,
  itemVariants,
  SkeletonLoader
} from './ui/CRMComponents';

interface Customer {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  status: 'active' | 'inactive' | 'suspended';
  kyc_status: 'pending' | 'verified' | 'rejected';
  created_at: string;
}

interface TravelRequest {
  id: string;
  destination_country: string;
  travel_type: string;
  status: 'pending_documents' | 'documents_review' | 'docs_approved' | 'in_progress' | 'completed' | 'cancelled';
  documents_completion_percent: number;
  created_at: string;
}

export const CRMDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState({
    total_customers: 0,
    active_customers: 0,
    pending_kyc: 0,
    total_travel_requests: 0,
    pending_documents: 0,
    in_progress_requests: 0,
    completed_requests: 0,
    pending_webhooks: 0,
    pending_crm_syncs: 0
  });

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [travelRequests, setTravelRequests] = useState<TravelRequest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch('/api/v1/crm/metrics', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        const data = await response.json();
        if (data.success) {
          setMetrics(data.data);
        }
      } catch (error) {
        console.error('Failed to fetch metrics:', error);
      }
    };

    const fetchCustomers = async () => {
      try {
        const response = await fetch('/api/v1/crm/customers?limit=10', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        const data = await response.json();
        if (data.success) {
          setCustomers(data.customers);
        }
      } catch (error) {
        console.error('Failed to fetch customers:', error);
      }
    };

    const fetchTravelRequests = async () => {
      try {
        const response = await fetch('/api/v1/crm/travel-requests?limit=10', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        const data = await response.json();
        if (data.success) {
          setTravelRequests(data.data);
        }
      } catch (error) {
        console.error('Failed to fetch travel requests:', error);
      }
    };

    Promise.all([fetchMetrics(), fetchCustomers(), fetchTravelRequests()]).finally(
      () => setLoading(false)
    );
  }, []);

  if (loading) {
    return <SkeletonLoader count={10} />;
  }

  const metricIcons = {
    customers: '👥',
    requests: '✈️',
    documents: '📄',
    sync: '🔄'
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="min-h-screen p-6 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900"
    >
      {/* Page Header */}
      <PageHeader
        title="CRM Dashboard"
        subtitle="Portal & CRM Unified Management"
        icon="📊"
      />

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <MetricCard
          label="Total Customers"
          value={metrics.total_customers}
          icon={metricIcons.customers}
          change={{ value: 12, isPositive: true }}
        />
        <MetricCard
          label="Active Travel Requests"
          value={metrics.total_travel_requests}
          icon={metricIcons.requests}
          change={{ value: 5, isPositive: true }}
        />
        <MetricCard
          label="Pending Review"
          value={metrics.pending_documents}
          icon={metricIcons.documents}
          change={{ value: 3, isPositive: false }}
        />
        <MetricCard
          label="Sync Status"
          value={metrics.pending_crm_syncs}
          icon={metricIcons.sync}
          change={{ value: 0, isPositive: true }}
        />
      </div>

      {/* Customers Table */}
      <motion.div
        variants={itemVariants}
        className="mb-8"
      >
        <h2 className="text-2xl font-bold text-white mb-4">Recent Customers</h2>
        <GlassmorphicTable
          columns={[
            {
              key: 'email',
              label: 'Email',
              width: '2fr',
              render: (value) => (
                <span className="font-mono text-xs">{value}</span>
              )
            },
            {
              key: 'first_name',
              label: 'Name',
              render: (_, row) => `${row.first_name} ${row.last_name}`
            },
            {
              key: 'status',
              label: 'Status',
              render: (value) => <StatusBadge status={value} animated />
            },
            {
              key: 'kyc_status',
              label: 'KYC',
              render: (value) => <StatusBadge status={value} animated />
            }
          ]}
          data={customers}
          onRowClick={(row) => console.log('Customer clicked:', row)}
        />
      </motion.div>

      {/* Travel Requests Table */}
      <motion.div
        variants={itemVariants}
      >
        <h2 className="text-2xl font-bold text-white mb-4">Travel Requests</h2>
        <GlassmorphicTable
          columns={[
            {
              key: 'destination_country',
              label: 'Destination',
              width: '1.5fr'
            },
            {
              key: 'travel_type',
              label: 'Type',
              render: (value) => value.replace(/_/g, ' ').toUpperCase()
            },
            {
              key: 'status',
              label: 'Status',
              render: (value) => <StatusBadge status={value} animated />
            },
            {
              key: 'documents_completion_percent',
              label: 'Documents',
              render: (value) => (
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-white/20 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-blue-400 to-purple-400"
                      initial={{ width: 0 }}
                      animate={{ width: `${value}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                    />
                  </div>
                  <span className="text-xs font-semibold">{value}%</span>
                </div>
              )
            }
          ]}
          data={travelRequests}
          onRowClick={(row) => console.log('Request clicked:', row)}
        />
      </motion.div>

      {/* Footer Stats */}
      <motion.div
        variants={itemVariants}
        className="mt-8 p-6 rounded-xl text-center"
        style={{
          background: 'rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.2)'
        }}
      >
        <p className="text-white/60 text-sm">
          Last updated: {new Date().toLocaleTimeString()} • 
          {' '}<span className="text-green-400">● All systems operational</span>
        </p>
      </motion.div>
    </motion.div>
  );
};
