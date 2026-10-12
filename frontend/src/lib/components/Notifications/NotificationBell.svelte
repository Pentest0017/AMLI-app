<script lang="ts">
	import { onMount } from 'svelte';

	interface NotificationItem {
		id: string;
		title: string;
		message: string;
		notification_type: string;
		link_url: string;
		is_read: boolean;
		created_at: string;
	}

	let isOpen = $state(false);
	let unreadCount = $state(0);
	let notifications = $state<NotificationItem[]>([]);
	let loading = $state(false);

	let activeTab = $state<'ALL' | 'UNREAD' | 'ASSIGNMENTS' | 'EVIDENCE' | 'INTERMEDIARY' | 'AUDITS' | 'ESCALATIONS'>('ALL');

	let filteredNotifications = $derived.by(() => {
		if (activeTab === 'UNREAD') {
			return notifications.filter((n) => !n.is_read);
		} else if (activeTab === 'ASSIGNMENTS') {
			return notifications.filter(
				(n) => n.notification_type === 'ASSIGNMENT' || (n.notification_type === 'INTERMEDIARY' && n.title.includes('Assignment'))
			);
		} else if (activeTab === 'EVIDENCE') {
			return notifications.filter(
				(n) => n.notification_type.includes('EVIDENCE') || (n.notification_type === 'INTERMEDIARY' && n.title.includes('Report'))
			);
		} else if (activeTab === 'INTERMEDIARY') {
			return notifications.filter((n) => n.notification_type === 'INTERMEDIARY');
		} else if (activeTab === 'AUDITS') {
			return notifications.filter((n) => n.notification_type.includes('AUDIT'));
		} else if (activeTab === 'ESCALATIONS') {
			return notifications.filter((n) => n.notification_type === 'ESCALATION');
		}
		return notifications;
	});

	async function fetchUnreadCount() {
		try {
			const res = await fetch('/api/notifications/unread-count/', { credentials: 'include' });
			if (res.ok) {
				const data = await res.json();
				unreadCount = data.unread_count ?? data.count ?? 0;
			}
		} catch (err) {
			console.error('Failed to fetch unread count:', err);
		}
	}

	async function fetchNotifications() {
		loading = true;
		try {
			const res = await fetch('/api/notifications/?limit=20', { credentials: 'include' });
			if (res.ok) {
				const data = await res.json();
				notifications = data.results || (Array.isArray(data) ? data : []);
				if (data.unread_count !== undefined) {
					unreadCount = data.unread_count;
				}
			}
		} catch (err) {
			console.error('Failed to fetch notifications:', err);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		fetchUnreadCount();
		fetchNotifications();

		const interval = setInterval(() => {
			fetchUnreadCount();
			if (isOpen) {
				fetchNotifications();
			}
		}, 8000);

		const handleUpdate = () => {
			fetchUnreadCount();
			fetchNotifications();
		};
		window.addEventListener('notification-update', handleUpdate);

		return () => {
			clearInterval(interval);
			window.removeEventListener('notification-update', handleUpdate);
		};
	});

	function toggleDropdown() {
		isOpen = !isOpen;
		if (isOpen) {
			fetchNotifications();
		}
	}

	async function markAsRead(notification: NotificationItem) {
		if (!notification.is_read) {
			notification.is_read = true;
			if (unreadCount > 0) unreadCount--;
			try {
				await fetch(`/api/notifications/${notification.id}/read/`, { method: 'POST' });
			} catch (err) {
				console.error('Failed to mark read:', err);
			}
		}
		if (notification.link_url) {
			isOpen = false;
			window.location.href = notification.link_url;
		}
	}

	async function markAllAsRead() {
		notifications = notifications.map((n) => ({ ...n, is_read: true }));
		unreadCount = 0;
		try {
			await fetch('/api/notifications/read-all/', { method: 'POST' });
		} catch (err) {
			console.error('Failed to mark all read:', err);
		}
	}

	function getNotificationIcon(type: string): string {
		switch (type) {
			case 'ASSIGNMENT':
				return 'fa-solid fa-list-check text-blue-500';
			case 'EVIDENCE_SUBMITTED':
				return 'fa-solid fa-cloud-arrow-up text-amber-500';
			case 'EVIDENCE_APPROVED':
				return 'fa-solid fa-circle-check text-emerald-500';
			case 'EVIDENCE_REJECTED':
				return 'fa-solid fa-circle-xmark text-rose-500';
			case 'ESCALATION':
				return 'fa-solid fa-triangle-exclamation text-rose-600';
			case 'AUDIT_PHASE_CHANGE':
				return 'fa-solid fa-arrows-rotate text-purple-500';
			default:
				return 'fa-solid fa-bell text-surface-500';
		}
	}

	function formatDate(iso: string): string {
		if (!iso) return '';
		const d = new Date(iso);
		return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	onMount(() => {
		fetchUnreadCount();
		fetchNotifications();
		const interval = setInterval(() => {
			fetchUnreadCount();
			if (isOpen) fetchNotifications();
		}, 10000);
		return () => clearInterval(interval);
	});
</script>

<div class="relative">
	<button
		onclick={toggleDropdown}
		aria-label="Notifications"
		class="relative p-2 rounded-lg border border-surface-200-800 bg-surface-100-900/80 text-surface-600-400 hover:bg-surface-200-800 hover:text-surface-900-100 transition-all cursor-pointer flex items-center justify-center w-9 h-9"
	>
		<i class="fa-solid fa-bell text-sm"></i>
		{#if unreadCount > 0}
			<span
				class="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white shadow-xs animate-pulse"
			>
				{unreadCount > 99 ? '99+' : unreadCount}
			</span>
		{/if}
	</button>

	{#if isOpen}
		<!-- Backdrop -->
		<button class="fixed inset-0 z-40 cursor-default" onclick={() => (isOpen = false)} aria-label="Close notifications dropdown"></button>

		<!-- Dropdown Panel -->
		<div
			class="absolute right-0 mt-2 z-50 w-80 sm:w-96 rounded-xl border border-surface-200-800 bg-surface-50-950 shadow-2xl overflow-hidden"
		>
			<div class="flex items-center justify-between px-4 py-3 border-b border-surface-200-800 bg-surface-100-900/50">
				<div class="flex items-center gap-2">
					<i class="fa-solid fa-bell text-surface-500"></i>
					<span class="font-semibold text-sm">Notifications</span>
					{#if unreadCount > 0}
						<span class="rounded-full bg-primary-500/20 px-2 py-0.5 text-xs text-primary-500 font-medium">
							{unreadCount} new
						</span>
					{/if}
				</div>
				{#if unreadCount > 0}
					<button
						onclick={markAllAsRead}
						class="text-xs text-primary-500 hover:underline font-medium cursor-pointer"
					>
						Mark all as read
					</button>
				{/if}
			</div>

			<!-- Category Filter Tabs -->
			<div class="flex items-center gap-1 px-3 py-1.5 border-b border-surface-200-800 bg-surface-100-900/30 overflow-x-auto text-[11px]">
				<button onclick={() => (activeTab = 'ALL')} class="px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors whitespace-nowrap {activeTab === 'ALL' ? 'bg-primary-500 text-white' : 'text-surface-600-400 hover:bg-surface-200-800'}">All</button>
				<button onclick={() => (activeTab = 'UNREAD')} class="px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors whitespace-nowrap {activeTab === 'UNREAD' ? 'bg-primary-500 text-white' : 'text-surface-600-400 hover:bg-surface-200-800'}">Unread</button>
				<button onclick={() => (activeTab = 'ASSIGNMENTS')} class="px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors whitespace-nowrap {activeTab === 'ASSIGNMENTS' ? 'bg-primary-500 text-white' : 'text-surface-600-400 hover:bg-surface-200-800'}">Assignments</button>
				<button onclick={() => (activeTab = 'EVIDENCE')} class="px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors whitespace-nowrap {activeTab === 'EVIDENCE' ? 'bg-primary-500 text-white' : 'text-surface-600-400 hover:bg-surface-200-800'}">Evidence</button>
				<button onclick={() => (activeTab = 'INTERMEDIARY')} class="px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors whitespace-nowrap {activeTab === 'INTERMEDIARY' ? 'bg-primary-500 text-white' : 'text-surface-600-400 hover:bg-surface-200-800'}">Intermediary</button>
				<button onclick={() => (activeTab = 'AUDITS')} class="px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors whitespace-nowrap {activeTab === 'AUDITS' ? 'bg-primary-500 text-white' : 'text-surface-600-400 hover:bg-surface-200-800'}">Audits</button>
				<button onclick={() => (activeTab = 'ESCALATIONS')} class="px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors whitespace-nowrap {activeTab === 'ESCALATIONS' ? 'bg-primary-500 text-white' : 'text-surface-600-400 hover:bg-surface-200-800'}">Escalations</button>
			</div>

			<div class="max-h-96 overflow-y-auto divide-y divide-surface-200-800/50">
				{#if loading && notifications.length === 0}
					<div class="p-6 text-center text-sm text-surface-500">Loading notifications...</div>
				{:else if filteredNotifications.length === 0}
					<div class="p-6 text-center text-sm text-surface-500">No notifications in this tab</div>
				{:else}
					{#each filteredNotifications as item}
						<button
							onclick={() => markAsRead(item)}
							class="w-full text-left p-3.5 hover:bg-surface-100-900/60 transition-colors flex items-start gap-3 cursor-pointer {item.is_read
								? 'opacity-70'
								: 'bg-primary-500/5 font-medium'}"
						>
							<div class="mt-0.5 text-base">
								<i class={getNotificationIcon(item.notification_type)}></i>
							</div>
							<div class="flex-1 min-w-0">
								<div class="flex items-center justify-between gap-1">
									<span class="text-xs font-semibold text-surface-900-100 truncate">{item.title}</span>
									<span class="text-[10px] text-surface-500 shrink-0">{formatDate(item.created_at)}</span>
								</div>
								<p class="text-xs text-surface-600-400 mt-1 line-clamp-2">{item.message}</p>
							</div>
						</button>
					{/each}
				{/if}
			</div>
		</div>
	{/if}
</div>
