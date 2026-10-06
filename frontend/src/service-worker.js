/// <reference lib="webworker" />
/* eslint-disable no-undef */
/** @type {ServiceWorkerGlobalScope} */
const scope = /** @type {any} */ (self);
scope.addEventListener('push', (event) => {
	const data = event.data?.json() ?? {};
	const title = data.title || 'bgmon Alarm';
	const options = {
		body: data.body || '',
		icon: data.icon || '/icon-192.png',
		badge: data.badge || '/icon-192.png',
		tag: data.tag || 'bgmon-alarm',
		requireInteraction: data.requireInteraction ?? true
	};
	event.waitUntil(scope.registration.showNotification(title, options));
});

scope.addEventListener('notificationclick', (event) => {
	event.notification.close();
	event.waitUntil(scope.clients.openWindow('/'));
});
