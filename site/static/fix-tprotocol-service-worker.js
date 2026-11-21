// Removes the service worker the old Evidence site installed at this path.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.registration.unregister());
