<script lang="ts">
	import { onMount } from 'svelte';
	import SideBarFooter from './SideBarFooter.svelte';
	import SideBarHeader from './SideBarHeader.svelte';
	import SideBarNavigation from './SideBarNavigation.svelte';
	import SideBarToggle from './SideBarToggle.svelte';
	import { writable } from 'svelte/store';

	import { getCookie, setCookie } from '$lib/utils/cookies';
	import { tableHandlers } from '$lib/utils/stores';
	import { m } from '$paraglide/messages';

	import { invalidateAll } from '$app/navigation';
	import { page } from '$app/stores';
		import { breadcrumbs, goto } from '$lib/utils/breadcrumbs';
			import { getFlash } from 'sveltekit-flash-message';
		import LoadingSpinner from '../utils/LoadingSpinner.svelte';
	import {
		getModalStore,
		type ModalComponent,
		type ModalSettings
	} from '$lib/components/Modals/stores';

	interface Props {
		open: boolean;
		sideBarVisibleItems: Record<string, boolean>;
	}

	let { open = $bindable(), sideBarVisibleItems }: Props = $props();

	const user = $page.data?.user;

		

	const modalStore = getModalStore();
	const flash = getFlash(page);

	const loading = writable(false);

	async function loadDemoDomain() {
		$loading = true;
		const response = await fetch('/folders/import-dummy/', { method: 'POST' });
		if (!response.ok) {
			if (response.status === 500) {
				flash.set({ type: 'error', message: m.demoDataAlreadyImported() });
			} else {
				flash.set({ type: 'error', message: m.errorOccuredDuringImport() });
			}
			console.error('Failed to load demo data');
			$loading = false;
			return false;
		}
		flash.set({ type: 'success', message: m.successfullyImportedFolder() });

		await goto('/folders', {
			crumbs: breadcrumbs,
			label: m.domains(),
			breadcrumbAction: 'replace'
		});

		invalidateAll();
		Object.values($tableHandlers).forEach((handler) => {
			handler.invalidate();
		});
		$loading = false;
		return true;
	}

	

	onMount(() => {
		// Removed first login modal logic
	});

	

	let classesSidebarOpen = $derived((open: boolean) => (open ? '' : '-ml-56 pointer-events-none'));
</script>

<div data-testid="sidebar" class="sidebar">
	<aside
		class="flex w-64 shadow transition-all duration-300 fixed h-screen overflow-visible top-0 left-0 z-20 {classesSidebarOpen(
			open
		)}"
	>
		<nav class="flex-1 flex flex-col overflow-y-auto overflow-x-hidden bg-surface-50-950 py-4 px-3">
			<SideBarHeader />
			<SideBarNavigation {sideBarVisibleItems} />
			<SideBarFooter />
		</nav>
	</aside>
	{#if $loading}
		<div
			class="fixed inset-0 flex items-center justify-center bg-surface-50-950 bg-opacity-60 z-1000"
		>
			<div class="flex flex-col items-center space-y-4 p-6 rounded-lg bg-surface-50-950 shadow-lg">
				<LoadingSpinner />

				<p class="text-sm text-surface-700-300 font-medium text-center">
					{m.importingDemoData()}
				</p>

				<p class="text-xs text-surface-600-400 text-center max-w-xs">
					{m.demoEnvironmentBeingPrepared()}
				</p>
			</div>
		</div>
	{/if}

	<SideBarToggle bind:open />
</div>
