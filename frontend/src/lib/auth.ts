let token: string | null = null;

export function setAuthToken(t: string) {
	token = t;
	localStorage.setItem('bgmon_token', t);
}

export function getAuthToken(): string | null {
	if (!token) {
		token = localStorage.getItem('bgmon_token');
	}
	return token;
}

export function clearAuthToken() {
	token = null;
	localStorage.removeItem('bgmon_token');
}

export async function apiFetch(path: string, options: RequestInit = {}) {
	const t = getAuthToken();
	const headers = new Headers(options.headers || {});
	if (t) {
		headers.set('Authorization', `Bearer ${t}`);
	}
	return fetch(path, {
		...options,
		headers
	});
}
