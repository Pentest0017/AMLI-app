<script lang="ts">
	import { navData } from '$lib/components/SideBar/navData';

	import SideBarItem from '$lib/components/SideBar/SideBarItem.svelte';
	import SideBarCategory from '$lib/components/SideBar/SideBarCategory.svelte';
	import { Accordion } from '@skeletonlabs/skeleton-svelte';
	import { page } from '$app/state';
	import { lastAccordionItem } from '$lib/utils/stores';

	interface Props {
		sideBarVisibleItems?: Record<string, boolean>;
	}

	let { sideBarVisibleItems }: Props = $props();

	let items = $derived.by(() => {
		const user = page.data?.user;
		const isSuperOrWebAdmin = Boolean(
			user?.is_superuser ||
			user?.platform_role === 'superadmin' ||
			user?.platform_role === 'webadmin'
		);

		return navData.items
			.map((item) => {
				const filteredSubItems = item.items
					.filter((subItem) => {
						// Superadmins and superusers bypass feature toggle restrictions
						if (user?.platform_role === 'superadmin' || user?.is_superuser) {
							return true;
						}
						// For webadmin, admin, user, etc., check active_features returned from backend Access Matrix
						if (user?.active_features && Array.isArray(user.active_features)) {
							return user.active_features.includes(subItem.name);
						}
						return true;
					})
					.map((subItem) => {
						if (subItem.name === 'controlAssignments' && !isSuperOrWebAdmin) {
							return { ...subItem, href: '/control-assignments/submit' };
						}
						return subItem;
					});

				return {
					...item,
					items: filteredSubItems
				};
			})
			.filter((item) => item.items.length > 0);
	});

	function handleValueChange(details: { value: string[] }) {
		$lastAccordionItem = details.value;
	}
</script>

<nav class="grow scrollbar">
	<Accordion
		value={$lastAccordionItem}
		onValueChange={handleValueChange}
		collapsible
		class="space-y-4"
	>
		{#each items as item}
			<Accordion.Item value={item.name} id={item.name.toLowerCase().replace(' ', '-')}>
				<Accordion.ItemTrigger class="flex w-full items-center cursor-pointer">
					<SideBarCategory {item} />
					<Accordion.ItemIndicator
						class="transition-transform duration-200 data-[state=open]:rotate-0 data-[state=closed]:-rotate-90 text-primary-700-300"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="14px"
							height="14px"
							viewBox="0 0 448 512"
							fill="currentColor"
						>
							<path
								d="M201.4 374.6c12.5 12.5 32.8 12.5 45.3 0l160-160c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 306.7 86.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l160 160z"
							/>
						</svg>
					</Accordion.ItemIndicator>
				</Accordion.ItemTrigger>
				<Accordion.ItemContent class="space-y-2">
					<SideBarItem item={item.items} {sideBarVisibleItems} />
				</Accordion.ItemContent>
			</Accordion.Item>
		{/each}
	</Accordion>
</nav>
