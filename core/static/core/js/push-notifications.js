/**
 * HomeGym - Push Notifications Manager
 * Handles Web Push Notification subscriptions
 */

class PushNotificationsManager {
    constructor() {
        this.swRegistration = null;
        this.publicVapidKey = null;
        this.isSupported = 'serviceWorker' in navigator && 'PushManager' in window;
    }

    /**
     * Initialize push notifications
     */
    async init() {
        if (!this.isSupported) {
            console.log('[Push] Not supported in this browser');
            return false;
        }

        try {
            // Get Service Worker registration
            this.swRegistration = await navigator.serviceWorker.ready;
            console.log('[Push] Service Worker ready');

            // Get VAPID public key from server
            const response = await fetch('/api/push/vapid-key/');
            if (!response.ok) {
                throw new Error('Failed to get VAPID key');
            }
            const data = await response.json();
            this.publicVapidKey = data.publicKey;
            console.log('[Push] VAPID key loaded');

            // Check current subscription status
            const subscription = await this.swRegistration.pushManager.getSubscription();
            if (subscription) {
                console.log('[Push] Already subscribed');
                return true;
            }

            return true;
        } catch (error) {
            console.error('[Push] Initialization error:', error);
            return false;
        }
    }

    /**
     * Request permission and subscribe
     */
    async subscribe() {
        try {
            // Request notification permission
            const permission = await Notification.requestPermission();
            
            if (permission !== 'granted') {
                console.log('[Push] Permission denied');
                return { success: false, message: 'Benachrichtigungen wurden abgelehnt' };
            }

            // Subscribe to push
            const subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(this.publicVapidKey)
            });

            console.log('[Push] Subscribed:', subscription);

            // Send subscription to server
            const response = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    subscription: subscription.toJSON()
                })
            });

            if (!response.ok) {
                throw new Error('Server subscription failed');
            }

            const result = await response.json();
            console.log('[Push] Server response:', result);

            return { success: true, message: result.message };

        } catch (error) {
            console.error('[Push] Subscribe error:', error);
            return { success: false, message: error.message };
        }
    }

    /**
     * Unsubscribe from push notifications
     */
    async unsubscribe() {
        try {
            const subscription = await this.swRegistration.pushManager.getSubscription();
            
            if (!subscription) {
                return { success: true, message: 'Keine aktive Subscription' };
            }

            // Unsubscribe from browser
            await subscription.unsubscribe();
            console.log('[Push] Unsubscribed from browser');

            // Tell server
            const response = await fetch('/api/push/unsubscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    endpoint: subscription.endpoint
                })
            });

            if (!response.ok) {
                throw new Error('Server unsubscribe failed');
            }

            const result = await response.json();
            return { success: true, message: result.message };

        } catch (error) {
            console.error('[Push] Unsubscribe error:', error);
            return { success: false, message: error.message };
        }
    }

    /**
     * Check if currently subscribed
     */
    async isSubscribed() {
        if (!this.swRegistration) return false;
        
        const subscription = await this.swRegistration.pushManager.getSubscription();
        return subscription !== null;
    }

    /**
     * Helper: Convert VAPID key
     */
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    /**
     * Helper: Get CSRF token
     */
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Global instance
window.pushManager = new PushNotificationsManager();

// Auto-initialize when ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.pushManager.init();
    });
} else {
    window.pushManager.init();
}
