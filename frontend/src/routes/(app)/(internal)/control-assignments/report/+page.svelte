<script lang="ts">
	import { onMount } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';
	import type { PageData } from './$types';

	pageTitle.set('Assessment Control Audit Report');

	let { data }: { data: PageData } = $props();

	let loading = $state(true);
	let assessments = $state<any[]>([]);
	let frameworks = $state<any[]>([]);
	let selectedTarget = $state<string>('');
	let selectedAssessmentId = $state<string>('');
	let selectedFrameworkId = $state<string>('');
	let reportSummary = $state<any>(null);
	let controlsList = $state<any[]>([]);

	let currentPage = $state(1);
	let totalPages = $state(1);

	let transitioning = $state(false);
	let reopenReason = $state('');
	let showReopenModal = $state(false);
	let transitionError = $state('');
	let initialized = false;

	$effect(() => {
		if (data && !initialized) {
			initialized = true;
			assessments = data.assessments || [];
			frameworks = data.frameworks || [];

			if (assessments.length > 0) {
				selectedAssessmentId = assessments[0].id;
				selectedTarget = `assessment:${assessments[0].id}`;
			} else if (frameworks.length > 0) {
				selectedFrameworkId = frameworks[0].id;
				selectedTarget = `framework:${frameworks[0].id}`;
			}
			loadReportData();
		}
	});

	function onTargetChange() {
		if (selectedTarget.startsWith('assessment:')) {
			selectedAssessmentId = selectedTarget.replace('assessment:', '');
			selectedFrameworkId = '';
		} else if (selectedTarget.startsWith('framework:')) {
			selectedFrameworkId = selectedTarget.replace('framework:', '');
			selectedAssessmentId = '';
		}
		loadReportData();
	}

	async function loadReportData(page: number = 1) {
		loading = true;
		currentPage = page;

		try {
			let urlParam = selectedAssessmentId
				? `assessment_id=${selectedAssessmentId}`
				: selectedFrameworkId
				? `framework_id=${selectedFrameworkId}`
				: '';

			if (!urlParam) {
				loading = false;
				return;
			}

			// 1. Fetch Summary Metrics
			const sumRes = await fetch(`/api/control-assignments-report/summary/?${urlParam}`);
			if (sumRes.ok) {
				reportSummary = await sumRes.json();
			}

			// 2. Fetch Control Details Table (large page size for audit completeness)
			const ctrlRes = await fetch(`/api/control-assignments-report/controls/?${urlParam}&page=${page}&page_size=100`);
			if (ctrlRes.ok) {
				const ctrlData = await ctrlRes.json();
				controlsList = ctrlData.results || [];
				totalPages = ctrlData.total_pages || 1;
			}
		} catch (err) {
			console.error('Failed to load report data:', err);
		} finally {
			loading = false;
		}
	}

	function exportPDF() {
		window.print();
	}

	async function transitionPhase(newPhase: string, reason: string = '') {
		if (!selectedAssessmentId) return;
		transitioning = true;
		transitionError = '';

		try {
			const res = await fetch(`/api/compliance-assessments/${selectedAssessmentId}/phase-transition/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ new_phase: newPhase, reopen_reason: reason })
			});

			if (res.ok) {
				showReopenModal = false;
				reopenReason = '';
				loadReportData();
			} else {
				const err = await res.json();
				transitionError = err.error || 'Phase transition failed.';
			}
		} catch (err) {
			transitionError = 'Network error during phase transition.';
		} finally {
			transitioning = false;
		}
	}

	const user = $derived(data.currentUser);
	const isSuperOrWebAdmin = $derived(
		user?.is_superuser ||
		user?.platform_role === 'superadmin' ||
		user?.platform_role === 'webadmin'
	);

	const selectedTargetName = $derived(() => {
		if (selectedAssessmentId) {
			const a = assessments.find((x) => x.id === selectedAssessmentId);
			return a ? a.name : 'Compliance Audit';
		}
		if (selectedFrameworkId) {
			const fw = frameworks.find((x) => x.id === selectedFrameworkId);
			return fw ? fw.name : 'Compliance Framework';
		}
		return 'Compliance Audit Report';
	});
</script>

<svelte:head>
	<style>
		@media print {
			body {
				background-color: white !important;
				color: black !important;
			}
			.no-print {
				display: none !important;
			}
			.print-only {
				display: block !important;
			}
			table {
				width: 100% !important;
				border-collapse: collapse !important;
			}
			th, td {
				border: 1px solid #cbd5e1 !important;
				padding: 6px 10px !important;
				color: black !important;
			}
			th {
				background-color: #f1f5f9 !important;
			}
		}
		.print-only {
			display: none;
		}
	</style>
</svelte:head>

{#if !data.hasPermission}
	<div class="p-16 text-center border border-dashed border-rose-500/30 rounded-2xl bg-rose-500/5 space-y-3">
		<div class="w-12 h-12 rounded-full bg-rose-500/10 text-rose-500 flex items-center justify-center mx-auto text-xl">
			<i class="fa-solid fa-lock"></i>
		</div>
		<h4 class="text-base font-bold text-rose-500">No Permission</h4>
		<p class="text-xs text-surface-500 max-w-sm mx-auto">
			Audit Reports access is restricted to Webadmin and Superadmin users only.
		</p>
	</div>
{:else}
	<div class="space-y-6">
		<!-- Printable PDF Header -->
		<div class="print-only mb-6 border-b pb-4">
			<h1 class="text-2xl font-bold text-slate-900">Compliance Audit & Assessment Report</h1>
			<p class="text-sm text-slate-600">Target: <strong>{selectedTargetName()}</strong> | Generated: {new Date().toLocaleString()}</p>
		</div>

		<!-- Top Navigation & PDF Export Actions (Screen Only) -->
		<div class="no-print flex flex-wrap items-center justify-between gap-4 bg-surface-100-900/60 p-4 rounded-xl border border-surface-200-800">
			<div class="flex items-center gap-3 flex-wrap">
				{#if isSuperOrWebAdmin}
					<a
						href="/control-assignments"
						class="px-4 py-2 rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-700-300 hover:bg-surface-200-800 text-sm font-medium transition-all flex items-center gap-2"
					>
						<i class="fa-solid fa-list-check"></i>
						<span>Control Assignments</span>
					</a>
				{/if}
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
				{#if isSuperOrWebAdmin}
					<a
						href="/control-assignments/report"
						class="px-4 py-2 rounded-lg bg-purple-600 text-white font-semibold text-sm shadow-xs flex items-center gap-2"
					>
						<i class="fa-solid fa-chart-pie"></i>
						<span>Audit Reports</span>
					</a>
				{/if}
			</div>

			<!-- PDF Export Button -->
			<button
				onclick={exportPDF}
				class="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-sm shadow-md transition-all flex items-center gap-2 cursor-pointer"
			>
				<i class="fa-solid fa-file-pdf"></i>
				<span>Export / Download PDF Report</span>
			</button>
		</div>

		<!-- Unified Single Target Selector Bar -->
		<div class="no-print p-4 rounded-xl border border-surface-200-800 bg-surface-50-950 space-y-4">
			<div class="flex flex-wrap items-center justify-between gap-4">
				<div class="flex items-center gap-3 flex-wrap w-full md:w-auto">
					<label class="text-xs font-bold text-surface-900-100 flex items-center gap-2 shrink-0">
						<i class="fa-solid fa-layer-group text-purple-500"></i>
						<span>Select Audit / Framework Target:</span>
					</label>
					<select
						bind:value={selectedTarget}
						onchange={onTargetChange}
						class="px-3 py-2 text-xs rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 font-medium min-w-80"
					>
						{#if assessments.length > 0}
							<optgroup label="📋 Active Compliance Audits & Assessments">
								{#each assessments as a}
									<option value={`assessment:${a.id}`}>{a.name} ({a.audit_phase || 'ACTIVE'})</option>
								{/each}
							</optgroup>
						{/if}
						{#if frameworks.length > 0}
							<optgroup label="📚 Compliance Frameworks & Checklists">
								{#each frameworks as fw}
									<option value={`framework:${fw.id}`}>{fw.name}</option>
								{/each}
							</optgroup>
						{/if}
					</select>
				</div>
			</div>
		</div>

		<!-- Comprehensive Summary KPI Cards Grid -->
		{#if reportSummary}
			<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3">
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Total Controls</span>
					<span class="text-xl font-black text-surface-900-100">{reportSummary.total_controls || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Assigned Controls</span>
					<span class="text-xl font-black text-blue-500">{reportSummary.assigned_controls_count || reportSummary.summary?.assigned_controls_count || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Unassigned</span>
					<span class="text-xl font-black text-surface-400">{reportSummary.unassigned_controls_count || reportSummary.summary?.unassigned_controls_count || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Evidences Submitted</span>
					<span class="text-xl font-black text-amber-500">{reportSummary.evidence_submitted_count || reportSummary.summary?.evidence_submitted_count || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Pending Upload</span>
					<span class="text-xl font-black text-orange-500">{reportSummary.pending_evidence_upload || reportSummary.summary?.pending_evidence_upload || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Pending Review</span>
					<span class="text-xl font-black text-cyan-500">{reportSummary.controls_pending_review || reportSummary.summary?.controls_pending_review || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Compliant / Approved</span>
					<span class="text-xl font-black text-emerald-500">{reportSummary.approved_controls_count || reportSummary.controls_compliant || reportSummary.summary?.controls_compliant || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Rejected</span>
					<span class="text-xl font-black text-rose-500">{reportSummary.rejected_controls_count || reportSummary.controls_non_compliant || reportSummary.summary?.controls_non_compliant || 0}</span>
				</div>
				<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 text-center space-y-1">
					<span class="text-[10px] font-bold text-surface-500 uppercase tracking-wider block">Compliance Rate</span>
					<span class="text-xl font-black text-purple-500">{reportSummary.completion_percentage || reportSummary.summary?.compliance_percentage || 0}%</span>
				</div>
			</div>
		{/if}

		<!-- Controls Audit Table -->
		{#if loading}
			<div class="p-12 text-center text-surface-500 font-medium">Loading audit report details...</div>
		{:else if controlsList.length === 0}
			<div class="p-12 text-center border border-dashed border-surface-200-800 rounded-2xl bg-surface-50-950/50">
				<p class="text-xs text-surface-500">No controls found in this audit snapshot or framework.</p>
			</div>
		{:else}
			<div class="border border-surface-200-800 rounded-xl overflow-hidden bg-surface-50-950">
				<table class="w-full text-left text-xs">
					<thead class="bg-surface-100-900/70 border-b border-surface-200-800 font-bold uppercase tracking-wider text-surface-600-400">
						<tr>
							<th class="p-3 w-20">Ref ID</th>
							<th class="p-3">Control Name</th>
							<th class="p-3 w-36">Assigned SPOC</th>
							<th class="p-3 w-36">Assigned Reviewer</th>
							<th class="p-3 w-28 text-center">Status</th>
							<th class="p-3 w-32">Evidence File</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-surface-200-800/50">
						{#each controlsList as ctrl}
							<tr class="hover:bg-surface-100-900/40">
								<td class="p-3 font-mono font-bold text-amber-500">{ctrl.ref_id}</td>
								<td class="p-3 font-medium text-surface-900-100">{ctrl.name}</td>
								<td class="p-3 text-amber-500 font-semibold">{ctrl.spoc || 'Unassigned'}</td>
								<td class="p-3 text-emerald-500 font-semibold">{ctrl.reviewer_email || 'Unassigned'}</td>
								<td class="p-3 text-center">
									<span class="px-2 py-0.5 rounded font-bold text-[10px] border {ctrl.overall_status === 'APPROVED' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : ctrl.overall_status === 'REJECTED' ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' : ctrl.overall_status === 'PENDING_REVIEW' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' : 'bg-surface-500/10 text-surface-500 border-surface-500/20'}">
										{ctrl.overall_status || 'PENDING'}
									</span>
								</td>
								<td class="p-3 font-mono text-[11px] truncate max-w-32">
									{#if ctrl.evidences && ctrl.evidences.length > 0}
										<a href={ctrl.evidences[0].file_url || '#'} target="_blank" class="text-primary-500 hover:underline flex items-center gap-1">
											<i class="fa-solid fa-paperclip"></i>
											<span class="truncate">{ctrl.evidences[0].name}</span>
										</a>
									{:else}
										<span class="text-surface-400">None</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
{/if}
