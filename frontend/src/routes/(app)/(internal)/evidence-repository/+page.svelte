<script lang="ts">
	import { onMount } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';

	pageTitle.set('Evidence Repository');

	let { data } = $props();

	let loading = $state(false);
	let items = $state<any[]>(data?.items || []);
	let backendFrameworksTree = $state<any[]>(data?.frameworksTree || []);

	// Active Navigation State in Folder-File Tree: ROOT -> FRAMEWORK -> DOMAIN -> CONTROL
	let activeFolderType = $state<'ROOT' | 'FRAMEWORK' | 'DOMAIN' | 'CONTROL'>('ROOT');
	let activeFrameworkName = $state<string | null>(null);
	let activeDomainName = $state<string | null>(null);
	let activeControlRef = $state<string | null>(null);

	// Search & Filter
	let searchQuery = $state('');
	let statusFilter = $state('');

	// Action Toolbar State
	let selectedItem = $state<any>(null);
	let clipboard = $state<{ id: string; name: string; type: 'FILE' | 'FOLDER'; mode: 'CUT' | 'COPY' } | null>(null);

	// New Custom Folder Modal
	let showNewFolderModal = $state(false);
	let customFolderName = $state('');

	// Copy/Reuse Modal
	let copyingItem = $state<any>(null);
	let copyTargetAssessmentId = $state('');
	let copySaving = $state(false);
	let copyMessage = $state('');
	let assessments = $state<any[]>([]);

	// Version History Drawer/Modal
	let versionHistoryItem = $state<any>(null);

	// Delete Evidence Modal
	let deletingItem = $state<any>(null);
	let deleteSaving = $state(false);
	let deleteMessage = $state('');

	async function handleDeleteEvidence() {
		if (!deletingItem) return;
		deleteSaving = true;
		deleteMessage = '';
		try {
			const csrfMatch = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
			const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : '';
			const headers: Record<string, string> = { 'Content-Type': 'application/json' };
			if (csrfToken) headers['X-CSRFToken'] = csrfToken;

			const res = await fetch(`/api/evidence-repository/delete/${deletingItem.id}/`, {
				method: 'DELETE',
				headers,
			});
			if (res.ok) {
				deleteMessage = 'Evidence deleted successfully and logged.';
				setTimeout(() => {
					deletingItem = null;
					loadEvidenceRepository();
				}, 1000);
			} else {
				const err = await res.json().catch(() => ({}));
				deleteMessage = err.error || err.detail || err.message || `Failed to delete evidence (HTTP ${res.status}).`;
			}
		} catch (err) {
			deleteMessage = 'Network error during deletion.';
		} finally {
			deleteSaving = false;
		}
	}

	async function loadEvidenceRepository() {
		loading = true;
		try {
			let url = `/api/evidence-repository/?q=${encodeURIComponent(searchQuery)}`;
			if (statusFilter) url += `&review_status=${statusFilter}`;
			const res = await fetch(url);
			if (res.ok) {
				const data = await res.json();
				items = data.results || [];
				backendFrameworksTree = data.frameworks_tree || [];
			}
		} catch (err) {
			console.error('Failed to load evidence repository:', err);
		} finally {
			loading = false;
		}
	}

	async function loadAssessmentsList() {
		try {
			const res = await fetch('/api/compliance-assessments/');
			if (res.ok) {
				const data = await res.json();
				assessments = data.results || data || [];
			}
		} catch (err) {
			console.error('Failed to load assessments:', err);
		}
	}

	// Framework -> Domain -> Control Folder Tree Construction
	let frameworkFolders = $derived.by(() => {
		const fwMap = new Map<string, {
			name: string;
			domains: Map<string, {
				name: string;
				controls: Map<string, { ref_id: string; name: string; items: any[] }>;
				items: any[];
			}>;
			items: any[];
		}>();

		// 1. Pre-populate all frameworks, domains, and controls from backend frameworks_tree
		for (const fw of backendFrameworksTree) {
			if (!fwMap.has(fw.name)) {
				fwMap.set(fw.name, { name: fw.name, domains: new Map(), items: [] });
			}
			const fwEntry = fwMap.get(fw.name)!;
			for (const dom of (fw.domains || [])) {
				if (!fwEntry.domains.has(dom.name)) {
					fwEntry.domains.set(dom.name, { name: dom.name, controls: new Map(), items: [] });
				}
				const domEntry = fwEntry.domains.get(dom.name)!;
				for (const c of (dom.controls || [])) {
					if (!domEntry.controls.has(c.ref_id)) {
						domEntry.controls.set(c.ref_id, { ref_id: c.ref_id, name: c.name, items: [] });
					}
				}
			}
		}

		// 2. Populate uploaded evidence items into matching control/domain/framework
		for (const item of items) {
			const fwName = item.control?.framework || 'General Framework';
			const domName = item.control?.domain || 'General Domain';
			const ctrlRef = item.control?.ref_id || 'General Control';

			if (!fwMap.has(fwName)) {
				fwMap.set(fwName, { name: fwName, domains: new Map(), items: [] });
			}
			const fw = fwMap.get(fwName)!;
			fw.items.push(item);

			if (!fw.domains.has(domName)) {
				fw.domains.set(domName, { name: domName, controls: new Map(), items: [] });
			}
			const dom = fw.domains.get(domName)!;
			dom.items.push(item);

			if (!dom.controls.has(ctrlRef)) {
				dom.controls.set(ctrlRef, { ref_id: ctrlRef, name: item.control?.name || '', items: [] });
			}
			dom.controls.get(ctrlRef)!.items.push(item);
		}

		return Array.from(fwMap.values());
	});

	let currentFrameworkFolder = $derived.by(() => {
		if (!activeFrameworkName) return null;
		return frameworkFolders.find((f) => f.name === activeFrameworkName) || null;
	});

	let currentDomainFolder = $derived.by(() => {
		if (!currentFrameworkFolder || !activeDomainName) return null;
		return currentFrameworkFolder.domains.get(activeDomainName) || null;
	});

	let currentControlFolder = $derived.by(() => {
		if (!currentDomainFolder || !activeControlRef) return null;
		return currentDomainFolder.controls.get(activeControlRef) || null;
	});

	let displayFiles = $derived.by(() => {
		if (activeFolderType === 'CONTROL' && currentControlFolder) {
			return currentControlFolder.items;
		}
		if (activeFolderType === 'DOMAIN' && currentDomainFolder) {
			return currentDomainFolder.items;
		}
		if (activeFolderType === 'FRAMEWORK' && currentFrameworkFolder) {
			return currentFrameworkFolder.items;
		}
		return items;
	});

	function navigateToRoot() {
		activeFolderType = 'ROOT';
		activeFrameworkName = null;
		activeDomainName = null;
		activeControlRef = null;
		selectedItem = null;
	}

	function navigateToFramework(fwName: string) {
		activeFolderType = 'FRAMEWORK';
		activeFrameworkName = fwName;
		activeDomainName = null;
		activeControlRef = null;
		selectedItem = null;
	}

	function navigateToDomain(domName: string) {
		activeFolderType = 'DOMAIN';
		activeDomainName = domName;
		activeControlRef = null;
		selectedItem = null;
	}

	function navigateToControl(ctrlRef: string) {
		activeFolderType = 'CONTROL';
		activeControlRef = ctrlRef;
		selectedItem = null;
	}

	function openCopyModal(item: any) {
		copyingItem = item;
		copyTargetAssessmentId = '';
		copyMessage = '';
		loadAssessmentsList();
	}

	function handleCut() {
		if (!selectedItem) return;
		clipboard = { id: selectedItem.id, name: selectedItem.title || selectedItem.name, type: 'FILE', mode: 'CUT' };
	}

	function handleCopy() {
		if (!selectedItem) return;
		clipboard = { id: selectedItem.id, name: selectedItem.title || selectedItem.name, type: 'FILE', mode: 'COPY' };
	}

	async function handleCopyReuse() {
		if (!copyingItem || !copyTargetAssessmentId) {
			copyMessage = 'Please select a target audit/assessment.';
			return;
		}
		copySaving = true;
		copyMessage = '';
		try {
			const res = await fetch('/api/evidence-repository/copy/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					source_link_id: copyingItem.id,
					target_assessment_id: copyTargetAssessmentId,
				})
			});
			if (res.ok) {
				copyMessage = 'Evidence successfully reused in target assessment!';
				setTimeout(() => {
					copyingItem = null;
					loadEvidenceRepository();
				}, 1200);
			} else {
				const err = await res.json();
				copyMessage = err.error || 'Failed to reuse evidence.';
			}
		} catch (err) {
			copyMessage = 'Network error during copy.';
		} finally {
			copySaving = false;
		}
	}

	function getStatusBadge(status: string) {
		switch (status) {
			case 'APPROVED': return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
			case 'REJECTED': return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
			case 'EXPIRED': return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
			default: return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
		}
	}

	function getAttachmentDownloadUrl(evidenceId: string): string {
		return `/evidences/${evidenceId}/attachment`;
	}

	onMount(() => {
		loadEvidenceRepository();
		loadAssessmentsList();
	});
