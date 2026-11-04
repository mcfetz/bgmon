import { describe, expect, it } from 'vitest';
import { diffGlobalSettings, type GlobalSettingsValues } from './globalSettings';

function values(overrides: Partial<GlobalSettingsValues> = {}): GlobalSettingsValues {
	return {
		insulin_action_hours: 4,
		correction_factor: 50,
		compression_low_enabled: true,
		insulin_stock: 3000,
		basal_stock: 1500,
		needle_stock: 100,
		sensor_stock: 5,
		low_stock_days: 14,
		...overrides
	};
}

describe('diffGlobalSettings', () => {
	it('returns nothing when the form was saved unchanged', () => {
		expect(diffGlobalSettings(values(), values())).toEqual({});
	});

	it('sends only the stock that actually changed', () => {
		const changed = diffGlobalSettings(values({ insulin_stock: 5742.5 }), values());

		expect(changed).toEqual({ insulin_stock: 5742.5 });
	});

	it('keeps the other stock fields out of the payload', () => {
		const changed = diffGlobalSettings(values({ needle_stock: 120 }), values());

		expect(changed).not.toHaveProperty('basal_stock');
		expect(changed).not.toHaveProperty('sensor_stock');
		expect(changed).not.toHaveProperty('insulin_stock');
	});

	it('treats an emptied field as a change to null', () => {
		expect(diffGlobalSettings(values({ basal_stock: null }), values())).toEqual({
			basal_stock: null
		});
	});

	it('sends the full payload when nothing was loaded yet', () => {
		expect(diffGlobalSettings(values(), null)).toEqual(values());
	});

	it('detects changes in the non-stock settings too', () => {
		const changed = diffGlobalSettings(
			values({ insulin_action_hours: 5, low_stock_days: 21, compression_low_enabled: false }),
			values()
		);

		expect(changed).toEqual({
			insulin_action_hours: 5,
			compression_low_enabled: false,
			low_stock_days: 21
		});
	});
});
