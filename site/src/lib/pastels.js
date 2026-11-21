// Pastel tokens --m1 to --m7, cycled by chart bars and table tabs.
const pastelCount = 7;

/** The pastel colour for a row index. */
export function pastel(index) {
	return `var(--m${(index % pastelCount) + 1})`;
}
