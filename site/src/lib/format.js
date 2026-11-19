// Number and date formats shared by tables and charts.
const formatters = {
	num0: new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }),
	num1: new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
	num2: new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
	pct1: new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }),
	pct2: new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 })
};

/** Format a value by name (num0, pct1); text passes through. */
export function formatValue(value, format) {
	if (value === null || value === undefined) return '';
	return format ? formatters[format].format(value) : String(value);
}

/** Format "2026-07-25" as "July 25, 2026". */
export function longDate(isoDate) {
	const options = { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' };
	return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString('en-US', options);
}
