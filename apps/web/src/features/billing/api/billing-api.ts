import { apiClient } from '@/lib/api-client';
import { fetchList, fetchOne, type ListParams } from '@/lib/crud';
import type { Invoice, Payment } from '@erp/api-types';

export const INVOICES_PATH = '/api/v1/billing/invoices/';

export const listInvoices = (params: ListParams) => fetchList<Invoice>(INVOICES_PATH, params);

export interface InvoiceLineInput {
  description: string;
  quantity: string;
  unit_price: string;
}

export interface InvoicePayload {
  enrollment_id: string;
  lines: InvoiceLineInput[];
  issue_date?: string;
  due_date?: string;
  notes?: string;
  /**
   * Omitted on purpose.
   *
   * The institution's configured currency is used, so the caller cannot issue
   * one invoice in pesos and the next in dollars for the same student -- there
   * would be no exchange rate to reconcile them. Present only for the rare
   * deliberate exception, and still validated against the supported list.
   */
  currency?: string;
}

export async function createInvoice(payload: InvoicePayload): Promise<Invoice> {
  const { data } = await apiClient.post<Invoice>(INVOICES_PATH, payload);
  return data;
}

/**
 * Enrollments that can be billed, as selector options.
 *
 * Filtered to `status=active` because the billing service refuses anything
 * else: offering a withdrawn enrollment would render a choice whose only
 * outcome is a 422.
 */
export async function listBillableEnrollments(): Promise<
  {
    id: string;
    student_name: string;
    program_name: string;
    academic_year_name: string;
  }[]
> {
  const { data } = await apiClient.get<{
    results: {
      id: string;
      student_name: string;
      program_name: string;
      academic_year_name: string;
    }[];
  }>('/api/v1/academic/enrollments/', {
    params: { status: 'active', page_size: 200, ordering: '-enrolled_on' },
  });
  return data.results;
}

export const getInvoice = (id: string) => fetchOne<Invoice>(INVOICES_PATH, id);

export interface PaymentPayload {
  amount: string;
  method: string;
  reference?: string;
  received_on?: string;
}

export async function registerPayment(
  invoiceId: string,
  payload: PaymentPayload,
): Promise<Payment> {
  const { data } = await apiClient.post<Payment>(
    `${INVOICES_PATH}${invoiceId}/payments/`,
    payload,
  );
  return data;
}

/**
 * Live academic context behind an invoice.
 *
 * Billing stores only `enrollment_id`, so this is a separate call rather than a
 * join — the academic context resolves it through its own service layer.
 * Returns `null` when the enrollment no longer exists, which is expected:
 * without a ForeignKey there is no cascade, so invoices outlive enrollments.
 */
export interface EnrollmentContext {
  enrollment_id: string;
  student_id: string;
  student_full_name: string;
  program_code: string;
  program_name: string;
  academic_year_name: string;
  status: string;
  is_billable: boolean;
}

export async function getInvoiceEnrollment(
  invoiceId: string,
): Promise<EnrollmentContext | null> {
  try {
    const { data } = await apiClient.get<EnrollmentContext>(
      `${INVOICES_PATH}${invoiceId}/enrollment/`,
    );
    return data;
  } catch {
    return null;
  }
}
