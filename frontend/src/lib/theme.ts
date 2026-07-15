export interface UserColors {
	bgLight: string;
	primaryLight: string;
	bgDark: string;
	primaryDark: string;
	mode: string;
}

function lighten(hex: string, pct: number): string {
	const num = parseInt(hex.replace('#', ''), 16);
	const r = Math.min(255, (num >> 16) + Math.round(255 * pct / 100));
	const g = Math.min(255, (num >> 8) & 0xff) + Math.round(255 * pct / 100);
	const b = Math.min(255, (num & 0xff) + Math.round(255 * pct / 100));
	return '#' + (0x1000000 + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

function darken(hex: string, pct: number): string {
	return lighten(hex, -pct);
}

function isDarkMode(colors: UserColors): boolean {
	if (colors.mode === 'dark') return true;
	if (colors.mode === 'light') return false;
	return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export function applyUserColors(colors: UserColors) {
	const dark = isDarkMode(colors);
	const bg = dark ? colors.bgDark : colors.bgLight;
	const primary = dark ? colors.primaryDark : colors.primaryLight;
	const root = document.documentElement;

	if (bg) {
		root.style.setProperty('--color-bg', bg);
		root.style.setProperty('--color-surface', dark ? darken(bg, 6) : lighten(bg, 6));
		root.style.setProperty('--color-border-default', dark ? darken(bg, 10) : lighten(bg, 10));
		root.style.setProperty('--color-glass-bg', bg + 'cc');
	}
	if (primary) {
		root.style.setProperty('--color-primary', primary);
		root.style.setProperty('--color-primary-dark', darken(primary, 15));
	}
}

export function getStoredColors(): UserColors {
	return {
		bgLight: localStorage.getItem('bgmon_color_bg_light') || '',
		primaryLight: localStorage.getItem('bgmon_color_primary_light') || '',
		bgDark: localStorage.getItem('bgmon_color_bg_dark') || '',
		primaryDark: localStorage.getItem('bgmon_color_primary_dark') || '',
		mode: localStorage.getItem('bgmon_color_mode') || 'auto'
	};
}
