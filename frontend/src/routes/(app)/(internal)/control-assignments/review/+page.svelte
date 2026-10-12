<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { pageTitle } from '$lib/utils/stores';
	import type { PageData } from './$types';

	pageTitle.set('Reviewer Evidence Approval');

	let { data }: { data: PageData } = $props();

	let loading = $state(false);
	let reviewControls = $state<any[]>(data?.reviewControls || []);
	let selectedLink = $state<any>(null);

	let searchQuery = $state('');
	let selectedFrameworkId = $state('');
	let frameworks = $state<any[]>(data?.frameworks || []);

	$effect(() => {
		const c = data?.reviewControls || [];
		const fw = data?.frameworks || [];
		untrack(() => {
			reviewControls = c;
			frameworks = fw;
		});
	});

	const user = $derived(data.currentUser);
	const isSuperOrWebAdmin = $derived(
		user?.is_superuser ||
		user?.platform_role === 'superadmin' ||
		user?.platform_role === 'webadmin'
	);

	const filteredReviews = $derived(
		reviewControls.filter((c) => {
			const matchesSearch =
				!searchQuery ||
				c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.control?.ref_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.control?.name?.toLowerCase().includes(searchQuery.toLowerCase());
			const matchesFw = !selectedFrameworkId || c.framework_id === selectedFrameworkId || c.control?.framework_id === selectedFrameworkId;
			return matchesSearch && matchesFw;
		})
	);

	// Review Action Form
	let actionType = $state<'APPROVED' | 'REJECTED'>('APPROVED');
	let feedback = $state('');
	let reviewerExpiryDate = $state('');
	let submitting = $state(false);
	let actionMessage = $state('');

	function getAttachmentUrl(item: any): string {
		if (item?.evidence_id) {
			return `/evidences/${item.evidence_id}/attachment`;
		}
		return item?.file_url || '#';
	}

	async function loadPendingReviews() {
		loading = true;
		try {
			const res = await fetch('/api/evidence-repository/?review_status=PENDING_REVIEW');
			if (res.ok) {
				const resData = await res.json();
				reviewControls = resData.results || [];
			}
		} catch (err) {
			console.error('Failed to load pending reviews:', err);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadPendingReviews();
	});

	function openReviewModal(link: any, type: 'APPROVED' | 'REJECTED') {
		selectedLink = link;
		actionType = type;
		feedback = '';
		reviewerExpiryDate = link.expiry_date || '';
		actionMessage = '';
	}

	async function handleReviewSubmit() {
		if (!selectedLink) return;
		submitting = true;
		actionMessage = '';

		const formData = new FormData();
		formData.append('link_id', selectedLink.id);
		formData.append('status', actionType);
		formData.append('feedback', feedback);
		if (reviewerExpiryDate) {
			formData.append('expiry_date', reviewerExpiryDate);
		}
		if (selectedLink.version !== undefined && selectedLink.version !== null) {
			formData.append('version', String(selectedLink.version));
		}

		try {
			const res = await fetch('?/reviewAction', {
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
				actionMessage = `Evidence ${actionType === 'APPROVED' ? 'Approved' : 'Rejected'} successfully!`;
				const linkIdToRemove = selectedLink.id;
				setTimeout(async () => {
					selectedLink = null;
					reviewControls = reviewControls.filter((r) => r.id !== linkIdToRemove);
					await invalidateAll();
					await loadPendingReviews();
				}, 600);
			} else if (dataResult.conflict || dataResult[0]?.conflict) {
				actionMessage = dataResult.error || dataResult[0]?.error || 'Conflict: Modified by another reviewer.';
				setTimeout(async () => {
					selectedLink = null;
					await invalidateAll();
					await loadPendingReviews();
				}, 1500);
			} else {
				actionMessage = dataResult.error || dataResult[0]?.error || 'Failed to submit review.';
			}
		} catch (err: any) {
			actionMessage = err.message || 'Network error submitting review.';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="space-y-6">
	<!-- Top Navigation Actions -->
	<div class="flex flex-wrap items-center justify-between gap-4 bg-surface-100-900/60 p-4 rounded-xl border border-surface-200-800">
		<div class="flex items-center gap-3">
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
				class="px-4 py-2 rounded-lg bg-emerald-600 text-white font-semibold text-sm shadow-xs flex items-center gap-2"
			>
				<i class="fa-solid fa-clipboard-check"></i>
				<span>Reviewer Approval</span>
			</a>
		</div>
	</div>

	<!-- Controls Filters Bar -->
	<div class="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-surface-200-800 bg-surface-50-950">
		<div class="flex items-center gap-4 flex-wrap">
			<div class="flex items-center gap-2">
				<label class="text-xs font-semibold text-surface-700-300">Framework:</label>
				<select
					bind:value={selectedFrameworkId}
					class="px-3 py-1.5 rounded-lg border border-surface-200-800 bg-surface-100-900 text-xs font-medium text-surface-900-100 min-w-48"
				>
					<option value="">All Frameworks</option>
					{#each frameworks as fw}
						<option value={fw.id}>{fw.name}</option>
					{/each}
				</select>
			</div>
		</div>

		<div class="relative w-64">
			<input
				type="text"
				placeholder="Search reviewer tasks..."
				bind:value={searchQuery}
				class="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 placeholder-surface-400"
			/>
			<i class="fa-solid fa-magnifying-glass absolute left-2.5 top-2 text-[10px] text-surface-400"></i>
		</div>
	</div>

	<!-- Review List -->
	{#if loading}
		<div class="p-12 text-center text-surface-500 font-medium">Loading pending evidence reviews...</div>
	{:else if filteredReviews.length === 0}
		<div class="p-16 text-center border border-dashed border-surface-200-800 rounded-2xl bg-surface-50-950/50 space-y-3">
			<div class="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center mx-auto text-xl">
				<i class="fa-solid fa-check-double"></i>
			</div>
			<h4 class="text-base font-bold text-surface-900-100">No Task Assigned</h4>
			<p class="text-xs text-surface-500 max-w-sm mx-auto">
				There are currently no reviewer approval tasks assigned to your account for this view.
			</p>
		</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
			{#each filteredReviews as item}
				<div class="p-5 rounded-2xl border border-surface-200-800 bg-surface-50-950 shadow-xs space-y-4 flex flex-col justify-between">
					<div class="space-y-3">
						<div class="flex items-center justify-between">
							<span class="px-2.5 py-1 rounded-md bg-purple-500/10 text-purple-600 font-mono text-xs font-bold border border-purple-500/20">
								{item.control?.ref_id || 'N/A'}
							</span>
							{#if item.expiry_warning}
								<span class="inline-flex items-center gap-1 text-[11px] font-bold text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
									<i class="fa-solid fa-triangle-exclamation"></i> Expires Before Audit
								</span>
							{/if}
						</div>

						<div>
							<h4 class="font-bold text-sm text-surface-900-100">{item.title || item.control?.name}</h4>
							{#if item.control?.description}
								<p class="text-xs text-surface-500 mt-1">
									<strong class="text-surface-700-300">Control Description:</strong> {item.control.description}
								</p>
							{/if}
						</div>

						{#if item.requirement?.description || item.description}
							<div class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700-300 space-y-1">
								<span class="font-bold block flex items-center gap-1 text-amber-500">
									<i class="fa-solid fa-circle-info"></i> Requested Evidence Description (Webadmin Instructions):
								</span>
								<p>{item.requirement?.description || item.description}</p>
							</div>
						{/if}

						<div class="p-3 rounded-lg bg-surface-100-900/60 border border-surface-200-800/60 space-y-1.5 text-xs">
							<div class="flex items-center justify-between text-surface-600-400">
								<span>Submitted by (SPOC):</span>
								<span class="font-medium text-surface-900-100">{item.control?.spoc || 'N/A'}</span>
							</div>
							{#if item.assessment}
								<div class="flex items-center justify-between text-surface-600-400">
									<span>Audit / Period:</span>
									<span class="font-medium text-surface-900-100">{item.assessment.name} ({item.assessment.audit_period || 'N/A'})</span>
								</div>
							{/if}
							{#if item.expiry_date}
								<div class="flex items-center justify-between text-surface-600-400">
									<span>File Expiry Date:</span>
									<span class="font-medium {item.expiry_warning ? 'text-amber-500' : 'text-surface-900-100'}">{item.expiry_date}</span>
								</div>
							{/if}
						</div>

						{#if item.evidence_id || item.file_url}
							<a
								href={getAttachmentUrl(item)}
								target="_blank"
								class="inline-flex items-center gap-2 text-xs text-primary-500 hover:underline font-semibold"
							>
								<i class="fa-solid fa-paperclip"></i>
								<span>View Uploaded Document Attachment</span>
							</a>
						{/if}
					</div>

					<div class="flex items-center gap-3 pt-3 border-t border-surface-200-800">
						<button
							onclick={() => openReviewModal(item, 'REJECTED')}
							class="flex-1 py-2 px-3 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 font-semibold text-xs transition-all border border-rose-500/30 flex items-center justify-center gap-1.5 cursor-pointer"
						>
							<i class="fa-solid fa-xmark"></i>
							<span>Reject with Feedback</span>
						</button>
						<button
							onclick={() => openReviewModal(item, 'APPROVED')}
							class="flex-1 py-2 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs transition-all shadow-xs flex items-center justify-center gap-1.5 cursor-pointer"
						>
							<i class="fa-solid fa-check"></i>
							<span>Approve Evidence</span>
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Review Action Modal -->
	{#if selectedLink}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
			<div class="w-full max-w-lg bg-surface-50-950 rounded-2xl border border-surface-200-800 shadow-2xl p-6 space-y-5">
				<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
					<h3 class="text-lg font-bold text-surface-900-100">
						{actionType === 'APPROVED' ? 'Approve' : 'Reject'} Evidence: <span class="text-primary-500">{selectedLink.control?.ref_id || 'N/A'}</span>
					</h3>
					<button onclick={() => (selectedLink = null)} class="text-surface-400 hover:text-surface-900-100">
						<i class="fa-solid fa-xmark text-lg"></i>
					</button>
				</div>

				<div class="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
					{#if selectedLink.control?.description}
						<div class="p-3 rounded-xl bg-surface-100-900/80 border border-surface-200-800 text-xs space-y-1">
							<span class="font-bold text-surface-900-100 block">Control Description:</span>
							<p class="text-surface-600-400 leading-relaxed">{selectedLink.control.description}</p>
						</div>
					{/if}

					{#if selectedLink.requirement?.description || selectedLink.description}
						<div class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700-300 space-y-1">
							<span class="font-bold block flex items-center gap-1 text-amber-500">
								<i class="fa-solid fa-circle-info"></i> Requested Evidence Description (Webadmin Instructions):
							</span>
							<p class="leading-relaxed">{selectedLink.requirement?.description || selectedLink.description}</p>
						</div>
					{/if}

					{#if selectedLink.evidence_id || selectedLink.file_url}
						<div class="p-3 rounded-xl bg-surface-100-900/60 border border-surface-200-800 text-xs space-y-1">
							<span class="font-bold text-surface-900-100 block">Uploaded Evidence Attachment:</span>
							<a
								href={getAttachmentUrl(selectedLink)}
								target="_blank"
								class="inline-flex items-center gap-2 text-primary-500 hover:underline font-semibold"
							>
								<i class="fa-solid fa-paperclip"></i>
								<span>Open Uploaded File ({selectedLink.title})</span>
							</a>
						</div>
					{/if}

					{#if actionType === 'APPROVED'}
						<div class="space-y-1.5">
							<label class="text-xs font-semibold text-surface-700-300">Set Evidence Expiry Date (Optional)</label>
							<input
								type="date"
								bind:value={reviewerExpiryDate}
								class="w-full px-3 py-2 text-xs rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
							/>
							<p class="text-[11px] text-surface-500">
								Set by Reviewer upon approval to ensure evidence freshness for upcoming audits.
							</p>
						</div>
					{/if}

					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">
							Reviewer Feedback / Comments {actionType === 'REJECTED' ? '(Required)' : '(Optional)'}:
						</label>
						<textarea
							bind:value={feedback}
							rows="3"
							placeholder={actionType === 'REJECTED' ? 'State the reason for rejection so the SPOC can re-upload...' : 'Add approval notes if needed...'}
							class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						></textarea>
					</div>
				</div>

				{#if actionMessage}
					<div class="text-xs p-2.5 rounded-lg font-medium {actionMessage.includes('Approved') || actionMessage.includes('Rejected') ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'}">
						{actionMessage}
					</div>
				{/if}

				<div class="flex items-center justify-end gap-3 pt-3 border-t border-surface-200-800">
					<button
						onclick={() => (selectedLink = null)}
						class="px-4 py-2 text-xs font-medium rounded-lg border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800"
					>
						Cancel
					</button>
					<button
						onclick={handleReviewSubmit}
						disabled={submitting || (actionType === 'REJECTED' && !feedback.trim())}
						class="px-5 py-2 text-xs font-semibold rounded-lg text-white shadow-xs disabled:opacity-50 {actionType === 'APPROVED' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'}"
					>
						{submitting ? 'Submitting...' : `Confirm ${actionType === 'APPROVED' ? 'Approval' : 'Rejection'}`}
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>
