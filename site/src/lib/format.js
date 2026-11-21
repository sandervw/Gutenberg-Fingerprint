// Number and date formats shared by tables and charts.
const formatters = {
	wholeNumber: new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }),
	oneDecimal: new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
	twoDecimals: new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
	wholePercent: new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 0 }),
	percentOneDecimal: new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }),
	percentTwoDecimals: new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 })
};

/** Format a value by name (wholeNumber, percentOneDecimal); text passes through. */
export function formatValue(value, format) {
	if (value === null || value === undefined) return '';
	if (!format) return String(value);
	if (!(format in formatters)) throw new Error(`Unknown format: ${format}`);
	return formatters[format].format(value);
}

/** Format "2026-07-25" as "July 25, 2026". */
export function longDate(isoDate) {
	const options = { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' };
	return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString('en-US', options);
}
