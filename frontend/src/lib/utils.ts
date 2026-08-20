import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTemplateDisplayName(templateId?: string | null): string {
  if (!templateId) return 'Unknown'
  const clean = templateId.trim().toLowerCase()
  if (clean === 'customer_letter_logo_v1print' || clean === 'customer_letter' || clean === 'customer_migration_letter') {
    return 'Customer Migration Letter'
  }
  if (clean === 'lod') return 'Letter of Demand (LOD)'
  if (clean === 'vat_confirmation') return 'VAT Confirmation'
  if (clean === 'final_notice') return 'Final Notice'
  if (clean === 'nonvat_home') return 'Non-VAT Home'
  if (clean === 'vat_home') return 'VAT Home'
  if (clean === 'nonvat_enterprise') return 'Non-VAT Enterprise'
  if (clean === 'vat_enterprise') return 'VAT Enterprise'
  if (clean === 'product_label_grouping') return 'Product Label Grouping'
  if (clean === 'subscription_ref_grouping') return 'Subscription Ref Grouping'
  if (clean === 'summary_statement') return 'Summary Statement'
  if (clean === 'invoice_of_summary') return 'Invoice of Summary'
  if (clean === 'usd_open_item') return 'USD Open Item'
  if (clean === 'vat_creditnote') return 'VAT Credit Note'
  if (clean === 'nonvat_creditnote') return 'Non-VAT Credit Note'
  
  return templateId
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function formatCycleDisplayName(folderType?: string | null | number, cycleNumber?: number | null): string {
  if (folderType === null || folderType === undefined || folderType === '') {
    return cycleNumber ? `Cycle ${cycleNumber}` : 'General'
  }
  
  const str = String(folderType).trim()
  
  // If it's pure numeric (e.g. 1, "1", 4, "4")
  if (/^\d+$/.test(str)) {
    return `Cycle ${str}`
  }

  const clean = str.toLowerCase()
  if (clean === 'customer_letter' || clean === 'customer_letter_logo_v1print' || clean === 'customer_migration_letter') {
    return 'Customer Migration Letter'
  }
  if (clean === 'lod' || clean === 'letter_of_demand') return 'Letter of Demand (LOD)'
  if (clean === 'vat_confirmation') return 'VAT Confirmation'
  if (clean === 'final_notice') return 'Final Notice'
  if (clean === 'test_gmfs' || clean === 'test_gmf') return 'Test GMF'

  if (cycleNumber) return `Cycle ${cycleNumber}`
  
  if (clean.startsWith('cycle')) {
    const num = str.replace(/[^0-9]/g, '')
    return num ? `Cycle ${num}` : str.replace(/_/g, ' ')
  }

  return str.replace(/_/g, ' ')
}
