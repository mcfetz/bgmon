export interface TirResult {
	inRange: number;
	below: number;
	above: number;
}

export function calculateTir(values: number[], low: number, high: number): TirResult {
	if (values.length === 0) {
		return { inRange: 0, below: 0, above: 0 };
	}

	let below = 0;
	let inRange = 0;
	let above = 0;

	for (const value of values) {
		if (value < low) {
			below++;
		} else if (value > high) {
			above++;
		} else {
			inRange++;
		}
	}

	const total = values.length;
	return {
		inRange: Math.round((inRange / total) * 100),
		below: Math.round((below / total) * 100),
		above: Math.round((above / total) * 100)
	};
}
