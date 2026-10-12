<script lang="ts">
	import { pageTitle } from '$lib/utils/stores';
	import { onMount } from 'svelte';

	interface UserNode {
		id: string;
		email: string;
		first_name?: string;
		last_name?: string;
		designation?: string;
		department?: string;
		reports_to?: string | { id: string } | null;
		platform_role?: string;
		is_active?: boolean;
		is_superuser?: boolean;
		children?: UserNode[];
	}

	interface Props {
		data: {
			users: UserNode[];
		};
	}

	let { data }: Props = $props();

	let searchQuery = $state('');
	let selectedDepartment = $state('all');
	let expandedNodes = $state<Record<string, boolean>>({});

	onMount(() => {
		$pageTitle = 'Company Hierarchy';
		// Expand all nodes by default
		const initialExpanded: Record<string, boolean> = {};
		data.users.forEach((u) => {
			initialExpanded[u.id] = true;
		});
		expandedNodes = initialExpanded;
	});

	function getReportsToId(user: UserNode): string | null {
		if (!user.reports_to) return null;
		if (typeof user.reports_to === 'object' && user.reports_to.id) {
			return user.reports_to.id;
		}
		return String(user.reports_to);
	}

	function getUserName(user: UserNode): string {
		const full = `${user.first_name || ''} ${user.last_name || ''}`.trim();
		return full || user.email;
	}

	function getUserInitials(user: UserNode): string {
		if (user.first_name && user.last_name) {
			return `${user.first_name[0]}${user.last_name[0]}`.toUpperCase();
		}
		return user.email.slice(0, 2).toUpperCase();
	}

	function getRoleBadgeClass(role?: string): string {
		if (role === 'superadmin') return 'bg-purple-600/20 text-purple-400 border-purple-500/30';
		if (role === 'webadmin') return 'bg-indigo-600/20 text-indigo-400 border-indigo-500/30';
		if (role === 'admin') return 'bg-sky-600/20 text-sky-400 border-sky-500/30';
		return 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30';
	}

	// Filter non-superadmin users
	let nonSuperAdminUsers = $derived.by(() => {
		return data.users.filter((u) => u.platform_role !== 'superadmin' && !u.is_superuser);
	});

	// Filter departments list
	let departments = $derived.by(() => {
		const set = new Set<string>();
		nonSuperAdminUsers.forEach((u) => {
			if (u.department) set.add(u.department);
		});
		return Array.from(set);
	});

	// Build Hierarchy Tree strictly from reports_to relationship
	let hierarchyTree = $derived.by(() => {
		const userMap = new Map<string, UserNode>();
		const rootNodes: UserNode[] = [];

		nonSuperAdminUsers.forEach((u) => {
			userMap.set(u.id, { ...u, children: [] });
		});

		nonSuperAdminUsers.forEach((u) => {
			const node = userMap.get(u.id);
			if (!node) return;
			const managerId = getReportsToId(u);
			if (managerId && userMap.has(managerId)) {
				userMap.get(managerId)!.children!.push(node);
			} else {
				rootNodes.push(node);
			}
		});

		// Filter nodes matching search/dept while preserving parent-child tree structure
		function filterNode(node: UserNode): UserNode | null {
			const q = searchQuery.toLowerCase();
			const matchesSearch =
				!q ||
				getUserName(node).toLowerCase().includes(q) ||
				node.email.toLowerCase().includes(q) ||
				(node.designation || '').toLowerCase().includes(q) ||
				(node.department || '').toLowerCase().includes(q);

			const matchesDept =
				selectedDepartment === 'all' || node.department === selectedDepartment;

			const filteredChildren = (node.children || [])
				.map(filterNode)
				.filter((child): child is UserNode => child !== null);

			if ((matchesSearch && matchesDept) || filteredChildren.length > 0) {
				return {
					...node,
					children: filteredChildren
				};
			}

			return null;
		}

		return rootNodes
			.map(filterNode)
			.filter((node): node is UserNode => node !== null);
	});

	function toggleExpand(id: string) {
		expandedNodes[id] = !expandedNodes[id];
	}

	function expandAll() {
		const next: Record<string, boolean> = {};
		data.users.forEach((u) => (next[u.id] = true));
		expandedNodes = next;
	}

	function collapseAll() {
		expandedNodes = {};
	}
</script>

