<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { goto, invalidateAll } from '$app/navigation';
	import { pageTitle } from '$lib/utils/stores';
	import type { PageData } from './$types';

	pageTitle.set('Control Assignments');

	let { data }: { data: PageData } = $props();

	let loading = $state(false);
	let frameworks = $state<any[]>(data?.frameworks || []);
	let selectedFrameworkId = $state<string>(data?.selectedFrameworkId || (data?.frameworks?.length ? data.frameworks[0].id : ''));
	let spocUsers = $state<any[]>(data?.spocUsers || []);
	let reviewerUsers = $state<any[]>(data?.reviewerUsers || []);
	let searchQuery = $state('');

	$effect(() => {
		const newFw = data?.frameworks || [];
		const newSpoc = data?.spocUsers || [];
		const newRev = data?.reviewerUsers || [];
		const defaultId = data?.selectedFrameworkId || (newFw.length > 0 ? newFw[0].id : '');

		untrack(() => {
			frameworks = newFw;
			spocUsers = newSpoc;
			reviewerUsers = newRev;
			if (!selectedFrameworkId && defaultId) {
				selectedFrameworkId = defaultId;
			}
		});
	});

	// Active editing modal state
	let editingControl = $state<any>(null);
	let editSpocId = $state('');
	let editReviewerId = $state('');
	let editDueDate = $state('');
	let editRequirements = $state<any[]>([]);
	let editNotes = $state('');
	let editIsNotApplicable = $state(false);
	let saving = $state(false);
	let saveMessage = $state('');

	// Bulk modal state
	let bulkModalOpen = $state(false);
	let selectedControlIds = $state<string[]>([]);
	let bulkSpocId = $state('');
	let bulkReviewerId = $state('');
	let bulkDueDate = $state('');
	let bulkSaving = $state(false);

	// SPOC Email Batching Settings inline state
	let batchWindowHours = $state(4);
	let batchSavingSettings = $state(false);
	let batchSettingsMessage = $state('');
	let showBatchSettings = $state(false);

	async function fetchBatchSettings() {
		try {
			const res = await fetch('/api/compliance/assignment-settings/');
			if (res.ok) {
				const data = await res.json();
				batchWindowHours = data.window_hours || 4;
			}
		} catch (e) {}
	}

	async function saveBatchSettings() {
		batchSavingSettings = true;
		batchSettingsMessage = '';
		try {
			const res = await fetch('/api/compliance/assignment-settings/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ window_hours: batchWindowHours })
			});
			if (res.ok) {
				const data = await res.json();
				batchWindowHours = data.window_hours;
				batchSettingsMessage = 'SPOC email batching window updated successfully!';
				setTimeout(() => (batchSettingsMessage = ''), 3000);
			} else {
				batchSettingsMessage = 'Failed to save batching settings.';
			}
		} catch (e) {
			batchSettingsMessage = 'Error saving batching settings.';
		} finally {
			batchSavingSettings = false;
		}
	}

	onMount(() => {
		fetchBatchSettings();
	});

	function onFrameworkChange() {
		if (selectedFrameworkId) {
			goto(`/control-assignments?framework_id=${selectedFrameworkId}`, { invalidateAll: true, keepFocus: true });
		}
	}

	function openEditModal(control: any) {
		editingControl = control;
		editSpocId = control.assignment?.spoc_user?.id || '';
		editReviewerId = control.assignment?.reviewer_user?.id || '';
		editDueDate = control.assignment?.due_date || '';
		editIsNotApplicable = Boolean(control.assignment?.is_not_applicable);
		editRequirements = control.assignment?.evidence_requirements
			? JSON.parse(JSON.stringify(control.assignment.evidence_requirements))
			: [];
		if (editRequirements.length === 0) {
			editRequirements.push({ name: 'Compliance Evidence Document', description: 'Primary evidence file', is_mandatory: true });
		}
		editNotes = '';
		saveMessage = '';
	}

	async function toggleNotApplicable(control: any) {
		const newStatus = !Boolean(control.assignment?.is_not_applicable);
		const formData = new FormData();
		formData.append('requirement_node_id', control.id);
		formData.append('framework_id', selectedFrameworkId || control.framework_id || '');
		formData.append('is_not_applicable', newStatus ? 'true' : 'false');

		try {
			const res = await fetch('?/toggleNA', {
				method: 'POST',
				body: formData
			});
			if (res.ok) {
				if (!control.assignment) {
					control.assignment = {};
				}
				control.assignment.is_not_applicable = newStatus;
				frameworks = [...frameworks];
				await invalidateAll();
			}
		} catch (err) {
			console.error('Failed to toggle N/A status:', err);
		}
	}

	function addRequirement() {
		editRequirements.push({ name: '', description: '', is_mandatory: true });
	}

	function removeRequirement(index: number) {
		editRequirements.splice(index, 1);
	}

	async function saveAssignment() {
		if (!editingControl) return;
		saving = true;
		saveMessage = '';

		const formData = new FormData();
		formData.append('requirement_node_id', editingControl.id);
		formData.append('framework_id', selectedFrameworkId || editingControl.framework_id || '');
		formData.append('spoc_user_id', editSpocId || '');
		formData.append('reviewer_user_id', editReviewerId || '');
		formData.append('due_date', editDueDate || '');
		formData.append('evidence_requirements', JSON.stringify(editRequirements));
		formData.append('notes', editNotes || '');
		formData.append('is_not_applicable', editIsNotApplicable ? 'true' : 'false');

		try {
			const res = await fetch('?/saveAssignment', {
				method: 'POST',
				body: formData
			});
			const result = await res.json();
			let dataResult = result;
			if (typeof result.data === 'string') {
				dataResult = JSON.parse(result.data);
			} else if (result.data) {
				dataResult = result.data;
			}

			if (dataResult.success || dataResult[0]?.success) {
				const spocObj = spocUsers.find((u) => u.id === editSpocId);
				const reviewerObj = reviewerUsers.find((u) => u.id === editReviewerId);

				editingControl.assignment = {
					id: dataResult.id || dataResult.data?.id || editingControl.assignment?.id || 'new',
					spoc_user: spocObj ? { id: spocObj.id, email: spocObj.email, first_name: spocObj.first_name, last_name: spocObj.last_name } : null,
					reviewer_user: reviewerObj ? { id: reviewerObj.id, email: reviewerObj.email, first_name: reviewerObj.first_name, last_name: reviewerObj.last_name } : null,
					evidence_requirements: editRequirements,
					notes: editNotes,
					is_not_applicable: editIsNotApplicable,
					is_active: true
				};

				frameworks = [...frameworks];
				saveMessage = 'Assignment saved successfully!';
				setTimeout(async () => {
					editingControl = null;
					await invalidateAll();
				}, 400);
			} else {
				saveMessage = dataResult.error || dataResult[0]?.error || 'Failed to save assignment.';
			}
		} catch (err: any) {
			saveMessage = err.message || 'Network error saving assignment.';
		} finally {
			saving = false;
		}
	}

	function toggleSelectAll(controls: any[]) {
		if (selectedControlIds.length === controls.length) {
			selectedControlIds = [];
		} else {
			selectedControlIds = controls.map((c) => c.id);
		}
	}

	function toggleSelectControl(id: string) {
		if (selectedControlIds.includes(id)) {
			selectedControlIds = selectedControlIds.filter((item) => item !== id);
		} else {
			selectedControlIds.push(id);
		}
	}

	async function executeBulkAssign() {
		if (selectedControlIds.length === 0) return;
		bulkSaving = true;

		const assignments = selectedControlIds.map((id) => ({
			requirement_node_id: id,
			framework_id: selectedFrameworkId,
			spoc_user_id: bulkSpocId || null,
			reviewer_user_id: bulkReviewerId || null,
			due_date: bulkDueDate || null,
		}));

		const formData = new FormData();
		formData.append('assignments', JSON.stringify(assignments));

		try {
			const res = await fetch('?/bulkAssign', {
				method: 'POST',
				body: formData
			});
			const result = await res.json();
			let dataResult = result;
			if (typeof result.data === 'string') {
				dataResult = JSON.parse(result.data);
			} else if (result.data) {
				dataResult = result.data;
			}

			if (dataResult.success || dataResult[0]?.success) {
				const spocObj = spocUsers.find((u) => u.id === bulkSpocId);
				const reviewerObj = reviewerUsers.find((u) => u.id === bulkReviewerId);

				for (const fw of frameworks) {
					for (const c of fw.controls || []) {
						if (selectedControlIds.includes(c.id)) {
							c.assignment = {
								id: c.assignment?.id || 'bulk',
								spoc_user: spocObj ? { id: spocObj.id, email: spocObj.email, first_name: spocObj.first_name, last_name: spocObj.last_name } : null,
								reviewer_user: reviewerObj ? { id: reviewerObj.id, email: reviewerObj.email, first_name: reviewerObj.first_name, last_name: reviewerObj.last_name } : null,
								is_active: true
							};
						}
					}
				}

				frameworks = [...frameworks];
				bulkModalOpen = false;
				selectedControlIds = [];
				await invalidateAll();
			} else {
				alert(dataResult.error || dataResult[0]?.error || 'Bulk assignment failed.');
			}
		} catch (err: any) {
			alert(err.message || 'Network error executing bulk assignment.');
		} finally {
			bulkSaving = false;
		}
	}

	let hideFullyAssigned = $state(false);

	function formatUserDisplayName(user: any) {
		if (!user) return 'Unassigned';
		const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
		const desig = user.designation ? String(user.designation).trim() : '';
		if (name && desig) return `${name} - ${desig}`;
		if (name) return name;
		if (user.email && desig) return `${user.email} - ${desig}`;
		return user.email || 'Unassigned';
	}

	const activeFramework = $derived(
		frameworks.find((f) => f.id === selectedFrameworkId) || (frameworks.length > 0 ? frameworks[0] : null)
	);

	const filteredControls = $derived(
		activeFramework
			? activeFramework.controls.filter((c: any) => {
					const matchesSearch =
						c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
						c.ref_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
						(c.domain_name && c.domain_name.toLowerCase().includes(searchQuery.toLowerCase()));
					const isFullyAssigned = Boolean(c.assignment?.spoc_user && c.assignment?.reviewer_user);
					if (hideFullyAssigned && isFullyAssigned) return false;
					return matchesSearch;
			  })
			: []
	);
