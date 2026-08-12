'use client';

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import type { ListParams } from '@/lib/crud';

import {
  createInvoice,
  getInvoice,
  getInvoiceEnrollment,
  listBillableEnrollments,
  listInvoices,
  registerPayment,
  type InvoicePayload,
  type PaymentPayload,
} from './billing-api';

export const billingKeys = {
  all: ['billing'] as const,
  invoices: (params: ListParams) => ['billing', 'invoices', params] as const,
  invoice: (id: string) => ['billing', 'invoice', id] as const,
  enrollment: (id: string) => ['billing', 'invoice', id, 'enrollment'] as const,
  billableEnrollments: ['billing', 'billable-enrollments'] as const,
};

export function useInvoices(params: ListParams) {
  return useQuery({
    queryKey: billingKeys.invoices(params),
    queryFn: () => listInvoices(params),
    placeholderData: keepPreviousData,
  });
}

export function useInvoice(id: string | null) {
  return useQuery({
    queryKey: billingKeys.invoice(id ?? 'none'),
    queryFn: () => getInvoice(id as string),
    enabled: Boolean(id),
  });
}

export function useInvoiceEnrollment(id: string | null) {
  return useQuery({
    queryKey: billingKeys.enrollment(id ?? 'none'),
    queryFn: () => getInvoiceEnrollment(id as string),
    enabled: Boolean(id),
  });
}

export function useBillableEnrollments() {
  return useQuery({
    queryKey: billingKeys.billableEnrollments,
    queryFn: listBillableEnrollments,
    staleTime: 60_000,
  });
}

export function useCreateInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InvoicePayload) => createInvoice(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: billingKeys.all }),
  });
}

export function useRegisterPayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ invoiceId, payload }: { invoiceId: string; payload: PaymentPayload }) =>
      registerPayment(invoiceId, payload),
    onSuccess: () => {
      // A payment changes both the invoice and the derived status shown in the
      // list, so invalidate the whole billing tree rather than one key.
      queryClient.invalidateQueries({ queryKey: billingKeys.all });
    },
  });
}