<div class="space-y-6 max-w-7xl mx-auto p-2">
	<!-- Top Header & Stats -->
	<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface-800/40 p-6 rounded-xl border border-surface-700/50 shadow-lg backdrop-blur-md">
		<div>
			<h1 class="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-primary-400 via-secondary-400 to-tertiary-400 bg-clip-text text-transparent">
				Company Hierarchy
			</h1>
			<p class="text-sm text-surface-400 mt-1">
				Organizational reporting structure built via manager reporting relationships
			</p>
		</div>

		<div class="flex items-center gap-4">
			<div class="flex items-center gap-3 bg-surface-900/60 px-4 py-2 rounded-lg border border-surface-700/60">
				<i class="fa-solid fa-users text-primary-400 text-lg"></i>
				<div>
					<div class="text-xs text-surface-400 uppercase font-semibold">Total Employees</div>
					<div class="text-lg font-bold text-surface-100">{nonSuperAdminUsers.length}</div>
				</div>
			</div>
			<div class="flex items-center gap-3 bg-surface-900/60 px-4 py-2 rounded-lg border border-surface-700/60">
				<i class="fa-solid fa-building text-secondary-400 text-lg"></i>
				<div>
					<div class="text-xs text-surface-400 uppercase font-semibold">Departments</div>
					<div class="text-lg font-bold text-surface-100">{departments.length}</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Controls & Search Bar -->
	<div class="flex flex-col sm:flex-row items-center justify-between gap-4 bg-surface-800/30 p-4 rounded-xl border border-surface-700/40">
		<div class="flex flex-wrap items-center gap-3 w-full sm:w-auto">
			<div class="relative min-w-[260px] flex-1 sm:flex-none">
				<i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-surface-400 text-sm"></i>
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search employees, titles, emails..."
					class="input pl-9 pr-4 py-2 text-sm bg-surface-900/80 border-surface-700 rounded-lg w-full focus:ring-2 focus:ring-primary-500"
				/>
			</div>

			{#if departments.length > 0}
				<select
					bind:value={selectedDepartment}
					class="select text-sm bg-surface-900/80 border-surface-700 rounded-lg py-2 px-3 focus:ring-2 focus:ring-primary-500"
				>
					<option value="all">All Departments ({departments.length})</option>
					{#each departments as dept}
						<option value={dept}>{dept}</option>
					{/each}
				</select>
			{/if}
		</div>

		<div class="flex items-center gap-2">
			<button
				type="button"
				onclick={expandAll}
				class="btn btn-sm variant-soft-primary text-xs font-semibold flex items-center gap-1.5"
			>
				<i class="fa-solid fa-expand"></i>
				Expand All
			</button>
			<button
				type="button"
				onclick={collapseAll}
				class="btn btn-sm variant-soft-surface text-xs font-semibold flex items-center gap-1.5"
			>
				<i class="fa-solid fa-compress"></i>
				Collapse All
			</button>
		</div>
	</div>

	<!-- Tree Container -->
	{#if hierarchyTree.length === 0}
		<div class="card p-12 text-center bg-surface-800/20 border border-surface-700/40 rounded-xl space-y-3">
			<i class="fa-solid fa-diagram-project text-4xl text-surface-500"></i>
			<h3 class="text-xl font-bold text-surface-200">No organizational records found</h3>
			<p class="text-sm text-surface-400">
				Try adjusting your search criteria or set manager relationships in User Management.
			</p>
		</div>
	{:else}
		<div class="overflow-x-auto pb-8 pt-2">
			<div class="min-w-max flex flex-col items-center space-y-8">
				{#each hierarchyTree as rootNode (rootNode.id)}
					<div class="flex flex-col items-center">
						<!-- Node Recursive Template -->
						{#snippet renderNode(node: UserNode)}
							{@const isExpanded = expandedNodes[node.id] ?? true}
							{@const hasChildren = node.children && node.children.length > 0}

							<div class="flex flex-col items-center relative">
								<!-- Node Card -->
								<div class="group relative bg-surface-800 border border-surface-700/80 hover:border-primary-500/60 p-4 rounded-xl shadow-md hover:shadow-xl transition-all duration-200 w-72 backdrop-blur-md">
									<div class="flex items-start gap-3">
										<div class="w-11 h-11 rounded-full bg-gradient-to-tr from-primary-600 to-secondary-600 flex items-center justify-center text-white font-bold text-sm shadow-md shrink-0 ring-2 ring-surface-700">
											{getUserInitials(node)}
										</div>
										<div class="flex-1 min-w-0">
											<div class="flex items-center justify-between gap-1">
												<h4 class="font-bold text-sm text-surface-100 truncate group-hover:text-primary-400 transition-colors">
													{getUserName(node)}
												</h4>
												{#if node.platform_role}
													<span class="text-[10px] font-semibold px-2 py-0.5 rounded-full border uppercase tracking-wider shrink-0 {getRoleBadgeClass(node.platform_role)}">
														{node.platform_role}
													</span>
												{/if}
											</div>

											<p class="text-xs text-surface-300 font-medium truncate mt-0.5">
												{node.designation || 'Team Member'}
											</p>

											<div class="flex flex-wrap items-center gap-1.5 mt-2">
												{#if node.department}
													<span class="inline-flex items-center gap-1 text-[11px] bg-surface-700/50 text-surface-300 px-2 py-0.5 rounded border border-surface-600/40">
														<i class="fa-solid fa-building text-[9px] text-primary-400"></i>
														{node.department}
													</span>
												{/if}
												<span class="inline-flex items-center gap-1 text-[11px] text-surface-400">
													<i class="fa-solid fa-envelope text-[9px]"></i>
													<span class="truncate max-w-[120px]">{node.email}</span>
												</span>
											</div>
										</div>
									</div>

									{#if hasChildren}
										<button
											type="button"
											onclick={() => toggleExpand(node.id)}
											class="absolute -bottom-3 left-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-surface-700 hover:bg-primary-600 text-surface-200 hover:text-white border border-surface-600 flex items-center justify-center text-xs shadow transition-colors cursor-pointer"
											title={isExpanded ? 'Collapse' : 'Expand'}
										>
											<i class="fa-solid {isExpanded ? 'fa-minus' : 'fa-plus'}"></i>
										</button>
									{/if}
								</div>

								<!-- Connector to children -->
								{#if hasChildren && isExpanded}
									<div class="w-0.5 h-6 bg-surface-600 my-1"></div>

									<div class="flex justify-center relative">
										{#if node.children!.length > 1}
											<div class="absolute top-0 left-0 right-0 h-0.5 bg-surface-600" style="left: calc({100 / (node.children!.length * 2)}%); right: calc({100 / (node.children!.length * 2)}%);"></div>
										{/if}

										<div class="flex gap-8 pt-1">
											{#each node.children! as child (child.id)}
												<div class="flex flex-col items-center relative">
													<div class="w-0.5 h-4 bg-surface-600"></div>
													{@render renderNode(child)}
												</div>
											{/each}
										</div>
									</div>
								{/if}
							</div>
						{/snippet}

						{@render renderNode(rootNode)}
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