</script>

<div class="p-6 space-y-6">
	<!-- Top Bar & Function Toolbar -->
	<div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
		<div>
			<h1 class="text-2xl font-bold text-surface-900-100">Evidence Repository</h1>
			<p class="text-xs text-surface-600-400">
				Framework-Based Hierarchy: <code>Evidence Repository</code> &rarr; <code>Framework Folder</code> &rarr; <code>Domain Folder</code> &rarr; <code>Control Folder</code> &rarr; <code>Evidences (with Version Numbers & Status Tags)</code>.
			</p>
		</div>

		<!-- Action Toolbar -->
		<div class="flex flex-wrap items-center gap-2 bg-surface-100-900 p-2 rounded-container border border-surface-200-800 shadow-xs">
			{#if clipboard}
				<div class="flex items-center gap-1.5 px-3 py-1 bg-primary-500/10 text-primary-500 text-xs font-semibold rounded border border-primary-500/20 mr-2">
					<i class={clipboard.mode === 'CUT' ? 'fa-solid fa-scissors' : 'fa-solid fa-copy'}></i>
					<span>{clipboard.mode}: {clipboard.name}</span>
					<button class="hover:text-error-500 ml-1 cursor-pointer" onclick={() => (clipboard = null)} title="Clear Clipboard">&times;</button>
				</div>
			{/if}

			<button
				class="btn btn-sm variant-filled-primary flex items-center gap-1.5 cursor-pointer text-xs font-semibold"
				onclick={() => (showNewFolderModal = true)}
				title="Create Custom Folder"
			>
				<i class="fa-solid fa-folder-plus"></i>
				<span>+ New Folder</span>
			</button>

			<button
				class="btn btn-sm variant-soft-secondary flex items-center gap-1.5 disabled:opacity-40 cursor-pointer text-xs font-semibold"
				disabled={!selectedItem}
				onclick={handleCut}
				title="Cut Selected Evidence File"
			>
				<i class="fa-solid fa-scissors"></i>
				<span>Cut</span>
			</button>

			<button
				class="btn btn-sm variant-soft-secondary flex items-center gap-1.5 disabled:opacity-40 cursor-pointer text-xs font-semibold"
				disabled={!selectedItem}
				onclick={handleCopy}
				title="Copy Selected Evidence File"
			>
				<i class="fa-solid fa-copy"></i>
				<span>Copy</span>
			</button>

			<button
				class="btn btn-sm variant-soft-success flex items-center gap-1.5 disabled:opacity-40 cursor-pointer text-xs font-semibold"
				disabled={!selectedItem}
				onclick={() => selectedItem && openCopyModal(selectedItem)}
				title="Reuse Evidence File in Target Audit"
			>
				<i class="fa-solid fa-share-nodes"></i>
				<span>Reuse</span>
			</button>

			<div class="h-5 w-px bg-surface-300-700 mx-1"></div>

			<!-- Status Filter -->
			<select
				bind:value={statusFilter}
				onchange={loadEvidenceRepository}
				class="select text-xs py-1.5 px-2 bg-surface-50-950 border border-surface-200-800 rounded font-medium"
			>
				<option value="">All Statuses</option>
				<option value="APPROVED">Approved Only</option>
				<option value="PENDING_REVIEW">Pending Review</option>
				<option value="REJECTED">Rejected</option>
				<option value="EXPIRED">Expired</option>
			</select>

			<!-- Search Bar -->
			<div class="relative w-48 sm:w-60">
				<input
					type="text"
					placeholder="Search evidence..."
					bind:value={searchQuery}
					onkeyup={loadEvidenceRepository}
					class="input text-xs py-1.5 pl-8 pr-3 bg-surface-50-950 border border-surface-200-800 rounded"
				/>
				<i class="fa-solid fa-magnifying-glass absolute left-2.5 top-2.5 text-xs text-surface-400"></i>
			</div>

			<button
				class="btn btn-sm variant-filled-surface flex items-center gap-1.5 cursor-pointer text-xs font-semibold"
				onclick={loadEvidenceRepository}
				title="Refresh Evidence Repository"
			>
				<i class="fa-solid fa-rotate-right"></i>
				<span>Refresh</span>
			</button>
		</div>
	</div>

	<!-- Interactive Breadcrumb Path Bar -->
	<div class="flex items-center space-x-2 text-sm card p-3 variant-soft-surface flex-wrap gap-y-1">
		<i class="fa-solid fa-folder-tree text-primary-500 mr-1"></i>
		<button class="font-medium hover:underline text-surface-900-100 cursor-pointer flex items-center gap-1" onclick={navigateToRoot}>
			<span>Evidence Repository</span>
			<span class="badge variant-soft text-xs">ROOT</span>
		</button>

		{#if currentFrameworkFolder}
			<span class="text-surface-400">&gt;</span>
			<button class="font-medium hover:underline text-surface-900-100 cursor-pointer flex items-center gap-1" onclick={() => navigateToFramework(currentFrameworkFolder!.name)}>
				<span>{currentFrameworkFolder.name}</span>
				<span class="badge variant-soft text-xs">FRAMEWORK</span>
			</button>
		{/if}

		{#if currentDomainFolder}
			<span class="text-surface-400">&gt;</span>
			<button class="font-medium hover:underline text-surface-900-100 cursor-pointer flex items-center gap-1" onclick={() => navigateToDomain(currentDomainFolder!.name)}>
				<span>{currentDomainFolder.name}</span>
				<span class="badge variant-soft text-xs">DOMAIN</span>
			</button>
		{/if}

		{#if currentControlFolder}
			<span class="text-surface-400">&gt;</span>
			<button class="font-medium hover:underline text-surface-900-100 cursor-pointer flex items-center gap-1" onclick={() => navigateToControl(currentControlFolder!.ref_id)}>
				<span>{currentControlFolder.ref_id} - {currentControlFolder.name}</span>
				<span class="badge variant-soft text-xs">CONTROL</span>
			</button>
		{/if}
	</div>

	<!-- Main Repository Explorer Grid -->
	<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
		<!-- Left: Framework -> Domain -> Control Folder Hierarchy Tree Panel -->
		<div class="card p-4 shadow-md bg-surface-50-950 space-y-3 lg:col-span-1 border border-surface-200-800">
			<h2 class="text-sm font-bold uppercase tracking-wider text-surface-600-400 border-b border-surface-200-800 pb-2">
				Folder Hierarchy
			</h2>

			<div class="space-y-1 max-h-[600px] overflow-y-auto pr-1 text-xs font-mono">
				<!-- Root Node -->
				<div
					class="flex items-center justify-between p-2 rounded cursor-pointer transition-colors hover:bg-surface-200-800 {activeFolderType === 'ROOT' ? 'ring-2 ring-primary-500 bg-primary-500/10 font-bold' : ''}"
					onclick={navigateToRoot}
				>
					<div class="flex items-center space-x-2 truncate">
						<i class="fa-solid fa-hard-drive text-primary-500"></i>
						<span class="truncate font-semibold">Evidence Repository</span>
					</div>
					<span class="badge variant-soft text-[10px]">{items.length}</span>
				</div>

				<!-- Framework Folders -->
				{#each frameworkFolders as fw}
					<div
						class="flex items-center justify-between p-2 rounded cursor-pointer transition-colors hover:bg-surface-200-800 ml-3 {activeFolderType === 'FRAMEWORK' && activeFrameworkName === fw.name ? 'ring-2 ring-primary-500 bg-primary-500/10 font-bold' : ''}"
						onclick={() => navigateToFramework(fw.name)}
					>
						<div class="flex items-center space-x-2 truncate">
							<i class="fa-solid fa-folder text-amber-500"></i>
							<span class="truncate font-semibold">{fw.name}</span>
						</div>
						<span class="badge variant-soft text-[10px]">{fw.items.length}</span>
					</div>

					<!-- Domain Folders under active Framework -->
					{#if activeFrameworkName === fw.name}
						{#each Array.from(fw.domains.values()) as dom}
							<div
								class="flex items-center justify-between p-1.5 rounded cursor-pointer transition-colors hover:bg-surface-200-800 ml-6 {activeFolderType === 'DOMAIN' && activeDomainName === dom.name ? 'ring-2 ring-primary-500 bg-primary-500/10 font-bold' : ''}"
								onclick={() => navigateToDomain(dom.name)}
							>
								<div class="flex items-center space-x-2 truncate">
									<i class="fa-solid fa-folder-open text-blue-500"></i>
									<span class="truncate">{dom.name}</span>
								</div>
								<span class="badge variant-soft text-[10px]">{dom.items.length}</span>
							</div>

							<!-- Control Folders under active Domain -->
							{#if activeDomainName === dom.name}
								{#each Array.from(dom.controls.values()) as ctrl}
									<div
										class="flex items-center justify-between p-1.5 rounded cursor-pointer transition-colors hover:bg-surface-200-800 ml-9 {activeFolderType === 'CONTROL' && activeControlRef === ctrl.ref_id ? 'ring-2 ring-primary-500 bg-primary-500/10 font-bold' : ''}"
										onclick={() => navigateToControl(ctrl.ref_id)}
									>
										<div class="flex items-center space-x-2 truncate text-primary-500">
											<i class="fa-solid fa-file-lines text-emerald-500"></i>
											<span class="truncate">{ctrl.ref_id}</span>
										</div>
										<span class="badge variant-soft text-[10px]">{ctrl.items.length}</span>
									</div>
								{/each}
							{/if}
						{/each}
					{/if}
				{/each}
			</div>
		</div>

		<!-- Right: Files and Subfolders View Panel -->
		<div class="lg:col-span-3 space-y-4">
			<!-- Folder Navigation Cards -->
			{#if activeFolderType === 'ROOT'}
				<div class="card p-4 shadow-md bg-surface-50-950 border border-surface-200-800 space-y-3">
					<h3 class="text-xs font-bold uppercase tracking-wider text-surface-600-400">Framework Folders ({frameworkFolders.length})</h3>
					{#if frameworkFolders.length === 0}
						<p class="text-xs text-surface-500 py-4 text-center italic">No evidence folders found in repository.</p>
					{:else}
						<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
							{#each frameworkFolders as fw}
								<div
									class="p-3 rounded-lg border border-surface-200-800 bg-surface-100-900 hover:border-primary-500 cursor-pointer transition-all flex items-center justify-between"
									onclick={() => navigateToFramework(fw.name)}
								>
									<div class="flex items-center space-x-2 truncate">
										<i class="fa-solid fa-folder text-amber-500 text-lg"></i>
										<div class="truncate">
											<span class="text-xs font-bold text-surface-900-100 truncate block">{fw.name}</span>
											<span class="text-[10px] text-surface-500">{fw.domains.size} Domains</span>
										</div>
									</div>
									<span class="badge variant-soft text-xs">{fw.items.length} files</span>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{:else if activeFolderType === 'FRAMEWORK' && currentFrameworkFolder}
				<div class="card p-4 shadow-md bg-surface-50-950 border border-surface-200-800 space-y-3">
					<h3 class="text-xs font-bold uppercase tracking-wider text-surface-600-400">Domain Folders inside '{currentFrameworkFolder.name}' ({currentFrameworkFolder.domains.size})</h3>
					<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-h-96 overflow-y-auto p-1">
						{#each Array.from(currentFrameworkFolder.domains.values()) as dom}
							<div
								class="p-3 rounded-lg border border-surface-200-800 bg-surface-100-900 hover:border-primary-500 cursor-pointer transition-all flex items-center justify-between"
								onclick={() => navigateToDomain(dom.name)}
							>
								<div class="flex items-center space-x-2 truncate">
									<i class="fa-solid fa-folder-open text-blue-500 text-lg"></i>
									<div class="truncate">
										<span class="text-xs font-bold text-surface-900-100 truncate block">{dom.name}</span>
										<span class="text-[10px] text-surface-500">{dom.controls.size} Controls</span>
									</div>
								</div>
								<span class="badge variant-soft text-xs">{dom.items.length} files</span>
							</div>
						{/each}
					</div>
				</div>
			{:else if activeFolderType === 'DOMAIN' && currentDomainFolder}
				<div class="card p-4 shadow-md bg-surface-50-950 border border-surface-200-800 space-y-3">
					<h3 class="text-xs font-bold uppercase tracking-wider text-surface-600-400">Control Folders inside '{currentDomainFolder.name}' ({currentDomainFolder.controls.size})</h3>
					<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-h-96 overflow-y-auto p-1">
						{#each Array.from(currentDomainFolder.controls.values()) as ctrl}
							<div
								class="p-3 rounded-lg border border-surface-200-800 bg-surface-100-900 hover:border-primary-500 cursor-pointer transition-all flex items-center justify-between"
								onclick={() => navigateToControl(ctrl.ref_id)}
							>
								<div class="flex items-center space-x-2 truncate">
									<i class="fa-solid fa-file-lines text-emerald-500 text-lg"></i>
									<div class="truncate">
										<span class="text-xs font-bold text-surface-900-100 truncate block">{ctrl.ref_id}</span>
										<span class="text-[10px] text-surface-500 truncate block">{ctrl.name}</span>
									</div>
								</div>
								<span class="badge variant-soft text-xs">{ctrl.items.length} files</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Evidence Files List Table -->
			<div class="card p-4 shadow-md bg-surface-50-950 border border-surface-200-800 space-y-3">
				<div class="flex items-center justify-between border-b border-surface-200-800 pb-2">
					<h3 class="text-xs font-bold uppercase tracking-wider text-surface-600-400">
						Evidence Files ({displayFiles.length})
					</h3>
				</div>

				{#if loading}
					<div class="p-8 text-center text-xs text-surface-500">Loading evidence repository files...</div>
				{:else if displayFiles.length === 0}
					<div class="p-12 text-center border border-dashed border-surface-200-800 rounded-lg">
						<i class="fa-solid fa-folder-open text-3xl text-surface-400 mb-2"></i>
						<p class="text-xs text-surface-500">No evidence files located in this folder view.</p>
					</div>
				{:else}
					<div class="table-container overflow-x-auto">
						<table class="table table-hover text-xs">
							<thead>
								<tr class="bg-surface-100-900 border-b border-surface-200-800 text-surface-600-400 font-semibold uppercase tracking-wider text-[11px]">
									<th class="py-2.5 px-3 text-left">Control</th>
									<th class="py-2.5 px-3 text-left">Evidence Document Title</th>
									<th class="py-2.5 px-3 text-center">Version</th>
									<th class="py-2.5 px-3 text-center">Review Status</th>
									<th class="py-2.5 px-3 text-left">Expiry Date</th>
									<th class="py-2.5 px-3 text-right">Actions</th>
								</tr>
							</thead>
							<tbody>
								{#each displayFiles as item}
									<tr
										class="border-b border-surface-200-800/60 cursor-pointer hover:bg-surface-100-900/60 {selectedItem?.id === item.id ? 'bg-primary-500/10' : ''}"
										onclick={() => (selectedItem = item)}
									>
										<td class="py-3 px-3 font-mono font-bold text-primary-500">
											{item.control?.ref_id || 'N/A'}
										</td>
										<td class="py-3 px-3 font-medium text-surface-900-100">
											<div class="flex items-center space-x-2">
												<i class="fa-solid fa-file-pdf text-rose-500"></i>
												<div>
													<span class="font-bold block">{item.title}</span>
													<span class="text-[10px] text-surface-500 truncate block max-w-xs">{item.description || item.control?.name}</span>
												</div>
											</div>
										</td>
										<td class="py-3 px-3 text-center">
											<span class="badge variant-soft-surface font-mono font-bold text-xs">v{item.version || '1.0'}</span>
										</td>
										<td class="py-3 px-3 text-center">
											<span class="px-2 py-0.5 rounded text-[11px] font-bold border {getStatusBadge(item.review_status)}">
												{item.review_status || 'PENDING_REVIEW'}
											</span>
										</td>
										<td class="py-3 px-3 text-surface-600-400">
											{#if item.expiry_date}
												<span class={item.expiry_warning ? 'text-amber-500 font-bold' : ''}>
													{item.expiry_date}
												</span>
											{:else}
												<span class="text-surface-400 italic">No Expiry Set</span>
											{/if}
										</td>
										<td class="py-3 px-3 text-right space-x-1">
											{#if item.evidence_id}
												<a
													href={getAttachmentDownloadUrl(item.evidence_id)}
													target="_blank"
													class="btn btn-xs variant-soft-primary cursor-pointer text-[11px]"
													title="Download Attachment"
													onclick={(e) => e.stopPropagation()}
												>
													<i class="fa-solid fa-download"></i>
												</a>
											{/if}
											<button
												class="btn btn-xs variant-soft-surface cursor-pointer text-[11px]"
												onclick={(e) => { e.stopPropagation(); versionHistoryItem = item; }}
												title="View Version History"
											>
												<i class="fa-solid fa-clock-rotate-left"></i>
											</button>
											<button
												class="btn btn-xs variant-soft-error cursor-pointer text-[11px] text-rose-500 hover:bg-rose-500/20"
												onclick={(e) => { e.stopPropagation(); deletingItem = item; deleteMessage = ''; }}
												title="Delete Evidence (Admin Action)"
											>
												<i class="fa-solid fa-trash"></i>
											</button>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>

<!-- New Custom Folder Modal -->
{#if showNewFolderModal}
	<div class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
		<div class="card p-6 bg-surface-50-950 border border-surface-200-800 max-w-md w-full space-y-4 shadow-xl">
			<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
				<h3 class="text-base font-bold text-surface-900-100 flex items-center gap-2">
					<i class="fa-solid fa-folder-plus text-primary-500"></i> Create Custom Subfolder
				</h3>
				<button class="text-surface-400 hover:text-surface-900 cursor-pointer" onclick={() => (showNewFolderModal = false)}>&times;</button>
			</div>

			<div class="space-y-2">
				<label class="text-xs font-semibold text-surface-700-300">Folder Name:</label>
				<input
					type="text"
					bind:value={customFolderName}
					placeholder="e.g. Audit Reports 2026, Vendor Certificates..."
					class="input text-xs p-2.5 bg-surface-100-900 border border-surface-200-800 rounded w-full"
				/>
			</div>

			<div class="flex justify-end gap-2 pt-2">
				<button class="btn btn-sm variant-soft-surface text-xs font-semibold" onclick={() => (showNewFolderModal = false)}>Cancel</button>
				<button
					class="btn btn-sm variant-filled-primary text-xs font-semibold"
					onclick={() => {
						showNewFolderModal = false;
						customFolderName = '';
					}}
				>
					Create Folder
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Version History Drawer/Modal -->
{#if versionHistoryItem}
	<div class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
		<div class="card p-6 bg-surface-50-950 border border-surface-200-800 max-w-lg w-full space-y-4 shadow-xl">
			<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
				<h3 class="text-base font-bold text-surface-900-100 flex items-center gap-2">
					<i class="fa-solid fa-clock-rotate-left text-primary-500"></i> Version History Log
				</h3>
				<button class="text-surface-400 hover:text-surface-900 cursor-pointer" onclick={() => (versionHistoryItem = null)}>&times;</button>
			</div>

			<div class="space-y-3 text-xs">
				<div class="p-3 bg-surface-100-900 rounded-lg space-y-1">
					<span class="font-bold text-surface-900-100 block">{versionHistoryItem.title}</span>
					<span class="text-surface-500 block">Control {versionHistoryItem.control?.ref_id} - {versionHistoryItem.control?.name}</span>
				</div>

				<div class="space-y-2 max-h-60 overflow-y-auto pr-1">
					<div class="p-3 rounded-lg border border-primary-500/30 bg-primary-500/5 space-y-1">
						<div class="flex items-center justify-between font-semibold">
							<span class="badge variant-filled-primary text-[10px]">Version v{versionHistoryItem.version || '1.0'} (Current)</span>
							<span class="text-[11px] text-surface-500">{versionHistoryItem.review_status}</span>
						</div>
						<p class="text-surface-600-400 pt-1">Submitted by SPOC: {versionHistoryItem.control?.spoc || 'System'}</p>
						{#if versionHistoryItem.reviewer_feedback}
							<p class="text-amber-500 italic">Reviewer Feedback: {versionHistoryItem.reviewer_feedback}</p>
						{/if}
						{#if versionHistoryItem.evidence_id}
							<div class="pt-2">
								<a href={getAttachmentDownloadUrl(versionHistoryItem.evidence_id)} target="_blank" class="btn btn-xs variant-soft-primary text-[11px] inline-flex items-center gap-1">
									<i class="fa-solid fa-download"></i> Download Version File
								</a>
							</div>
						{/if}
					</div>
				</div>
			</div>

			<div class="flex justify-end pt-2">
				<button class="btn btn-sm variant-soft-surface text-xs font-semibold" onclick={() => (versionHistoryItem = null)}>Close</button>
			</div>
		</div>
	</div>
{/if}

<!-- Delete Evidence Confirmation Modal -->
{#if deletingItem}
	<div class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
		<div class="card p-6 bg-surface-50-950 border border-surface-200-800 max-w-md w-full space-y-4 shadow-xl">
			<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
				<h3 class="text-base font-bold text-rose-500 flex items-center gap-2">
					<i class="fa-solid fa-triangle-exclamation"></i> Delete Evidence Document
				</h3>
				<button class="text-surface-400 hover:text-surface-900 cursor-pointer" onclick={() => (deletingItem = null)}>&times;</button>
			</div>

			<div class="space-y-3 text-xs">
				<p class="text-surface-700-300">
					Are you sure you want to delete evidence document <strong class="text-surface-900-100">'{deletingItem.title}'</strong> for control <span class="font-mono font-bold text-primary-500">{deletingItem.control?.ref_id}</span>?
				</p>
				<div class="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-500 text-[11px] space-y-1">
					<p class="font-bold"><i class="fa-solid fa-shield-halved me-1"></i> Audit Logging Notice:</p>
					<p>This action will be permanently recorded in the system audit log (actor, timestamp, evidence ID, and control reference).</p>
				</div>

				{#if deleteMessage}
					<div class="p-2.5 rounded text-[11px] font-bold {deleteMessage.includes('successfully') ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'}">
						{deleteMessage}
					</div>
				{/if}
			</div>

			<div class="flex justify-end gap-2 pt-2">
				<button class="btn btn-sm variant-soft-surface text-xs font-semibold" onclick={() => (deletingItem = null)} disabled={deleteSaving}>Cancel</button>
				<button
					class="btn btn-sm variant-filled-error text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700"
					onclick={handleDeleteEvidence}
					disabled={deleteSaving}
				>
					{deleteSaving ? 'Deleting & Logging...' : 'Confirm Delete'}
				</button>
			</div>
		</div>
	</div>
{/if}
