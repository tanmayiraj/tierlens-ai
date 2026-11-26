/**
 * Formats monetary amounts in Indian Rupees (INR, ₹).
 * Adheres to Indian numbering system (Lakhs, Crores).
 */
export function formatINR(amount?: number | null, compact: boolean = true): string {
  if (amount === undefined || amount === null || isNaN(amount)) {
    return '₹0';
  }

  const num = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';

  if (compact) {
    if (num >= 10_000_000) {
      const cr = (num / 10_000_000).toFixed(2).replace(/\.?0+$/, '');
      return `${sign}₹${cr} Cr`;
    }
    if (num >= 100_000) {
      const lakh = (num / 100_000).toFixed(2).replace(/\.?0+$/, '');
      return `${sign}₹${lakh} L`;
    }
    return `${sign}₹${num.toLocaleString('en-IN')}`;
  }

  return `${sign}₹${num.toLocaleString('en-IN')}`;
}

/**
 * Returns formatted amount with both Crores/Lakhs representation and full numeric INR string.
 * Example: "₹194.40 Cr (₹1,94,40,00,000)"
 */
export function formatINRExpanded(amount?: number | null): string {
  if (amount === undefined || amount === null || isNaN(amount) || amount === 0) {
    return '₹0';
  }
  const compact = formatINR(amount, true);
  const full = formatINR(amount, false);
  if (compact === full) {
    return full;
  }
  return `${compact} (${full})`;
}

export default {
  formatINR,
  formatINRExpanded,
};
