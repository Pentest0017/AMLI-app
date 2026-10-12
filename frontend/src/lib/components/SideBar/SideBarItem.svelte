<script lang="ts">
	import { page } from '$app/state';
	import { safeTranslate } from '$lib/utils/i18n';
	import Anchor from '$lib/components/Anchor/Anchor.svelte';
	import { onMount } from 'svelte';

	interface Props {
		item?: { name: string; href: string; fa_icon: string }[];
		sideBarVisibleItems?: Record<string, boolean>;
	}

	let { item = [], sideBarVisibleItems }: Props = $props();

	let hasPendingAction = $state(false);

	async function checkPendingStatus() {
		try {
			const res = await fetch('/api/intermediary-compliance/pending-status/');
			if (res.ok) {
				const data = await res.json();
				hasPendingAction = !!data.has_pending_action;
			}
		} catch (e) {
			console.error('Error fetching pending status:', e);
		}
	}

	onMount(() => {
		checkPendingStatus();
		const interval = setInterval(checkPendingStatus, 15000);
		return () => clearInterval(interval);
	});

	let classesActive = $derived((href: string) =>
		href === page.url.pathname
			? 'bg-primary-100-900 text-primary-800-200'
			: 'hover:bg-primary-50-950 text-surface-950-50 '
	);
</script>

{#each item as item}
	<Anchor
		href={item.href}
		breadcrumbAction="replace"
		class="unstyled flex whitespace-nowrap items-center py-2 text-sm font-normal rounded-base {classesActive(
			item.href ?? ''
		)}"
		data-testid={'accordion-item-' + item.href.substring(1)}
	>
		<span
			class="px-4 flex items-center w-full space-x-2 text-xs pointer-events-none"
			id={item.name}
			title={safeTranslate(item.name)}
		>
			<i class="{item.fa_icon} w-1/12 pointer-events-none"></i>
			<span class="text-sm tracking-wide truncate pointer-events-none">{safeTranslate(item.name)}</span>
			{#if item.href === '/intermediary-compliance/repository' && hasPendingAction}
				<span class="ml-auto flex h-2 w-2 relative" title="Pending Review Action Required">
					<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-error-400 opacity-75"></span>
					<span class="relative inline-flex rounded-full h-2 w-2 bg-error-500"></span>
				</span>
			{/if}
		</span>
	</Anchor>
{/each}
