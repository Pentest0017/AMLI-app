<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';

	pageTitle.set('Evidences Library');

	let { data } = $props();

	let loading = $state(false);
	let items = $state<any[]>(data?.items || []);

	$effect(() => {
		const newItems = data?.items || [];
		untrack(() => {
			items = newItems;
		});
	});

	// Filters State
	let selectedFramework = $state('');
	let selectedDomain = $state('');
	let statusTagFilter = $state('');
	let searchQuery = $state('');

	async function loadApprovedEvidences() {
		loading = true;
		try {
			let url = `/api/evidence-repository/?review_status=APPROVED&q=${encodeURIComponent(searchQuery)}`;
			const res = await fetch(url);
			if (res.ok) {
				const resData = await res.json();
				items = resData.results || [];
			}
		} catch (err) {
			console.error('Failed to load approved evidence library:', err);
		} finally {
			loading = false;
		}
	}

	// Extract unique frameworks for dropdown
	let frameworkOptions = $derived.by(() => {
		const set = new Set<string>();
		for (const item of items) {
			if (item.control?.framework) set.add(item.control.framework);
		}
		return Array.from(set).sort();
	});

	// Extract unique domains for dropdown
	let domainOptions = $derived.by(() => {
		const set = new Set<string>();
		for (const item of items) {
			if (item.control?.domain) set.add(item.control.domain);
		}
		return Array.from(set).sort();
	});

	// Filtered Evidences List
	let filteredItems = $derived.by(() => {
		const now = new Date();
		return items.filter((item) => {
			const isExpired = item.expiry_date ? new Date(item.expiry_date) < now : false;

			const matchesFw = !selectedFramework || item.control?.framework === selectedFramework;
			const matchesDom = !selectedDomain || item.control?.domain === selectedDomain;
			const matchesStatus =
				!statusTagFilter ||
				(statusTagFilter === 'ACTIVE' && !isExpired) ||
				(statusTagFilter === 'EXPIRED' && isExpired);

			const q = searchQuery.toLowerCase();
			const matchesSearch =
				!searchQuery ||
				item.title?.toLowerCase().includes(q) ||
				item.control?.ref_id?.toLowerCase().includes(q) ||
				item.control?.name?.toLowerCase().includes(q) ||
				item.control?.framework?.toLowerCase().includes(q) ||
				item.control?.domain?.toLowerCase().includes(q);

			return matchesFw && matchesDom && matchesStatus && matchesSearch;
		});
	});

	function isItemExpired(expiryDateStr: string | null): boolean {
		if (!expiryDateStr) return false;
		return new Date(expiryDateStr) < new Date();
	}

	function getAttachmentDownloadUrl(evidenceId: string): string {
		return `/evidences/${evidenceId}/attachment`;
	}

	onMount(() => {
		loadApprovedEvidences();
	});
</script>

