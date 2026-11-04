export interface GlobalSettingsValues {
	insulin_action_hours: number;
	correction_factor: number;
	compression_low_enabled: boolean;
	insulin_stock: number | null;
	basal_stock: number | null;
	needle_stock: number | null;
	sensor_stock: number | null;
	low_stock_days: number;
}

export type GlobalSettingsChanges = Partial<GlobalSettingsValues>;

export function diffGlobalSettings(
	current: GlobalSettingsValues,
	loaded: GlobalSettingsValues | null
): GlobalSettingsChanges {
	const changed: GlobalSettingsChanges = {};
	if (!loaded) return { ...current };

	if (current.insulin_action_hours !== loaded.insulin_action_hours) {
		changed.insulin_action_hours = current.insulin_action_hours;
	}
	if (current.correction_factor !== loaded.correction_factor) {
		changed.correction_factor = current.correction_factor;
	}
	if (current.compression_low_enabled !== loaded.compression_low_enabled) {
		changed.compression_low_enabled = current.compression_low_enabled;
	}
	if (current.insulin_stock !== loaded.insulin_stock) {
		changed.insulin_stock = current.insulin_stock;
	}
	if (current.basal_stock !== loaded.basal_stock) {
		changed.basal_stock = current.basal_stock;
	}
	if (current.needle_stock !== loaded.needle_stock) {
		changed.needle_stock = current.needle_stock;
	}
	if (current.sensor_stock !== loaded.sensor_stock) {
		changed.sensor_stock = current.sensor_stock;
	}
	if (current.low_stock_days !== loaded.low_stock_days) {
		changed.low_stock_days = current.low_stock_days;
	}

	return changed;
}
