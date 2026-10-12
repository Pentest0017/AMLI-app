<script lang="ts">
	import AutocompleteSelect from '../AutocompleteSelect.svelte';
	import Select from '../Select.svelte';
	import TextField from '$lib/components/Forms/TextField.svelte';
	import type { SuperForm } from 'sveltekit-superforms';
	import type { ModelInfo, CacheLock } from '$lib/utils/types';
	import * as m from '$paraglide/messages';
	import Dropdown from '$lib/components/Dropdown/Dropdown.svelte';
	import FrameworkResultSnippet from '$lib/components/Snippets/AutocompleteSelect/FrameworkResultSnippet.svelte';
	import { getCookie } from '$lib/utils/cookies';

	interface Props {
		form: SuperForm<any>;
		model: ModelInfo;
		cacheLocks?: Record<string, CacheLock>;
		formDataCache?: Record<string, any>;
		initialData?: Record<string, any>;
		object?: any;
		context: string;
	}

	let {
		form,
		model = $bindable(),
		cacheLocks = {},
		formDataCache = $bindable({}),
		initialData = {},
		object = {},
		context
	}: Props = $props();

	const formData = form.form;

	let suggestions = $state(false);
	let implementationGroupsChoices = $state<{ label: string; value: string }[]>([]);
	let defaultImplementationGroups: string[] = $state([]);
	let is_dynamic = $state(false);

	let currentScopeMode = $derived($formData.scope_mode || 'full');

	let auditPeriodStartDate = $state('');
	let auditPeriodEndDate = $state('');

	function formatDateString(dStr: string) {
		if (!dStr) return '';
		const parts = dStr.split('-');
		if (parts.length === 3) {
			const year = parts[0];
			const month = parseInt(parts[1], 10) - 1;
			const day = parseInt(parts[2], 10);
			const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
			if (month >= 0 && month < 12) {
				return `${monthNames[month]} ${day}, ${year}`;
			}
		}
		return dStr;
	}

	function handlePeriodDateChange() {
		if (auditPeriodStartDate && auditPeriodEndDate) {
			$formData.audit_period_year = `${formatDateString(auditPeriodStartDate)} - ${formatDateString(auditPeriodEndDate)}`;
		} else if (auditPeriodStartDate) {
			$formData.audit_period_year = formatDateString(auditPeriodStartDate);
		}
	}

	// Scope Picker Modal state
	let isScopeModalOpen = $state(false);
	let isLoadingLibrary = $state(false);
	let modalSearchQuery = $state('');

	type ControlItem = {
		id: string;
		name: string;
		ref_id: string;
		domainName: string;
		frameworkName: string;
		frameworkId: string;
	};
	type DomainItem = { urn: string; name: string; controls: ControlItem[] };
	type FrameworkTree = { id: string; name: string; domains: DomainItem[] };

	let frameworksList = $state<FrameworkTree[]>([]);
	let allControlsList = $state<ControlItem[]>([]);
	let expandedFrameworkIds = $state<Set<string>>(new Set());
	let expandedDomainUrns = $state<Set<string>>(new Set());
	let selectedControlIds = $state<Set<string>>(new Set());

	// Initialize selectedControlIds from form state and auto-load tree on custom scope mode
	$effect(() => {
		if (!$formData.scope_mode) {
			form.form.update((d) => ({ ...d, scope_mode: 'full' }));
		}
	});

	$effect(() => {
		if ($formData.selected_nodes && Array.isArray($formData.selected_nodes)) {
			selectedControlIds = new Set($formData.selected_nodes);
		}
	});

	$effect(() => {
		if (currentScopeMode === 'custom') {
			loadLibraryData();
		}
	});

	function syncSelectedNodesToForm(newSelection: Set<string>) {
		selectedControlIds = newSelection;
		const arr = Array.from(newSelection);
		form.form.update((d) => ({
			...d,
			selected_nodes: arr
		}));
	}

	function setIndeterminate(node: HTMLInputElement, isIndeterminate: boolean) {
		node.indeterminate = isIndeterminate;
		return {
			update(newIndeterminate: boolean) {
				node.indeterminate = newIndeterminate;
			}
		};
	}

	async function loadLibraryData(forceReload = false) {
		if (frameworksList.length > 0 && !forceReload) return; // already loaded

		isLoadingLibrary = true;
		try {
			let res = await fetch('/requirement-nodes/tree/', {
				headers: { Accept: 'application/json' }
			});
			if (res.ok) {
				const data = await res.json();
				const treeList: FrameworkTree[] = data.results || [];
				const flatControls: ControlItem[] = treeList.flatMap((fw) =>
					fw.domains.flatMap((d) => d.controls)
				);

				frameworksList = treeList;
				allControlsList = flatControls;
				return;
			} else {
				console.error('Failed to load requirement nodes tree endpoint:', res.status, res.statusText);
			}
		} catch (err) {
			console.error('Failed to load library data for scope:', err);
		} finally {
			isLoadingLibrary = false;
		}
	}

	async function openScopeModal() {
		isScopeModalOpen = true;
		await loadLibraryData();
	}

	function toggleFrameworkExpand(id: string) {
		const next = new Set(expandedFrameworkIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		expandedFrameworkIds = next;
	}

	function toggleDomainExpand(urn: string) {
		const next = new Set(expandedDomainUrns);
		if (next.has(urn)) {
			next.delete(urn);
		} else {
			next.add(urn);
		}
		expandedDomainUrns = next;
	}

	function expandAll() {
		expandedFrameworkIds = new Set(frameworksList.map((f) => f.id));
		expandedDomainUrns = new Set(frameworksList.flatMap((f) => f.domains.map((d) => d.urn)));
	}

	function collapseAll() {
		expandedFrameworkIds = new Set();
		expandedDomainUrns = new Set();
	}

	function toggleControlSelection(id: string) {
		const next = new Set(selectedControlIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		syncSelectedNodesToForm(next);
	}

	function getDomainSelectionState(dom: DomainItem) {
		const domCtrlIds = dom.controls.map((c) => c.id);
		const count = domCtrlIds.filter((id) => selectedControlIds.has(id)).length;
		const total = domCtrlIds.length;
		return {
			checked: total > 0 && count === total,
			indeterminate: count > 0 && count < total,
			count,
			total
		};
	}

	function toggleDomainSelection(dom: DomainItem) {
		const domCtrlIds = dom.controls.map((c) => c.id);
		const allSelected = domCtrlIds.every((id) => selectedControlIds.has(id));
		const next = new Set(selectedControlIds);
		if (allSelected) {
			domCtrlIds.forEach((id) => next.delete(id));
		} else {
			domCtrlIds.forEach((id) => next.add(id));
		}
		syncSelectedNodesToForm(next);
	}

	function getFrameworkSelectionState(fw: FrameworkTree) {
		const fwCtrlIds = fw.domains.flatMap((d) => d.controls).map((c) => c.id);
		const count = fwCtrlIds.filter((id) => selectedControlIds.has(id)).length;
		const total = fwCtrlIds.length;
		return {
			checked: total > 0 && count === total,
			indeterminate: count > 0 && count < total,
			count,
			total
		};
	}

	function toggleFrameworkSelection(fw: FrameworkTree) {
		const fwCtrlIds = fw.domains.flatMap((d) => d.controls).map((c) => c.id);
		const allSelected = fwCtrlIds.every((id) => selectedControlIds.has(id));
		const next = new Set(selectedControlIds);
		if (allSelected) {
			fwCtrlIds.forEach((id) => next.delete(id));
		} else {
			fwCtrlIds.forEach((id) => next.add(id));
		}
		syncSelectedNodesToForm(next);
	}

	function applyScopeSelection() {
		syncSelectedNodesToForm(selectedControlIds);
		isScopeModalOpen = false;
	}

	let searchResults = $derived.by(() => {
		const q = modalSearchQuery.trim().toLowerCase();
		if (!q) return [];
		return allControlsList.filter(
			(c) =>
				c.name.toLowerCase().includes(q) ||
				c.ref_id.toLowerCase().includes(q) ||
				c.domainName.toLowerCase().includes(q) ||
				c.frameworkName.toLowerCase().includes(q)
		);
	});

	async function handleFrameworkChange(id: string) {
		if (id) {
			await fetch(`/frameworks/${id}`)
				.then((r) => r.json())
				.then((r) => {
					is_dynamic = r['is_dynamic'] || false;
					const implementation_groups = r['implementation_groups_definition'] || [];
					implementationGroupsChoices = implementation_groups.map((group) => ({
						label: group.name,
						value: group.ref_id
					}));
					suggestions = r['reference_controls']?.length > 0;

					defaultImplementationGroups = implementation_groups
						.filter((group) => group.default_selected)
						.map((group) => group.ref_id);

					if (!object.id) {
						form.form.update((currentData) => ({
							...currentData,
							selected_implementation_groups: defaultImplementationGroups
						}));
					}
				});
		}
	}
</script>

{#if (context === 'fromBaseline' || context === 'clone') && initialData.baseline}
	<AutocompleteSelect
		{form}
		field="baseline"
		cacheLock={cacheLocks['baseline']}
		bind:cachedValue={formDataCache['baseline']}
		label={m.baseline()}
		optionsEndpoint="compliance-assessments"
		hidden
	/>
{/if}
{#if initialData.ebios_rm_studies}
	<AutocompleteSelect
		{form}
		field="ebios_rm_studies"
		multiple
		cacheLock={cacheLocks['ebios_rm_studies']}
		bind:cachedValue={formDataCache['ebios_rm_studies']}
		label={m.ebiosRmStudies()}
		hidden
	/>
{/if}

<!-- Audit Scope Selection: Full Framework vs Custom Scope -->
<Select
	{form}
	options={[
		{ label: 'Full Framework Scope', value: 'full' },
		{ label: 'Custom Scope (Select Specific Domains & Controls)', value: 'custom' }
	]}
	field="scope_mode"
	label="Audit Scope Selection"
	helpText="Select full framework scope or custom select specific domains and controls."
	disableDoubleDash
	onChange={(e: any) => {
		const val = typeof e === 'string' ? e : e?.target?.value;
		const newMode = val === 'custom' ? 'custom' : 'full';
		if (newMode === 'custom') {
			form.form.update((d) => ({ ...d, scope_mode: 'custom', framework: null }));
			loadLibraryData();
		} else {
			syncSelectedNodesToForm(new Set());
			form.form.update((d) => ({ ...d, scope_mode: 'full', selected_nodes: [] }));
		}
	}}
/>

{#if currentScopeMode !== 'custom'}
	{#if context === 'fromBaseline' && initialData.baseline}
		<AutocompleteSelect
			{form}
			disabled={object.id}
			optionsEndpoint="compliance-assessments/{page.params.id}/frameworks"
			field="framework"
			cacheLock={cacheLocks['framework']}
			optionsLabelField="str"
			optionsValueField="id"
			bind:cachedValue={formDataCache['framework']}
			label={m.targetFramework()}
			onChange={async (e) => handleFrameworkChange(e)}
			mount={async (e) => handleFrameworkChange(e)}
			additionalMultiselectOptions={{
				liOptionClass: 'flex items-center w-full border-t-8 border-b-8 border-transparent'
			}}
			includeAllOptionFields
		>
			{#snippet optionSnippet(option: Record)}
				<FrameworkResultSnippet {option} />
			{/snippet}
		</AutocompleteSelect>
	{:else}
		<AutocompleteSelect
			{form}
			disabled={object.id || context === 'clone'}
			optionsEndpoint="frameworks"
			optionsDetailedUrlParameters={context === 'fromBaseline'
				? [['baseline', initialData.baseline]]
				: []}
			field="framework"
			cacheLock={cacheLocks['framework']}
			optionsLabelField="name"
			optionsValueField="id"
			bind:cachedValue={formDataCache['framework']}
			label={context === 'clone' ? m.framework() : m.targetFramework()}
			onChange={async (e) => handleFrameworkChange(e)}
			mount={async (e) => handleFrameworkChange(e)}
		/>
	{/if}
{/if}

{#if currentScopeMode === 'custom'}
	<div class="p-4 border border-primary-500/40 rounded-xl bg-surface-50 dark:bg-surface-800 space-y-4 my-4 shadow-md">
		<div class="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-surface-200 dark:border-surface-700">
			<div>
				<h4 class="text-base font-bold text-primary-500 flex items-center gap-2">
					<i class="fa-solid fa-list-check"></i>
					<span>Custom Audit Scope & Controls Selector</span>
				</h4>
				<p class="text-xs text-surface-500">
					Select specific domains or controls across stored checklists for this assessment.
				</p>
			</div>
			<div class="flex items-center gap-2">
				<span class="badge variant-filled-primary font-semibold text-xs px-3 py-1">
					{selectedControlIds.size} Controls Selected
				</span>
				<button
					type="button"
					class="btn variant-soft text-xs px-2.5 py-1"
					onclick={expandAll}
				>
					<i class="fa-solid fa-folder-open text-xs mr-1"></i>
					<span>Expand All</span>
				</button>
				<button
					type="button"
					class="btn variant-soft text-xs px-2.5 py-1"
					onclick={collapseAll}
				>
					<i class="fa-solid fa-folder text-xs mr-1"></i>
					<span>Collapse All</span>
				</button>
				<button
					type="button"
					class="btn variant-soft-primary text-xs px-3 py-1.5 flex items-center gap-1.5"
					onclick={openScopeModal}
				>
					<i class="fa-solid fa-expand"></i>
					<span>Open Fullscreen Selector</span>
				</button>
			</div>
		</div>

		<!-- Search Bar -->
		<div class="relative">
			<i class="fa-solid fa-magnifying-glass absolute left-3 top-3 text-surface-400"></i>
			<input
				type="text"
				bind:value={modalSearchQuery}
				placeholder="Search controls by ID (e.g. DOM-16, A.5.16, 6.1.1) or control name across all stored checklists..."
				class="input pl-10 pr-4 py-2 text-sm rounded-lg border-surface-300 dark:border-surface-600 bg-surface-100 dark:bg-surface-900 w-full"
			/>
		</div>

		<!-- Inline Tree View -->
		{#if isLoadingLibrary}
			<div class="flex items-center justify-center py-10 text-surface-500 gap-3">
				<i class="fa-solid fa-spinner fa-spin text-xl text-primary-500"></i>
				<span class="text-sm font-medium">Loading library checklists, domains, and controls...</span>
			</div>
		{:else if searchResults.length > 0}
			<div class="max-h-96 overflow-y-auto space-y-2 p-2 bg-surface-100 dark:bg-surface-900 rounded-lg border border-surface-200 dark:border-surface-700">
				<div class="text-xs font-semibold text-surface-500 px-2">
					Found {searchResults.length} matching controls:
				</div>
				{#each searchResults as ctrl}
					<label class="flex items-center gap-3 p-2 rounded hover:bg-surface-200 dark:hover:bg-surface-800 cursor-pointer text-xs">
						<input
							type="checkbox"
							checked={selectedControlIds.has(ctrl.id)}
							onchange={() => {
								toggleControlSelection(ctrl.id);
							}}
							class="checkbox checkbox-primary"
						/>
						<span class="font-bold text-primary-600 dark:text-primary-400 font-mono bg-primary-500/10 px-1.5 py-0.5 rounded">
							[{ctrl.ref_id || 'ID'}]
						</span>
						<span class="font-medium text-surface-900 dark:text-surface-100 flex-1">{ctrl.name}</span>
						<span class="text-surface-400 text-[10px] bg-surface-200 dark:bg-surface-800 px-2 py-0.5 rounded">
							{ctrl.frameworkName} → {ctrl.domainName}
						</span>
					</label>
				{/each}
			</div>
		{:else if frameworksList.length > 0}
			<div class="max-h-96 overflow-y-auto space-y-3 p-2 bg-surface-100 dark:bg-surface-900 rounded-lg border border-surface-200 dark:border-surface-700">
				{#each frameworksList as fw}
					{@const fwState = getFrameworkSelectionState(fw)}
					<div class="border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden">
						<!-- Framework Header -->
						<div class="flex items-center justify-between p-3 bg-surface-200/50 dark:bg-surface-800/50">
							<div class="flex items-center gap-2">
								<input
									type="checkbox"
									checked={fwState.checked}
									use:setIndeterminate={fwState.indeterminate}
									onchange={() => toggleFrameworkSelection(fw)}
									class="checkbox checkbox-primary mr-1"
								/>
								<button
									type="button"
									class="flex items-center gap-2 font-bold text-sm text-surface-900 dark:text-surface-100 hover:text-primary-500"
									onclick={() => toggleFrameworkExpand(fw.id)}
								>
									<i class="fa-solid {expandedFrameworkIds.has(fw.id) ? 'fa-chevron-down' : 'fa-chevron-right'} text-xs"></i>
									<i class="fa-solid fa-book-bookmark text-primary-500"></i>
									<span>{fw.name}</span>
								</button>
							</div>
							<span class="text-xs font-semibold px-2 py-0.5 rounded bg-surface-300/40 dark:bg-surface-700 text-surface-700 dark:text-surface-300">
								{fwState.count} / {fwState.total} Selected
							</span>
						</div>

						<!-- Framework Domains -->
						{#if expandedFrameworkIds.has(fw.id)}
							<div class="p-2 space-y-2 bg-surface-50 dark:bg-surface-900">
								{#each fw.domains as dom}
									{@const domState = getDomainSelectionState(dom)}
									<div class="border border-surface-200/60 dark:border-surface-800 rounded-md">
										<!-- Domain Header -->
										<div class="flex items-center justify-between p-2 bg-surface-100 dark:bg-surface-800 text-xs font-semibold">
											<div class="flex items-center gap-2">
												<input
													type="checkbox"
													checked={domState.checked}
													use:setIndeterminate={domState.indeterminate}
													onchange={() => toggleDomainSelection(dom)}
													class="checkbox checkbox-primary mr-1"
												/>
												<button
													type="button"
													class="flex items-center gap-2 text-surface-800 dark:text-surface-200 hover:text-primary-500"
													onclick={() => toggleDomainExpand(dom.urn)}
												>
													<i class="fa-solid {expandedDomainUrns.has(dom.urn) ? 'fa-chevron-down' : 'fa-chevron-right'} text-[10px]"></i>
													<i class="fa-solid fa-folder-tree text-secondary-500"></i>
													<span>{dom.name}</span>
												</button>
											</div>
											<span class="text-[11px] font-medium text-surface-500">
												{domState.count} / {domState.total}
											</span>
										</div>

										<!-- Controls list -->
										{#if expandedDomainUrns.has(dom.urn)}
											<div class="p-2 grid grid-cols-1 md:grid-cols-2 gap-1.5 bg-surface-50 dark:bg-surface-900">
												{#each dom.controls as ctrl}
													<label class="flex items-start gap-2 p-1.5 rounded hover:bg-surface-200/50 dark:hover:bg-surface-800/50 cursor-pointer text-xs">
														<input
															type="checkbox"
															checked={selectedControlIds.has(ctrl.id)}
															onchange={() => {
																toggleControlSelection(ctrl.id);
															}}
															class="checkbox checkbox-primary mt-0.5"
														/>
														<div class="flex flex-col flex-1 leading-tight">
															<div class="flex items-center gap-1.5">
																<span class="font-bold text-primary-600 dark:text-primary-400 font-mono text-[11px]">
																	[{ctrl.ref_id || 'REQ'}]
																</span>
																<span class="font-medium text-surface-800 dark:text-surface-200">{ctrl.name}</span>
															</div>
														</div>
													</label>
												{/each}
											</div>
										{/if}
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{:else}
			<div class="p-6 text-center text-surface-500 text-sm flex flex-col items-center gap-2">
				<i class="fa-solid fa-folder-open text-2xl"></i>
				<span>No library checklists found. Click re-sync below to refresh.</span>
				<button type="button" class="btn variant-soft-primary text-xs px-3 py-1 mt-2" onclick={() => loadLibraryData(true)}>
					Reload Checklists Tree
				</button>
			</div>
		{/if}
	</div>
{/if}

{#if implementationGroupsChoices.length > 0}
	<AutocompleteSelect
		multiple
		translateOptions={false}
		{form}
		options={implementationGroupsChoices}
		field="selected_implementation_groups"
		cacheLock={cacheLocks['selected_implementation_groups']}
		bind:cachedValue={formDataCache['selected_implementation_groups']}
		label={m.selectedImplementationGroups()}
		helpText={is_dynamic ? m.selectedImplementationGroupsDynamicHelpText() : undefined}
	/>
{/if}

<TextField
	{form}
	field="version"
	label={m.version()}
	helpText={m.versionHelpText()}
	cacheLock={cacheLocks['version']}
	bind:cachedValue={formDataCache['version']}
/>

<Dropdown open={false} style="hover:text-primary-700" icon="fa-solid fa-clock" header={m.more()}>
	<div class="space-y-4 pt-2">
		<Select
			{form}
			options={[
				{ label: 'On-Demand Assessment', value: 'on_demand' },
				{ label: 'Scheduled Assessment (Yearly Auto-Trigger)', value: 'scheduled' }
			]}
			field="schedule_type"
			label="Assessment Trigger Type"
			helpText="Select whether this audit is triggered on demand or scheduled yearly."
			disableDoubleDash
		/>

		<!-- Audit Period Date Range Selector -->
		<div class="space-y-1">
			<label class="block text-sm font-medium text-surface-700 dark:text-surface-300">
				Audit Period Date Selector
			</label>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div>
					<label class="block text-xs font-semibold text-surface-600 dark:text-surface-400 mb-1">
						Audit Period Start Date
					</label>
					<input
						type="date"
						class="input border border-surface-300 dark:border-surface-600 rounded-md px-3 py-2 w-full text-sm bg-surface-50 dark:bg-surface-800 text-surface-900 dark:text-surface-100"
						bind:value={auditPeriodStartDate}
						onchange={handlePeriodDateChange}
					/>
				</div>
				<div>
					<label class="block text-xs font-semibold text-surface-600 dark:text-surface-400 mb-1">
						Audit Period End Date
					</label>
					<input
						type="date"
						class="input border border-surface-300 dark:border-surface-600 rounded-md px-3 py-2 w-full text-sm bg-surface-50 dark:bg-surface-800 text-surface-900 dark:text-surface-100"
						bind:value={auditPeriodEndDate}
						onchange={handlePeriodDateChange}
					/>
				</div>
			</div>
			<p class="text-xs text-surface-500 mt-1">Select start and end dates for the audit coverage period (e.g. Jun 1, 2025 - May 31, 2026).</p>
		</div>

		<TextField
			{form}
			field="audit_period_year"
			label="Audit Period (Formatted Text)"
			helpText="Auto-generated from date selectors above or enter custom format (e.g. Jun 1, 2025 - May 31, 2026)"
			cacheLock={cacheLocks['audit_period_year']}
			bind:cachedValue={formDataCache['audit_period_year']}
		/>

		<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
			<TextField
				type="date"
				{form}
				field="start_date"
				label="Start Date"
				helpText="Date when audit begins"
				cacheLock={cacheLocks['start_date']}
				bind:cachedValue={formDataCache['start_date']}
			/>

			<TextField
				type="date"
				{form}
				field="evidence_due_date"
				label="Evidence Due Date"
				helpText="Target deadline for evidence submissions"
				cacheLock={cacheLocks['evidence_due_date']}
				bind:cachedValue={formDataCache['evidence_due_date']}
			/>

			<TextField
				type="date"
				{form}
				field="due_date"
				label="Audit End Date"
				helpText="Target audit closing date"
				cacheLock={cacheLocks['due_date']}
				bind:cachedValue={formDataCache['due_date']}
			/>
		</div>
	</div>
</Dropdown>

<!-- Custom Scope Modal Window -->
{#if isScopeModalOpen}
	<div class="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-surface-900/75 backdrop-blur-md">
		<div class="card bg-surface-100-900 w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl rounded-xl border border-surface-300 dark:border-surface-700 overflow-hidden">
			
			<!-- Modal Header -->
			<div class="p-4 border-b border-surface-300 dark:border-surface-700 flex items-center justify-between bg-surface-200-800">
				<div>
					<h3 class="text-lg font-bold text-surface-900 dark:text-surface-50 flex items-center gap-2">
						<i class="fa-solid fa-list-check text-primary-500"></i>
						<span>Select Custom Audit Scope & Controls</span>
					</h3>
					<p class="text-xs text-surface-500">Browse checklists → domains → controls or search across all stored library frameworks.</p>
				</div>
				<button type="button" class="btn-icon btn-sm variant-ghost hover:variant-soft" onclick={() => isScopeModalOpen = false}>
					<i class="fa-solid fa-xmark text-lg"></i>
				</button>
			</div>

			<!-- Search Bar -->
			<div class="p-4 border-b border-surface-300 dark:border-surface-700 bg-surface-100-900 flex items-center gap-3">
				<div class="relative flex-1">
					<i class="fa-solid fa-magnifying-glass absolute left-3 top-3 text-surface-400 text-sm"></i>
					<input
						type="text"
						bind:value={modalSearchQuery}
						placeholder="Search controls by ref ID (e.g. DOM-16, A.5.1) or control name across all checklists..."
						class="input pl-9 text-sm w-full bg-surface-50 dark:bg-surface-800"
					/>
				</div>
				{#if modalSearchQuery}
					<button type="button" class="btn btn-sm variant-soft" onclick={() => modalSearchQuery = ''}>
						Clear Search
					</button>
				{/if}
			</div>

			<!-- Modal Main Body -->
			<div class="flex-1 overflow-y-auto p-4 space-y-4">
				{#if isLoadingLibrary}
					<div class="flex items-center justify-center py-16 text-surface-500 gap-3">
						<i class="fa-solid fa-spinner fa-spin text-2xl text-primary-500"></i>
						<span class="text-sm font-medium">Loading library checklists, domains, and controls...</span>
					</div>
				{:else if modalSearchQuery.trim()}
					<!-- Search Results View -->
					<div class="space-y-2">
						<p class="text-xs font-semibold text-surface-500 uppercase tracking-wider">
							Search Results ({searchResults.length} controls found)
						</p>
						{#each searchResults as ctrl}
							<label class="flex items-start gap-3 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:bg-surface-200-800 cursor-pointer transition-colors">
								<input
									type="checkbox"
									checked={selectedControlIds.has(ctrl.id)}
									onchange={() => toggleControlSelection(ctrl.id)}
									class="checkbox mt-0.5"
								/>
								<div class="flex-1 min-w-0">
									<div class="flex items-center gap-2 flex-wrap">
										<span class="badge variant-soft-primary text-[10px] font-mono">{ctrl.frameworkName}</span>
										<span class="badge variant-soft-surface text-[10px]">{ctrl.domainName}</span>
										{#if ctrl.ref_id}
											<span class="text-xs font-mono font-bold text-secondary-500">{ctrl.ref_id}</span>
										{/if}
									</div>
									<p class="text-sm font-medium text-surface-900 dark:text-surface-100 mt-1">{ctrl.name}</p>
								</div>
							</label>
						{/each}
					</div>
				{:else}
					<!-- Hierarchy: Checklist -> Domain -> Controls -->
					<div class="space-y-3">
						{#each frameworksList as fw}
							<div class="border border-surface-300 dark:border-surface-700 rounded-lg overflow-hidden bg-surface-50 dark:bg-surface-850">
								<!-- Framework Header -->
								<div class="flex items-center justify-between p-3 bg-surface-200-800 cursor-pointer hover:bg-surface-300-700 select-none" onclick={() => toggleFrameworkExpand(fw.id)}>
									<div class="flex items-center gap-3">
										<i class="fa-solid {expandedFrameworkIds.has(fw.id) ? 'fa-chevron-down text-primary-500' : 'fa-chevron-right text-surface-400'} text-xs"></i>
										<i class="fa-solid fa-book-bookmark text-primary-500 text-sm"></i>
										<span class="font-semibold text-sm text-surface-900 dark:text-surface-100">{fw.name}</span>
									</div>
									<div class="flex items-center gap-2" onclick={(e) => e.stopPropagation()}>
										<button type="button" class="btn btn-xs variant-soft-primary" onclick={() => selectAllInFramework(fw.id)}>
											Select All Controls in Framework
										</button>
									</div>
								</div>

								<!-- Domains List under Framework -->
								{#if expandedFrameworkIds.has(fw.id)}
									<div class="p-3 space-y-3 border-t border-surface-200 dark:border-surface-750">
										{#each fw.domains as dom}
											<div class="border border-surface-200 dark:border-surface-700 rounded-md overflow-hidden bg-surface-100 dark:bg-surface-900">
												<!-- Domain Header -->
												<div class="flex items-center justify-between p-2.5 bg-surface-200-800 cursor-pointer hover:bg-surface-300-700 select-none" onclick={() => toggleDomainExpand(dom.urn)}>
													<div class="flex items-center gap-2">
														<i class="fa-solid {expandedDomainUrns.has(dom.urn) ? 'fa-folder-open text-warning-500' : 'fa-folder text-surface-400'} text-xs"></i>
														<span class="font-medium text-xs text-surface-900 dark:text-surface-100">{dom.name}</span>
														<span class="text-[10px] text-surface-500">({dom.controls.length} controls)</span>
													</div>
													<div class="flex items-center gap-2" onclick={(e) => e.stopPropagation()}>
														<button type="button" class="btn btn-xs variant-soft" onclick={() => selectAllInDomain(dom)}>
															Select All Domain Controls
														</button>
													</div>
												</div>

												<!-- Controls List under Domain -->
												{#if expandedDomainUrns.has(dom.urn)}
													<div class="p-2 space-y-1 bg-surface-50 dark:bg-surface-950 divide-y divide-surface-200 dark:divide-surface-800">
														{#each dom.controls as ctrl}
															<label class="flex items-start gap-3 p-2 rounded hover:bg-surface-200-800 cursor-pointer text-xs transition-colors">
																<input
																	type="checkbox"
																	checked={selectedControlIds.has(ctrl.id)}
																	onchange={() => toggleControlSelection(ctrl.id)}
																	class="checkbox mt-0.5"
																/>
																<div class="flex-1 min-w-0">
																	<div class="flex items-center gap-2">
																		{#if ctrl.ref_id}
																			<span class="font-mono font-bold text-secondary-500">{ctrl.ref_id}</span>
																		{/if}
																		<span class="font-medium text-surface-800 dark:text-surface-200">{ctrl.name}</span>
																	</div>
																</div>
															</label>
														{/each}
													</div>
												{/if}
											</div>
										{/each}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Modal Footer -->
			<div class="p-4 border-t border-surface-300 dark:border-surface-700 bg-surface-200-800 flex items-center justify-between">
				<div class="text-xs font-semibold text-primary-500 flex items-center gap-2">
					<i class="fa-solid fa-circle-check"></i>
					<span>{selectedControlIds.size} controls selected for assessment scope</span>
				</div>
				<div class="flex items-center gap-2">
					<button type="button" class="btn btn-sm variant-ghost" onclick={() => isScopeModalOpen = false}>
						Cancel
					</button>
					<button type="button" class="btn btn-sm variant-filled-primary font-semibold" onclick={applyScopeSelection}>
						Apply Selected Controls ({selectedControlIds.size})
					</button>
				</div>
			</div>

		</div>
	</div>
{/if}
