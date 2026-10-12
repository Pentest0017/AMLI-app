<script lang="ts">
	import DonutChart from '$lib/components/Chart/DonutChart.svelte';
	import { m } from '$paraglide/messages';
	import { page } from '$app/state';
	import { Progress } from '@skeletonlabs/skeleton-svelte';
	import { displayScoreColor, formatScoreValue } from '$lib/utils/helpers';
	import type { PageData } from './$types';
	import Anchor from '$lib/components/Anchor/Anchor.svelte';
	import { canPerformAction } from '$lib/utils/access-control';
	import { URL_MODEL_MAP } from '$lib/utils/crud';
	import GenerateAuditReportModal from '$lib/components/Modals/GenerateAuditReportModal.svelte';

	let showReportModal = $state(false);
	let selectedReportAudit = $state<any>(null);

	function openReportModal(assessment: any) {
		selectedReportAudit = {
			id: assessment.id,
			name: assessment.name,
			framework_name: assessment.framework?.str || 'Custom Upload'
		};
		showReportModal = true;
	}

	const REQUIREMENT_ASSESSMENT_STATUS = [
		'compliant',
		'partially_compliant',
		'in_progress',
		'non_compliant',
		'not_applicable',
		'to_do'
	] as const;

	const user = page.data.user;

	interface Props {
		data: PageData;
	}

	let { data }: Props = $props();

	const foldersWithAssessments = $derived(
		data.folderRecaps.filter((folderRecap) => folderRecap.compliance_assessments.length > 0)
	);

	const model = URL_MODEL_MAP['folders'];
	const canEditObject = (folder: any): boolean =>
		canPerformAction({
			user,
			action: 'change',
			model: model.name,
			domain: folder.id
		});

	let showControlsModal = $state(false);
	let activeModalAssessmentId = $state<string | null>(null);
	let activeModalAssessmentName = $state<string>('');
	let controlsList = $state<any[]>([]);
	let loadingControls = $state(false);
	let controlsSearchQuery = $state('');

	function getDetailedDonutValues(assessment: any) {
		const sb = assessment.status_breakdown;
		if (!sb) {
			return assessment.donut?.result?.values || [];
		}

		const items = [
			{
				name: 'not_assigned',
				localName: 'Not Assigned',
				value: sb.not_assigned || 0,
				itemStyle: { color: '#9ca3af' }
			},
			{
				name: 'pending_evidence',
				localName: 'Pending Evidence',
				value: sb.pending_evidence || 0,
				itemStyle: { color: '#f59e0b' }
			},
			{
				name: 'pending_review',
				localName: 'Pending Review',
				value: sb.pending_review || 0,
				itemStyle: { color: '#06b6d4' }
			},
			{
				name: 'approved',
				localName: 'Approved / Compliant',
				value: sb.approved || 0,
				itemStyle: { color: '#10b981' }
			},
			{
				name: 'rejected',
				localName: 'Rejected',
				value: sb.rejected || 0,
				itemStyle: { color: '#f43f5e' }
			},
			{
				name: 'not_applicable',
				localName: 'Not Applicable (N/A)',
				value: sb.not_applicable || 0,
				itemStyle: { color: '#a855f7' }
			}
		];

		const activeItems = items.filter((i) => i.value > 0);
		return activeItems.length > 0 ? activeItems : items;
	}

	async function openControlsModal(assessmentId: string, assessmentName: string) {
		activeModalAssessmentId = assessmentId;
		activeModalAssessmentName = assessmentName;
		showControlsModal = true;
		loadingControls = true;
		controlsSearchQuery = '';

		try {
			const res = await fetch(`/api/compliance-assessments/${assessmentId}/controls-detail/`, {
				headers: { Accept: 'application/json' }
			});
			if (res.ok) {
				const data = await res.json();
				controlsList = data.controls || [];
			} else {
				console.error('controls-detail returned non-OK status:', res.status);
			}
		} catch (err) {
			console.error('Failed to load controls detail:', err);
		} finally {
			loadingControls = false;
		}
	}

	async function toggleNotApplicable(ctrl: any) {
		if (!activeModalAssessmentId) return;
		const isCurrentlyNa = ctrl.status === 'NOT_APPLICABLE' || ctrl.result === 'not_applicable';
		const nextNaState = !isCurrentlyNa;

		try {
			const res = await fetch(`/api/compliance-assessments/${activeModalAssessmentId}/set-not-applicable/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					requirement_assessment_id: ctrl.id,
					is_not_applicable: nextNaState
				})
			});

			if (res.ok) {
				ctrl.status = nextNaState ? 'NOT_APPLICABLE' : 'NOT_ASSIGNED';
				ctrl.result = nextNaState ? 'not_applicable' : 'not_assessed';
				openControlsModal(activeModalAssessmentId, activeModalAssessmentName);
			}
		} catch (err) {
			console.error('Failed to toggle N/A status:', err);
		}
	}

	const filteredModalControls = $derived(
		controlsList.filter(
			(c) =>
				c.name.toLowerCase().includes(controlsSearchQuery.toLowerCase()) ||
				c.ref_id.toLowerCase().includes(controlsSearchQuery.toLowerCase()) ||
				(c.spoc && c.spoc.toLowerCase().includes(controlsSearchQuery.toLowerCase()))
		)
	);
</script>

<div class="p-4 space-y-6 bg-surface-50-950 min-h-screen card">
	<h2 class="text-2xl font-extrabold text-surface-950-50 mb-4">{m.overallCompliance()}</h2>

	<div class="space-y-6">
		{#if foldersWithAssessments.length === 0}
			<div class="flex items-center justify-center min-h-[60vh]">
				<div class="text-center max-w-lg">
					<p class="text-xl font-bold text-surface-950-50">
						{m.createYourFirstAuditToSeeRecapPage()}
					</p>
					<p class="mt-2 text-sm text-surface-600-400">
						{m.AuditExistsYoullSeeOverallCompliance()}
					</p>
				</div>
			</div>
		{:else}
			{#each foldersWithAssessments as folder}
				<div
					class="bg-surface-50-950 shadow-lg rounded-xl border border-surface-200-800 overflow-hidden transition hover:shadow-xl transform w-full"
				>
					<div
						class="p-4 bg-gradient-to-r from-primary-400 to-primary-500 text-white flex justify-between items-center"
					>
						<a class="text-lg font-bold hover:underline" href="/folders/{folder.id}">
							{folder.name}
						</a>
					</div>

					{#if folder.overallCompliance?.values?.length > 0}
						<div
							class="px-4 py-3 bg-gradient-to-r from-primary-50 to-primary-100 dark:from-surface-800 dark:to-surface-900 rounded-b-lg"
						>
							<p class="text-sm font-semibold text-primary-700 dark:text-primary-300 mb-2">
								{m.globalOverall()}
							</p>
							<div class="flex h-6 rounded-lg overflow-hidden shadow-inner">
								{#each folder.overallCompliance.values.sort((a, b) => REQUIREMENT_ASSESSMENT_STATUS.indexOf(a.name) - REQUIREMENT_ASSESSMENT_STATUS.indexOf(b.name)) as sp}
									<div
										class="flex justify-center items-center text-xs font-semibold"
										style="
										width: {sp.percentage}%;
										background-color: {sp.itemStyle.color};
										color: {sp.itemStyle.color === '#000000' ? 'white' : 'black'};
										box-shadow: inset 0 0 1px rgba(0,0,0,0.3);
									"
									>
										{Number(sp.percentage) > 5 ? `${sp.percentage}%` : ''}
									</div>
								{/each}
							</div>
						</div>
					{/if}

					<div class="p-4 space-y-4">
						{#each folder.compliance_assessments as assessment}
							<div
								class="bg-surface-50-950 rounded-lg p-4 shadow-inner transition hover:bg-surface-100-900 space-y-4"
							>
								<div class="flex justify-between items-center">
									<div>
										<p class="text-sm font-semibold">{m.name()}</p>
										<a
											class="text-blue-600 dark:text-blue-400 hover:underline text-lg font-bold"
											href="/compliance-assessments/{assessment.id}"
										>
											{assessment.name}
										</a>
									</div>
									<div>
										<p class="text-sm font-semibold">{m.framework()}</p>
										<p>{assessment.framework.str}</p>
									</div>
								</div>

								<!-- Rich 6-Status Metric Badges Bar -->
								{#if assessment.status_breakdown}
									<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
										<div class="p-2 rounded-lg border border-surface-200-800 bg-surface-100-900/60 text-center">
											<span class="text-[10px] font-bold text-surface-400 uppercase tracking-wider block">Not Assigned</span>
											<span class="text-base font-black text-surface-300">{assessment.status_breakdown.not_assigned || 0}</span>
										</div>
										<div class="p-2 rounded-lg border border-amber-500/20 bg-amber-500/5 text-center">
											<span class="text-[10px] font-bold text-amber-500 uppercase tracking-wider block">Pending Evidence</span>
											<span class="text-base font-black text-amber-400">{assessment.status_breakdown.pending_evidence || 0}</span>
										</div>
										<div class="p-2 rounded-lg border border-cyan-500/20 bg-cyan-500/5 text-center">
											<span class="text-[10px] font-bold text-cyan-500 uppercase tracking-wider block">Pending Review</span>
											<span class="text-base font-black text-cyan-400">{assessment.status_breakdown.pending_review || 0}</span>
										</div>
										<div class="p-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-center">
											<span class="text-[10px] font-bold text-emerald-500 uppercase tracking-wider block">Approved / Compliant</span>
											<span class="text-base font-black text-emerald-400">{assessment.status_breakdown.approved || 0}</span>
										</div>
										<div class="p-2 rounded-lg border border-rose-500/20 bg-rose-500/5 text-center">
											<span class="text-[10px] font-bold text-rose-500 uppercase tracking-wider block">Rejected</span>
											<span class="text-base font-black text-rose-400">{assessment.status_breakdown.rejected || 0}</span>
										</div>
										<div class="p-2 rounded-lg border border-purple-500/20 bg-purple-500/5 text-center">
											<span class="text-[10px] font-bold text-purple-400 uppercase tracking-wider block">Not Applicable (N/A)</span>
											<span class="text-base font-black text-purple-300">{assessment.status_breakdown.not_applicable || 0}</span>
										</div>
									</div>
								{/if}

								<div class="flex flex-col lg:flex-row items-center justify-between gap-4">
									{#if assessment.global_score.maturity_score >= 0}
										<div class="flex justify-center items-center lg:order-1">
											<div class="relative">
												<Progress
													value={formatScoreValue(
														assessment.global_score.maturity_score,
														assessment.global_score.max_score
													)}
													min={0}
													max={100}
												>
													<Progress.Circle class="[--size:--spacing(24)]">
														<Progress.CircleTrack />
														<Progress.CircleRange
															class={displayScoreColor(
																assessment.global_score.maturity_score,
																assessment.global_score.max_score
															)}
														/>
													</Progress.Circle>
													<div class="absolute inset-0 flex items-center justify-center">
														<p class="font-semibold text-2xl">
															{assessment.global_score.maturity_score}
														</p>
													</div>
												</Progress>
											</div>
										</div>
									{/if}

									<div class="w-full lg:w-3/5 h-40 lg:h-32">
										<DonutChart
											s_label={m.complianceAssessments()}
											name={assessment.name + '_donut'}
											values={getDetailedDonutValues(assessment)}
										/>
									</div>

									<div
										class="flex flex-row lg:flex-col space-x-2 lg:space-x-0 lg:space-y-2 lg:order-3 w-full lg:w-48"
									>
										<!-- Webadmin Controls & Evidences Table Button -->
										<button
											onclick={() => openControlsModal(assessment.id, assessment.name)}
											class="px-3 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer w-full"
										>
											<i class="fa-solid fa-table-list"></i>
											<span>Controls & Evidences Table</span>
										</button>
										{#if canEditObject(folder)}
											<Anchor
												href="/compliance-assessments/{assessment.id}/edit?next=/recap"
												class="btn preset-filled-primary-500 w-1/2 lg:w-full"
											>
												<i class="fa-solid fa-edit mr-2"></i>
												{m.edit()}
											</Anchor>
										{/if}
										<button
											type="button"
											onclick={() => openReportModal(assessment)}
											class="btn preset-filled-primary-500 w-1/2 lg:w-full cursor-pointer"
										>
											<i class="fa-solid fa-download mr-2"></i>
											{m.exportButton()}
										</button>
									</div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>

<!-- Webadmin Controls & Evidences Table Modal -->
{#if showControlsModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
		<div class="bg-surface-50-950 border border-surface-200-800 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
			<!-- Modal Header -->
			<div class="p-4 border-b border-surface-200-800 flex items-center justify-between bg-surface-100-900/60">
				<div>
					<h3 class="text-lg font-bold text-surface-900-100 flex items-center gap-2">
						<i class="fa-solid fa-table-list text-purple-500"></i>
						<span>Controls & Evidences Inspection</span>
					</h3>
					<p class="text-xs text-surface-400">Audit Target: <strong class="text-surface-200">{activeModalAssessmentName}</strong></p>
				</div>
				<button
					onclick={() => (showControlsModal = false)}
					class="w-8 h-8 rounded-lg hover:bg-surface-200-800 text-surface-400 hover:text-surface-100 flex items-center justify-center transition-all cursor-pointer"
				>
					<i class="fa-solid fa-xmark text-lg"></i>
				</button>
			</div>

			<!-- Filter Search Bar -->
			<div class="p-4 border-b border-surface-200-800 bg-surface-50-950 flex items-center justify-between gap-4">
				<div class="relative flex-1">
					<i class="fa-solid fa-search absolute left-3 top-1/2 -translate-y-1/2 text-surface-400 text-xs"></i>
					<input
						type="text"
						bind:value={controlsSearchQuery}
						placeholder="Search controls by Ref ID, Name, or SPOC..."
						class="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 focus:outline-hidden focus:border-purple-500"
					/>
				</div>
				<span class="text-xs text-surface-400 font-mono">
					{filteredModalControls.length} / {controlsList.length} Controls
				</span>
			</div>

			<!-- Controls Inspection Table -->
			<div class="flex-1 overflow-y-auto p-4">
				{#if loadingControls}
					<div class="p-12 text-center text-surface-400 font-medium">Loading controls & evidence data...</div>
				{:else if filteredModalControls.length === 0}
					<div class="p-12 text-center border border-dashed border-surface-200-800 rounded-xl">
						<p class="text-xs text-surface-400">No controls match search query.</p>
					</div>
				{:else}
					<div class="border border-surface-200-800 rounded-xl overflow-hidden bg-surface-50-950">
						<table class="w-full text-left text-xs">
							<thead class="bg-surface-100-900/80 border-b border-surface-200-800 font-bold uppercase tracking-wider text-surface-400">
								<tr>
									<th class="p-3 w-20">Ref ID</th>
									<th class="p-3">Control Name</th>
									<th class="p-3 w-36">Assigned SPOC</th>
									<th class="p-3 w-32 text-center">Status</th>
									<th class="p-3 w-36">Evidence Attachment</th>
									<th class="p-3 w-28 text-center">N/A State</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-surface-200-800/50">
								{#each filteredModalControls as ctrl}
									<tr class="hover:bg-surface-100-900/40">
										<td class="p-3 font-mono font-bold text-amber-500">{ctrl.ref_id}</td>
										<td class="p-3 font-medium text-surface-900-100">{ctrl.name}</td>
										<td class="p-3 text-amber-400 font-medium">{ctrl.spoc || 'Unassigned'}</td>
										<td class="p-3 text-center">
											<span class="px-2 py-0.5 rounded font-bold text-[10px] border {ctrl.status === 'APPROVED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : ctrl.status === 'REJECTED' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : ctrl.status === 'PENDING_REVIEW' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' : ctrl.status === 'PENDING_EVIDENCE' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : ctrl.status === 'NOT_APPLICABLE' ? 'bg-purple-500/10 text-purple-300 border-purple-500/20' : 'bg-surface-500/10 text-surface-400 border-surface-500/20'}">
												{ctrl.status}
											</span>
										</td>
										<td class="p-3 font-mono text-[11px] truncate max-w-36">
											{#if ctrl.evidences && ctrl.evidences.length > 0}
												<a href={ctrl.evidences[0].file_url || '#'} target="_blank" class="text-primary-400 hover:underline flex items-center gap-1">
													<i class="fa-solid fa-paperclip"></i>
													<span class="truncate">{ctrl.evidences[0].name}</span>
												</a>
											{:else}
												<span class="text-surface-500">None</span>
											{/if}
										</td>
										<td class="p-3 text-center">
											<button
												onclick={() => toggleNotApplicable(ctrl)}
												class="px-2.5 py-1 rounded text-[10px] font-bold border transition-all cursor-pointer {ctrl.status === 'NOT_APPLICABLE' || ctrl.result === 'not_applicable' ? 'bg-purple-600 text-white border-purple-500' : 'border-surface-200-800 bg-surface-100-900 text-surface-400 hover:bg-surface-200-800'}"
											>
												{ctrl.status === 'NOT_APPLICABLE' || ctrl.result === 'not_applicable' ? 'N/A Active' : 'Set N/A'}
											</button>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>

			<!-- Modal Footer -->
			<div class="p-4 border-t border-surface-200-800 bg-surface-100-900/40 flex justify-end">
				<button
					onclick={() => (showControlsModal = false)}
					class="px-4 py-2 rounded-lg bg-surface-200-800 hover:bg-surface-300-700 text-surface-100 font-semibold text-xs transition-all cursor-pointer"
				>
					Close Inspection
				</button>
			</div>
		</div>
	</div>
{/if}

<GenerateAuditReportModal
	open={showReportModal}
	audit={selectedReportAudit}
	onClose={() => (showReportModal = false)}
/>
