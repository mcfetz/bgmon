import { describe, expect, it } from 'vitest';
import { calculateTir } from './tirCalculation';

describe('calculateTir', () => {
	it('returns zero percentages for empty array', () => {
		const result = calculateTir([], 70, 180);
		expect(result.inRange).toBe(0);
		expect(result.below).toBe(0);
		expect(result.above).toBe(0);
	});

	it('calculates percentages correctly', () => {
		const values = [60, 75, 100, 200, 250];
		const result = calculateTir(values, 70, 180);
		expect(result.below).toBe(20);
		expect(result.inRange).toBe(40);
		expect(result.above).toBe(40);
	});
});