<div class="p-6 space-y-6">
	<!-- Top Bar -->
	<div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
		<div>
			<h1 class="text-2xl font-bold text-surface-900-100 flex items-center gap-2">
				<i class="fa-solid fa-receipt text-primary-500"></i> Central Evidences Library
			</h1>
			<p class="text-xs text-surface-600-400">
				Central repository of all approved evidence files across the platform. Keeps historical evidence even after expiry with Active / Expired status tags.
			</p>
		</div>

		<button
			class="btn btn-sm variant-filled-surface flex items-center gap-1.5 cursor-pointer text-xs font-semibold"
			onclick={loadApprovedEvidences}
		>
			<i class="fa-solid fa-rotate-right"></i>
			<span>Refresh Library</span>
		</button>
	</div>

	<!-- Multi-Dimension Filter Bar (Framework, Domain, Control ID, Expiry Status) -->
	<div class="card p-4 shadow-md bg-surface-50-950 border border-surface-200-800 space-y-3">
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
			<!-- Framework Filter -->
			<div>
				<label class="text-[11px] font-bold text-surface-600-400 uppercase tracking-wider block mb-1">Framework:</label>
				<select bind:value={selectedFramework} class="select text-xs py-1.5 px-2 bg-surface-100-900 border border-surface-200-800 rounded w-full">
					<option value="">All Frameworks</option>
					{#each frameworkOptions as fw}
						<option value={fw}>{fw}</option>
					{/each}
				</select>
			</div>

			<!-- Domain Filter -->
			<div>
				<label class="text-[11px] font-bold text-surface-600-400 uppercase tracking-wider block mb-1">Domain:</label>
				<select bind:value={selectedDomain} class="select text-xs py-1.5 px-2 bg-surface-100-900 border border-surface-200-800 rounded w-full">
					<option value="">All Domains</option>
					{#each domainOptions as dom}
						<option value={dom}>{dom}</option>
					{/each}
				</select>
			</div>

			<!-- Expiry Status Filter -->
			<div>
				<label class="text-[11px] font-bold text-surface-600-400 uppercase tracking-wider block mb-1">Expiry Tag:</label>
				<select bind:value={statusTagFilter} class="select text-xs py-1.5 px-2 bg-surface-100-900 border border-surface-200-800 rounded w-full">
					<option value="">All Status Tags</option>
					<option value="ACTIVE">Active (Valid)</option>
					<option value="EXPIRED">Expired</option>
				</select>
			</div>

			<!-- Search Input -->
			<div>
				<label class="text-[11px] font-bold text-surface-600-400 uppercase tracking-wider block mb-1">Search Control / Title:</label>
				<div class="relative">
					<input
						type="text"
						placeholder="Search by ID, control, framework..."
						bind:value={searchQuery}
						class="input text-xs py-1.5 pl-8 pr-3 bg-surface-100-900 border border-surface-200-800 rounded w-full"
					/>
					<i class="fa-solid fa-magnifying-glass absolute left-2.5 top-2.5 text-xs text-surface-400"></i>
				</div>
			</div>
		</div>
	</div>

	<!-- Approved Evidences Grid Table -->
	<div class="card p-4 shadow-md bg-surface-50-950 border border-surface-200-800 space-y-3">
		<div class="flex items-center justify-between border-b border-surface-200-800 pb-2">
			<h3 class="text-xs font-bold uppercase tracking-wider text-surface-600-400">
				Approved Evidences ({filteredItems.length})
			</h3>
		</div>

		{#if loading}
			<div class="p-12 text-center text-xs text-surface-500">Loading central approved evidence library...</div>
		{:else if filteredItems.length === 0}
			<div class="p-16 text-center border border-dashed border-surface-200-800 rounded-lg space-y-2">
				<i class="fa-solid fa-folder-closed text-3xl text-surface-400"></i>
				<h4 class="text-sm font-bold text-surface-900-100">No Approved Evidences Found</h4>
				<p class="text-xs text-surface-500 max-w-sm mx-auto">
					There are currently no approved evidence items matching your filter criteria.
				</p>
			</div>
		{:else}
			<div class="table-container overflow-x-auto">
				<table class="table table-hover text-xs">
					<thead>
						<tr class="bg-surface-100-900 border-b border-surface-200-800 text-surface-600-400 font-semibold uppercase tracking-wider text-[11px]">
							<th class="py-2.5 px-3 text-left">Control ID</th>
							<th class="py-2.5 px-3 text-left">Framework & Domain</th>
							<th class="py-2.5 px-3 text-left">Evidence Document Title</th>
							<th class="py-2.5 px-3 text-center">Version</th>
							<th class="py-2.5 px-3 text-left">Expiry Date</th>
							<th class="py-2.5 px-3 text-center">Status Tag</th>
							<th class="py-2.5 px-3 text-right">Download</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredItems as item}
							{@const expired = isItemExpired(item.expiry_date)}
							<tr class="border-b border-surface-200-800/60 hover:bg-surface-100-900/60">
								<td class="py-3 px-3 font-mono font-bold text-primary-500">
									{item.control?.ref_id || 'N/A'}
								</td>
								<td class="py-3 px-3 text-surface-700-300">
									<span class="font-bold block text-surface-900-100">{item.control?.framework || 'General'}</span>
									<span class="text-[10px] text-surface-500 block">{item.control?.domain || 'General Domain'}</span>
								</td>
								<td class="py-3 px-3 font-medium text-surface-900-100">
									<div class="flex items-center space-x-2">
										<i class="fa-solid fa-file-shield text-emerald-500"></i>
										<div>
											<span class="font-bold block">{item.title}</span>
											<span class="text-[10px] text-surface-500 truncate block max-w-xs">{item.description || item.control?.name}</span>
										</div>
									</div>
								</td>
								<td class="py-3 px-3 text-center font-mono font-bold">
									<span class="badge variant-soft-surface text-xs">v{item.version || '1.0'}</span>
								</td>
								<td class="py-3 px-3 text-surface-600-400">
									{#if item.expiry_date}
										<span class={expired ? 'text-rose-500 font-bold' : ''}>{item.expiry_date}</span>
									{:else}
										<span class="text-surface-400 italic">No Expiry Set</span>
									{/if}
								</td>
								<td class="py-3 px-3 text-center">
									{#if expired}
										<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20">
											Expired
										</span>
									{:else}
										<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
											Active
										</span>
									{/if}
								</td>
								<td class="py-3 px-3 text-right">
									{#if item.evidence_id}
										<a
											href={getAttachmentDownloadUrl(item.evidence_id)}
											target="_blank"
											class="btn btn-xs variant-filled-primary cursor-pointer text-[11px]"
											title="Download Attachment"
										>
											<i class="fa-solid fa-download mr-1"></i> Download
										</a>
									{:else}
										<span class="text-surface-400 text-[10px] italic">No File</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