</script>

<div class="p-6 space-y-6">
	<!-- Top Navigation Actions -->
	<div class="flex flex-wrap items-center justify-between gap-4 bg-surface-100-900/60 p-4 rounded-xl border border-surface-200-800">
		<div class="flex items-center gap-3">
			<a
				href="/control-assignments"
				class="px-4 py-2 rounded-lg bg-primary-500 text-white font-semibold text-sm shadow-xs flex items-center gap-2"
			>
				<i class="fa-solid fa-list-check"></i>
				<span>Control Assignments</span>
			</a>
			<a
				href="/control-assignments/submit"
				class="px-4 py-2 rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-700-300 hover:bg-surface-200-800 text-sm font-medium transition-all flex items-center gap-2"
			>
				<i class="fa-solid fa-cloud-arrow-up text-amber-500"></i>
				<span>SPOC Submission</span>
			</a>
			<a
				href="/control-assignments/review"
				class="px-4 py-2 rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-700-300 hover:bg-surface-200-800 text-sm font-medium transition-all flex items-center gap-2"
			>
				<i class="fa-solid fa-clipboard-check text-emerald-500"></i>
				<span>Reviewer Approval</span>
			</a>
			<button
				onclick={() => (showBatchSettings = !showBatchSettings)}
				class="px-4 py-2 rounded-lg border text-sm transition-all flex items-center gap-2 cursor-pointer {showBatchSettings ? 'bg-primary-500 text-white font-semibold shadow-xs border-primary-500' : 'border-surface-200-800 bg-surface-50-950 text-surface-700-300 hover:bg-surface-200-800 font-medium'}"
			>
				<i class="fa-solid fa-clock-rotate-left"></i>
				<span>Configure Email Batching ({batchWindowHours}h)</span>
			</button>
		</div>

		{#if selectedControlIds.length > 0}
			<button
				onclick={() => (bulkModalOpen = true)}
				class="px-4 py-2 rounded-lg bg-emerald-600 text-white font-medium text-sm shadow-xs hover:bg-emerald-700 transition-all flex items-center gap-2 cursor-pointer"
			>
				<i class="fa-solid fa-users-gear"></i>
				<span>Bulk Assign ({selectedControlIds.length} controls)</span>
			</button>
		{/if}
	</div>

	<!-- Inline Batching Settings Panel -->
	{#if showBatchSettings}
		<div class="p-5 rounded-2xl border border-surface-200-800 bg-surface-50-950 shadow-md space-y-4">
			<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
				<div>
					<h4 class="font-bold text-sm text-surface-900-100 flex items-center gap-2">
						<i class="fa-solid fa-clock-rotate-left text-primary-500"></i>
						<span>SPOC Email Assignment Consolidation Settings</span>
					</h4>
					<p class="text-xs text-surface-500 mt-0.5">
						Configure the batching window timeframe for bundling multiple control assignments assigned to the same SPOC into a single consolidated email.
					</p>
				</div>
				<button onclick={() => (showBatchSettings = false)} class="text-surface-400 hover:text-surface-900-100">
					<i class="fa-solid fa-xmark"></i>
				</button>
			</div>

			{#if batchSettingsMessage}
				<div class="text-xs p-3 rounded-xl font-semibold border bg-emerald-500/10 text-emerald-500 border-emerald-500/20">
					{batchSettingsMessage}
				</div>
			{/if}

			<div class="flex items-center gap-4 max-w-md">
				<div class="flex-1 space-y-1">
					<label class="text-xs font-semibold text-surface-700-300" for="inline-batch-window">Consolidation Window (Hours):</label>
					<input
						id="inline-batch-window"
						type="number"
						min="1"
						max="168"
						bind:value={batchWindowHours}
						class="w-full px-3 py-1.5 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 font-semibold"
					/>
				</div>
				<button
					onclick={saveBatchSettings}
					disabled={batchSavingSettings}
					class="mt-5 px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-semibold shadow-xs disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
				>
					{#if batchSavingSettings}<i class="fa-solid fa-spinner fa-spin text-[10px]"></i>{/if}
					<span>Save Settings</span>
				</button>
			</div>
		</div>
	{/if}

	<!-- Controls Header & Filter -->
	<div class="flex flex-wrap items-center justify-between gap-4">
		<div class="flex items-center gap-4">
			<label class="text-sm font-semibold text-surface-700-300">Framework:</label>
			<select
				bind:value={selectedFrameworkId}
				onchange={onFrameworkChange}
				class="px-3 py-2 rounded-lg border border-surface-200-800 bg-surface-50-950 text-sm font-medium text-surface-900-100 min-w-64"
			>
				{#each frameworks as fw}
					<option value={fw.id}>{fw.name} ({fw.controls_count} controls)</option>
				{/each}
			</select>
		</div>

		<div class="flex items-center gap-3">
			<label class="flex items-center gap-2 text-xs font-semibold text-surface-700-300 cursor-pointer bg-surface-100-900 px-3.5 py-2 rounded-lg border border-surface-200-800 shadow-xs hover:border-primary-500/50 transition-colors">
				<input type="checkbox" bind:checked={hideFullyAssigned} class="rounded border-surface-300 text-primary-600 focus:ring-primary-500" />
				<span>Hide Fully Assigned Controls</span>
			</label>
			<div class="relative w-72">
				<input
					type="text"
					placeholder="Search controls..."
					bind:value={searchQuery}
					class="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100 placeholder-surface-400"
				/>
				<i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-surface-400"></i>
			</div>
		</div>
	</div>

	<!-- Controls Table -->
	{#if loading}
		<div class="p-12 text-center text-surface-500 font-medium">Extracting framework controls from library...</div>
	{:else if !activeFramework || filteredControls.length === 0}
		<div class="p-12 text-center border border-dashed border-surface-300-700 rounded-xl text-surface-500">
			No controls found for this framework.
		</div>
	{:else}
		<div class="border border-surface-200-800 rounded-xl overflow-x-auto bg-surface-50-950 shadow-xs relative">
			<table class="w-full text-left text-sm table-auto border-collapse">
				<thead class="bg-surface-100-900 border-b border-surface-200-800 text-xs font-semibold text-surface-600-400 uppercase tracking-wider">
					<tr>
						<th class="p-3.5 w-10 text-center">
							<input
								type="checkbox"
								checked={selectedControlIds.length === filteredControls.length && filteredControls.length > 0}
								onchange={() => toggleSelectAll(filteredControls)}
								class="rounded border-surface-300 text-primary-600 focus:ring-primary-500"
							/>
						</th>
						<th class="p-3.5 w-20">Ref ID</th>
						<th class="p-3.5 w-44">Domain Name</th>
						<th class="p-3.5 min-w-44">Control Name</th>
						<th class="p-3.5 w-44">Assigned SPOC (User)</th>
						<th class="p-3.5 w-44">Assigned Reviewer (Admin)</th>
						<th class="p-3.5 w-24 text-center">Requirements</th>
						<th class="p-3.5 w-48 text-right pr-4 sticky right-0 z-20 bg-surface-100-900 border-l border-surface-200-800 shadow-md">Action</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-surface-200-800/50">
					{#each filteredControls as control}
						<tr class="hover:bg-surface-100-900/40 transition-colors group">
							<td class="p-3.5 text-center">
								<input
									type="checkbox"
									checked={selectedControlIds.includes(control.id)}
									onchange={() => toggleSelectControl(control.id)}
									class="rounded border-surface-300 text-primary-600 focus:ring-primary-500"
								/>
							</td>
							<td class="p-3.5 font-mono text-xs font-bold text-primary-500 whitespace-nowrap">{control.ref_id}</td>
							<td class="p-3.5 text-xs font-semibold text-secondary-500 max-w-44" title={control.domain_name || 'General'}>
								<span class="inline-flex items-center gap-1.5 bg-secondary-500/10 text-secondary-400 px-2.5 py-1 rounded-md border border-secondary-500/20 max-w-full truncate">
									<i class="fa-solid fa-folder-tree text-[10px] shrink-0"></i>
									<span class="truncate">{control.domain_name || 'General'}</span>
								</span>
							</td>
							<td class="p-3.5 font-medium text-surface-900-100 max-w-xs truncate" title={control.name}>
								{control.name}
							</td>
							<td class="p-3.5 max-w-44">
								{#if control.assignment?.is_not_applicable}
									<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-500/10 text-slate-400 text-xs font-semibold border border-slate-500/20 truncate">
										<i class="fa-solid fa-ban text-[10px] shrink-0"></i> <span class="truncate">Not Applicable</span>
									</span>
								{:else if control.assignment?.spoc_user}
									<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-600 text-xs font-medium border border-blue-500/20 max-w-full truncate" title={formatUserDisplayName(control.assignment.spoc_user)}>
										<i class="fa-solid fa-user text-[10px] shrink-0"></i>
										<span class="truncate">{formatUserDisplayName(control.assignment.spoc_user)}</span>
									</span>
								{:else}
									<span class="text-xs text-surface-400 italic">Unassigned</span>
								{/if}
							</td>
							<td class="p-3.5 max-w-44">
								{#if control.assignment?.reviewer_user}
									<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-600 text-xs font-medium border border-purple-500/20 max-w-full truncate" title={formatUserDisplayName(control.assignment.reviewer_user)}>
										<i class="fa-solid fa-user-shield text-[10px] shrink-0"></i>
										<span class="truncate">{formatUserDisplayName(control.assignment.reviewer_user)}</span>
									</span>
								{:else}
									<span class="text-xs text-surface-400 italic">Unassigned</span>
								{/if}
							</td>
							<td class="p-3.5 text-center whitespace-nowrap">
								<span class="px-2 py-0.5 rounded-full bg-surface-200-800 text-xs font-medium">
									{control.assignment?.evidence_requirements?.length || 0} reqs
								</span>
							</td>
							<td class="p-3.5 text-right space-x-1.5 whitespace-nowrap pr-4 sticky right-0 z-10 bg-surface-50-950 group-hover:bg-surface-100-900 border-l border-surface-200-800 shadow-md">
								<button
									onclick={() => openEditModal(control)}
									class="px-3 py-1.5 rounded-lg bg-primary-500 hover:bg-primary-600 text-white font-semibold text-xs shadow-xs transition-all cursor-pointer"
								>
									Assign
								</button>
								<button
									onclick={() => toggleNotApplicable(control)}
									class="px-2.5 py-1.5 rounded-lg border border-slate-600/40 bg-slate-800/40 text-xs font-medium {control.assignment?.is_not_applicable ? 'text-amber-400 border-amber-500/40 hover:bg-amber-500/20' : 'text-slate-400 hover:bg-slate-700 hover:text-white'} transition-all cursor-pointer"
									title={control.assignment?.is_not_applicable ? 'Set Control as Applicable' : 'Set Control as Not Applicable'}
								>
									{control.assignment?.is_not_applicable ? 'Set Applicable' : 'Set N/A'}
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<!-- Edit Modal -->
	{#if editingControl}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
			<div class="w-full max-w-2xl bg-surface-50-950 rounded-2xl border border-surface-200-800 shadow-2xl p-6 space-y-5 max-h-[90vh] overflow-y-auto">
				<div class="flex items-start justify-between border-b border-surface-200-800 pb-3 gap-4">
					<div class="space-y-1 max-w-xl">
						<div class="flex items-center gap-2.5 flex-wrap">
							<h3 class="text-lg font-bold text-surface-900-100">
								Assign Control: <span class="text-primary-500">{editingControl.ref_id}</span>
							</h3>
							{#if editingControl.domain_name}
								<span class="inline-flex items-center gap-1 bg-secondary-500/10 text-secondary-400 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-secondary-500/30">
									<i class="fa-solid fa-folder-tree text-[10px]"></i>
									Domain: {editingControl.domain_name}
								</span>
							{/if}
						</div>
						<p class="text-sm font-semibold text-surface-800-200">{editingControl.name}</p>
						{#if editingControl.description}
							<div class="text-xs text-surface-400 bg-surface-100-900/60 p-2.5 rounded-lg border border-surface-200-800/60 max-h-28 overflow-y-auto leading-relaxed">
								<span class="font-medium text-surface-600-400 block mb-0.5">Control Description:</span>
								{editingControl.description}
							</div>
						{/if}
					</div>
					<button onclick={() => (editingControl = null)} class="text-surface-400 hover:text-surface-900-100 mt-1">
						<i class="fa-solid fa-xmark text-lg"></i>
					</button>
				</div>

				<div class="p-3 rounded-xl bg-slate-900/50 border border-slate-800">
					<label class="flex items-center gap-2.5 text-xs font-semibold text-slate-300 cursor-pointer">
						<input type="checkbox" bind:checked={editIsNotApplicable} class="rounded border-slate-600 text-amber-500 focus:ring-amber-500 w-4 h-4" />
						<span>Mark Control as Not Applicable (N/A) for this Framework</span>
					</label>
				</div>

				<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
					<!-- SPOC Selector -->
					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">SPOC (1 Person - Submitter):</label>
						<select
							bind:value={editSpocId}
							class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						>
							<option value="">-- Unassigned --</option>
							{#each spocUsers as user}
								<option value={user.id}>{formatUserDisplayName(user)}</option>
							{/each}
						</select>
					</div>

					<!-- Reviewer Selector -->
					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">Reviewer (1 Person - Approver):</label>
						<select
							bind:value={editReviewerId}
							class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						>
							<option value="">-- Unassigned --</option>
							{#each reviewerUsers as user}
								<option value={user.id}>{formatUserDisplayName(user)}</option>
							{/each}
						</select>
					</div>

					<!-- Evidence Due Date -->
					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">Evidence Due Date:</label>
						<input
							type="date"
							bind:value={editDueDate}
							class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						/>
					</div>
				</div>

				<!-- Evidence Requirements Section -->
				<div class="space-y-3 pt-2">
					<div class="flex items-center justify-between">
						<label class="text-xs font-bold text-surface-700-300 uppercase tracking-wider">Required Evidences:</label>
						<button
							type="button"
							onclick={addRequirement}
							class="text-xs text-primary-500 hover:underline font-semibold flex items-center gap-1 cursor-pointer"
						>
							<i class="fa-solid fa-plus text-[10px]"></i> Add Requirement
						</button>
					</div>

					<div class="space-y-2.5">
						{#each editRequirements as req, idx}
							<div class="p-3 rounded-xl border border-surface-200-800 bg-surface-100-900/60 space-y-2">
								<div class="flex items-center gap-2">
									<input
										type="text"
										placeholder="Evidence Title / Requirement Name (e.g. Access Control Log)"
										bind:value={req.name}
										class="flex-1 px-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100 font-semibold"
									/>
									<label class="flex items-center gap-1.5 text-xs text-surface-700-300 cursor-pointer">
										<input type="checkbox" bind:checked={req.is_mandatory} class="rounded text-primary-600" />
										<span>Mandatory</span>
									</label>
									<button
										type="button"
										onclick={() => removeRequirement(idx)}
										class="p-1.5 text-surface-400 hover:text-rose-500 transition-colors cursor-pointer"
										title="Remove requirement"
									>
										<i class="fa-solid fa-trash-can text-xs"></i>
									</button>
								</div>
								<input
									type="text"
									placeholder="Evidence Description / SPOC Instructions (e.g. Upload quarterly firewall log export PDF)"
									bind:value={req.description}
									class="w-full px-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100 placeholder-surface-400 font-medium"
								/>
							</div>
						{/each}
					</div>
				</div>

				{#if saveMessage}
					<div class="text-xs p-2.5 rounded-lg font-medium {saveMessage.includes('success') ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'}">
						{saveMessage}
					</div>
				{/if}

				<div class="flex items-center justify-end gap-3 pt-3 border-t border-surface-200-800">
					<button
						onclick={() => (editingControl = null)}
						class="px-4 py-2 text-xs font-medium rounded-lg border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800"
					>
						Cancel
					</button>
					<button
						onclick={saveAssignment}
						disabled={saving}
						class="px-5 py-2 text-xs font-semibold rounded-lg bg-primary-500 text-white shadow-xs hover:bg-primary-600 disabled:opacity-50"
					>
						{saving ? 'Saving...' : 'Save Assignment'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Bulk Assign Modal -->
	{#if bulkModalOpen}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
			<div class="w-full max-w-md bg-surface-50-950 rounded-2xl border border-surface-200-800 shadow-2xl p-6 space-y-5">
				<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
					<h3 class="text-lg font-bold text-surface-900-100">
						Bulk Assign ({selectedControlIds.length} controls)
					</h3>
					<button onclick={() => (bulkModalOpen = false)} class="text-surface-400 hover:text-surface-900-100">
						<i class="fa-solid fa-xmark text-lg"></i>
					</button>
				</div>

				<div class="space-y-4">
					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">Assign SPOC (User):</label>
						<select
							bind:value={bulkSpocId}
							class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						>
							<option value="">-- Unassigned --</option>
							{#each spocUsers as user}
								<option value={user.id}>{formatUserDisplayName(user)}</option>
							{/each}
						</select>
					</div>

					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">Assign Reviewer (Admin):</label>
						<select
							bind:value={bulkReviewerId}
							class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						>
							<option value="">-- Unassigned --</option>
							{#each reviewerUsers as user}
								<option value={user.id}>{formatUserDisplayName(user)}</option>
							{/each}
						</select>
					</div>

					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">Evidence Submission Due Date:</label>
						<input
							type="date"
							bind:value={bulkDueDate}
							class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						/>
					</div>
				</div>

				<div class="flex items-center justify-end gap-3 pt-3 border-t border-surface-200-800">
					<button
						onclick={() => (bulkModalOpen = false)}
						class="px-4 py-2 text-xs font-medium rounded-lg border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800"
					>
						Cancel
					</button>
					<button
						onclick={executeBulkAssign}
						disabled={bulkSaving}
						class="px-5 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white shadow-xs hover:bg-emerald-700 disabled:opacity-50"
					>
						{bulkSaving ? 'Assigning...' : 'Apply Bulk Assignment'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Batch Settings Modal -->
	{#if showBatchSettings}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
			<div class="w-full max-w-lg bg-surface-50-950 rounded-2xl border border-surface-200-800 shadow-2xl p-6 space-y-5">
				<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
					<h3 class="text-base font-bold text-surface-900-100 flex items-center gap-2">
						<i class="fa-solid fa-clock-rotate-left text-primary-500"></i>
						<span>SPOC Email Batching Settings</span>
					</h3>
					<button onclick={() => (showBatchSettings = false)} class="text-surface-400 hover:text-surface-900-100">
						<i class="fa-solid fa-xmark text-lg"></i>
					</button>
				</div>

				{#if batchSettingsMessage}
					<div class="p-3 rounded-lg border bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs font-semibold">
						{batchSettingsMessage}
					</div>
				{/if}

				<div class="space-y-3">
					<label class="text-xs font-semibold text-surface-800-200 block" for="modal-window-input">
						Assignment Consolidation Time Frame (Hours)
					</label>
					<div class="flex items-center gap-3">
						<input
							id="modal-window-input"
							type="number"
							min="1"
							max="168"
							class="w-32 px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 font-mono font-bold"
							bind:value={batchWindowHours}
						/>
						<span class="text-xs text-surface-500 font-medium">Hours</span>
					</div>
					<p class="text-xs text-surface-400 leading-relaxed">
						When controls are assigned to a SPOC, a batching window starts. All controls assigned within this timeframe will be bundled together and sent as a single email digest when the window expires (Default: 4 hours).
					</p>
				</div>

				<div class="flex items-center justify-end gap-3 pt-3 border-t border-surface-200-800">
					<button
						onclick={() => (showBatchSettings = false)}
						class="px-4 py-2 text-xs font-medium rounded-lg border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800"
					>
						Close
					</button>
					<button
						onclick={saveBatchSettings}
						disabled={batchSavingSettings}
						class="px-5 py-2 text-xs font-semibold rounded-lg bg-primary-500 text-white shadow-xs hover:bg-primary-600 disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
					>
						{#if batchSavingSettings}
							<i class="fa-solid fa-spinner fa-spin text-xs"></i>
						{:else}
							<i class="fa-solid fa-check text-xs"></i>
						{/if}
						<span>Save Batching Settings</span>
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

