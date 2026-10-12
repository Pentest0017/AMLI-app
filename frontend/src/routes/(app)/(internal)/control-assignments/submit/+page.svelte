<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';
	import type { PageData } from './$types';

	pageTitle.set('SPOC Evidence Submission');

	let { data }: { data: PageData } = $props();

	let loading = $state(false);
	let myControls = $state<any[]>(data?.myControls || []);
	let selectedControl = $state<any>(null);
	let selectedRequirement = $state<any>(null);

	let searchQuery = $state('');
	let selectedFrameworkId = $state('');
	let frameworks = $state<any[]>(data?.frameworks || []);

	$effect(() => {
		const c = data?.myControls || [];
		const fw = data?.frameworks || [];
		untrack(() => {
			myControls = c;
			frameworks = fw;
		});
	});

	const user = $derived(data?.currentUser);
	const isSuperOrWebAdmin = $derived(
		user?.is_superuser ||
		user?.platform_role === 'superadmin' ||
		user?.platform_role === 'webadmin'
	);
	const canReview = $derived(
		user?.is_superuser ||
		user?.platform_role === 'superadmin' ||
		user?.platform_role === 'webadmin' ||
		user?.platform_role === 'admin'
	);

	const filteredControls = $derived(
		myControls.filter((c) => {
			const matchesSearch =
				!searchQuery ||
				c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.ref_id?.toLowerCase().includes(searchQuery.toLowerCase());
			const matchesFw = !selectedFrameworkId || c.framework_id === selectedFrameworkId;
			return matchesSearch && matchesFw;
		})
	);

	// Submission Form Fields for Selected Requirement
	let fileName = $state('');
	let versionStr = $state('1.0');
	let expiryDate = $state('');
	let fileInput = $state<HTMLInputElement | null>(null);
	let uploading = $state(false);
	let uploadMessage = $state('');

	async function loadMyControls() {
		// Authoritative controls already loaded via server-side load function
	}

	function openRequirementUploadModal(control: any, requirement: any) {
		selectedControl = control;
		selectedRequirement = requirement;
		fileName = `Evidence for ${control.ref_id} - ${requirement.name}`;
		versionStr = '1.0';
		expiryDate = '';
		uploadMessage = '';
		uploading = false;
	}

	function closeModal() {
		selectedControl = null;
		selectedRequirement = null;
		uploadMessage = '';
		uploading = false;
	}

	onMount(() => {
		loadMyControls();
	});

	async function handleUpload() {
		if (!selectedControl || !selectedRequirement || !fileInput?.files?.[0]) {
			uploadMessage = 'Please select a file attachment to upload.';
			return;
		}

		if (!fileName.trim()) {
			uploadMessage = 'Please provide an evidence file name.';
			return;
		}

		uploading = true;
		uploadMessage = '';

		const formData = new FormData();
		formData.append('control_assignment_id', selectedControl.assignment.id);
		formData.append('evidence_requirement_id', selectedRequirement.id);
		formData.append('title', fileName.trim());
		formData.append('version', versionStr.trim() || '1.0');
		formData.append('description', selectedRequirement.description || '');
		formData.append('file', fileInput.files[0]);

		try {
			const res = await fetch('?/submitEvidence', {
				method: 'POST',
				body: formData
			});

			const result = await res.json();
			let dataResult = result;
			if (typeof result.data === 'string') {
				try {
					dataResult = JSON.parse(result.data);
				} catch (e) {}
			} else if (result.data) {
				dataResult = result.data;
			}

			if (res.ok && (dataResult.success || dataResult[0]?.success || dataResult.status === 'success')) {
				const linkData = {
					title: fileName.trim(),
					version: versionStr.trim() || '1.0',
					review_status: 'PENDING_REVIEW',
					reviewer_feedback: null
				};
				if (selectedRequirement && selectedRequirement.id) {
					selectedRequirement.latest_link = linkData;
				} else if (selectedControl && selectedControl.assignment) {
					selectedControl.assignment.latest_general_link = linkData;
				}
				uploadMessage = 'Evidence submitted successfully for review!';
				setTimeout(async () => {
					closeModal();
					await loadMyControls();
				}, 600);
			} else {
				uploadMessage = dataResult.error || dataResult[0]?.error || 'Failed to submit evidence.';
				uploading = false;
			}
		} catch (err) {
			uploadMessage = 'Network error during upload.';
			uploading = false;
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
				class="px-4 py-2 rounded-lg bg-amber-600 text-white font-semibold text-sm shadow-xs flex items-center gap-2"
			>
				<i class="fa-solid fa-cloud-arrow-up"></i>
				<span>SPOC Submission</span>
			</a>
			{#if canReview}
				<a
					href="/control-assignments/review"
					class="px-4 py-2 rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-700-300 hover:bg-surface-200-800 text-sm font-medium transition-all flex items-center gap-2"
				>
					<i class="fa-solid fa-clipboard-check text-emerald-500"></i>
					<span>Reviewer Approval</span>
				</a>
			{/if}
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
				placeholder="Search SPOC tasks..."
				bind:value={searchQuery}
				class="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 placeholder-surface-400"
			/>
			<i class="fa-solid fa-magnifying-glass absolute left-2.5 top-2 text-[10px] text-surface-400"></i>
		</div>
	</div>

	<!-- SPOC Controls Grid -->
	{#if loading}
		<div class="p-12 text-center text-surface-500 font-medium">Loading your assigned controls...</div>
	{:else if filteredControls.length === 0}
		<div class="p-16 text-center border border-dashed border-surface-200-800 rounded-2xl bg-surface-50-950/50 space-y-3">
			<div class="w-12 h-12 rounded-full bg-amber-500/10 text-amber-500 flex items-center justify-center mx-auto text-xl">
				<i class="fa-solid fa-clipboard-check"></i>
			</div>
			<h4 class="text-base font-bold text-surface-900-100">No Task Assigned</h4>
			<p class="text-xs text-surface-500 max-w-sm mx-auto">
				There are currently no SPOC evidence submission tasks assigned to your account for this view.
			</p>
		</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
			{#each filteredControls as control}
				<div class="p-5 rounded-2xl border border-surface-200-800 bg-surface-50-950 shadow-xs flex flex-col justify-between space-y-4">
					<div class="space-y-3">
						<div class="flex items-center justify-between">
							<span class="px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-600 font-mono text-xs font-bold border border-amber-500/20">
								{control.ref_id}
							</span>
							<span class="text-[11px] font-medium text-surface-500 truncate max-w-36">{control.framework_name}</span>
						</div>

						<div>
							<h4 class="font-bold text-sm text-surface-900-100">{control.name}</h4>
							{#if control.description}
								<p class="text-xs text-surface-500 mt-1 line-clamp-2" title={control.description}>
									<strong class="text-surface-700-300">Control Description:</strong> {control.description}
								</p>
							{/if}
						</div>

						<!-- Requirements List with Dedicated Buttons -->
						{#if control.assignment?.evidence_requirements?.length > 0}
							<div class="pt-2 space-y-3 border-t border-surface-200-800/60">
								<span class="text-[11px] font-bold text-surface-500 uppercase tracking-wider block">Requested Evidence Requirements:</span>
								{#each control.assignment.evidence_requirements as req}
									<div class="p-3 rounded-xl bg-surface-100-900/60 border border-surface-200-800 space-y-2">
										<div class="flex items-center justify-between gap-2">
											<span class="font-semibold text-xs text-surface-900-100 flex items-center gap-1.5 min-w-0 truncate">
												<i class="fa-solid fa-file-lines text-amber-500 text-xs shrink-0"></i>
												<span class="truncate">{req.name}</span>
											</span>
											{#if req.is_mandatory}
												<span class="text-[10px] text-rose-500 font-bold bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20 shrink-0">*Required</span>
											{/if}
										</div>

										{#if req.description}
											<p class="text-[11px] text-surface-600-400">
												<strong class="text-amber-500">Evidence Description:</strong> {req.description}
											</p>
										{/if}

										{#if req.latest_link}
											<div class="p-2 rounded-lg bg-surface-200-800/40 border border-surface-200-800 text-xs space-y-1">
												<div class="flex items-center justify-between">
													<span class="font-semibold text-surface-900-100 truncate">{req.latest_link.title} (v{req.latest_link.version})</span>
													{#if req.latest_link.review_status === 'APPROVED'}
														<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">Approved</span>
													{:else if req.latest_link.review_status === 'REJECTED'}
														<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20">Rejected</span>
													{:else}
														<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">Pending Review</span>
													{/if}
												</div>
												{#if req.latest_link.file_url}
													<a
														href={req.latest_link.file_url}
														target="_blank"
														class="inline-flex items-center gap-1 text-[11px] text-primary-500 hover:underline font-medium"
													>
														<i class="fa-solid fa-download"></i> View / Download Attachment
													</a>
												{/if}
												{#if req.latest_link.reviewer_feedback}
													<p class="text-[11px] text-surface-500 italic">Feedback: {req.latest_link.reviewer_feedback}</p>
												{/if}
											</div>
										{/if}

										<button
											onclick={() => openRequirementUploadModal(control, req)}
											class="w-full py-1.5 px-3 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs transition-all shadow-xs flex items-center justify-center gap-1.5 cursor-pointer mt-1"
										>
											<i class="fa-solid fa-upload text-[11px]"></i>
											<span>{req.latest_link ? 'Re-upload / Update Evidence' : `Submit Evidence for ${req.name}`}</span>
										</button>
									</div>
								{/each}
							</div>
						{/if}

						<!-- General Evidence Section for Controls -->
						<div class="pt-2 space-y-2 border-t border-surface-200-800/60">
							<span class="text-[11px] font-bold text-surface-500 uppercase tracking-wider block">General Evidence Document:</span>
							{#if control.assignment?.latest_general_link}
								<div class="p-3 rounded-xl bg-surface-100-900/60 border border-surface-200-800 space-y-2">
									<div class="flex items-center justify-between gap-2">
										<span class="font-semibold text-xs text-surface-900-100 flex items-center gap-1.5 min-w-0 truncate">
											<i class="fa-solid fa-paperclip text-amber-500 text-xs shrink-0"></i>
											<span class="truncate">{control.assignment.latest_general_link.title} (v{control.assignment.latest_general_link.version})</span>
										</span>
										{#if control.assignment.latest_general_link.review_status === 'APPROVED'}
											<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">Approved</span>
										{:else if control.assignment.latest_general_link.review_status === 'REJECTED'}
											<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20">Rejected</span>
										{:else}
											<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">Pending Review</span>
										{/if}
									</div>
									{#if control.assignment.latest_general_link.file_url}
										<a
											href={control.assignment.latest_general_link.file_url}
											target="_blank"
											class="inline-flex items-center gap-1 text-[11px] text-primary-500 hover:underline font-medium"
										>
											<i class="fa-solid fa-download"></i> View / Download Attachment
										</a>
									{/if}
									{#if control.assignment.latest_general_link.reviewer_feedback}
										<p class="text-[11px] text-surface-500 italic">Feedback: {control.assignment.latest_general_link.reviewer_feedback}</p>
									{/if}
								</div>
							{/if}

							<button
								onclick={() => openRequirementUploadModal(control, { id: '', name: 'General Evidence', description: control.description })}
								class="w-full py-2 px-4 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer mt-1"
							>
								<i class="fa-solid fa-upload"></i>
								<span>{control.assignment?.latest_general_link ? 'Re-upload / Update General Evidence' : 'Submit General Evidence'}</span>
							</button>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Dedicated Requirement Upload Modal -->
	{#if selectedControl && selectedRequirement}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
			<div class="w-full max-w-lg bg-surface-50-950 rounded-2xl border border-surface-200-800 shadow-2xl p-6 space-y-5">
				<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
					<div>
						<h3 class="text-base font-bold text-surface-900-100 flex items-center gap-2">
							<span class="px-2 py-0.5 rounded font-mono text-xs bg-amber-500/10 text-amber-500 border border-amber-500/20">{selectedControl.ref_id}</span>
							<span>Submit Evidence: {selectedRequirement.name}</span>
						</h3>
						<p class="text-xs text-surface-500 mt-1">{selectedControl.name}</p>
					</div>
					<button onclick={closeModal} class="text-surface-400 hover:text-surface-900-100 p-1">
						<i class="fa-solid fa-xmark text-lg"></i>
					</button>
				</div>

				<div class="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
					<!-- Requirement Description (Webadmin Instructions) -->
					{#if selectedRequirement.description}
						<div class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700-300 space-y-1">
							<span class="font-bold block flex items-center gap-1.5 text-amber-500">
								<i class="fa-solid fa-circle-info"></i> Requested Evidence Description:
							</span>
							<p class="leading-relaxed">{selectedRequirement.description}</p>
						</div>
					{/if}

					<!-- Reviewer Rejection / Feedback Banner (If Evidence Was Previously Rejected or Has Reviewer Notes) -->
					{#if selectedRequirement.latest_link && selectedRequirement.latest_link.review_status === 'REJECTED'}
						<div class="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs space-y-2">
							<div class="flex items-center justify-between">
								<span class="font-bold text-rose-600 flex items-center gap-1.5 text-xs">
									<i class="fa-solid fa-circle-xmark text-sm"></i> Evidence Rejected by Reviewer
								</span>
								{#if selectedRequirement.latest_link.reviewed_by}
									<span class="text-[11px] text-surface-500 font-mono">Reviewer: {selectedRequirement.latest_link.reviewed_by}</span>
								{/if}
							</div>
							<div class="p-2.5 rounded-lg bg-surface-100-900/80 border border-surface-200-800 text-surface-900-100">
								<span class="font-bold text-surface-700-300 block text-[11px] mb-0.5">Reviewer Feedback / Comments:</span>
								<p class="text-xs text-rose-500 leading-relaxed font-medium">
									{selectedRequirement.latest_link.reviewer_feedback || 'No comments provided by reviewer.'}
								</p>
							</div>
							<p class="text-[11px] text-surface-500">
								Please upload an updated evidence document addressing the reviewer's feedback.
							</p>
						</div>
					{:else if selectedRequirement.latest_link && selectedRequirement.latest_link.reviewer_feedback}
						<div class="p-3.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-xs space-y-2">
							<div class="flex items-center justify-between">
								<span class="font-bold text-purple-500 flex items-center gap-1.5">
									<i class="fa-solid fa-comment-dots"></i> Reviewer Feedback ({selectedRequirement.latest_link.review_status})
								</span>
								{#if selectedRequirement.latest_link.reviewed_by}
									<span class="text-[11px] text-surface-500 font-mono">{selectedRequirement.latest_link.reviewed_by}</span>
								{/if}
							</div>
							<p class="text-xs text-surface-900-100 leading-relaxed p-2 rounded-lg bg-surface-100-900/60 border border-surface-200-800">
								{selectedRequirement.latest_link.reviewer_feedback}
							</p>
						</div>
					{/if}

					<!-- Input 1: Evidence File Name -->
					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">File Name / Evidence Title *</label>
						<input
							type="text"
							bind:value={fileName}
							placeholder="Enter evidence document title"
							class="w-full px-3 py-2 text-xs rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100"
						/>
					</div>

					<!-- Input 2: Version -->
					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">Document Version *</label>
						<input
							type="text"
							bind:value={versionStr}
							placeholder="e.g. 1.0"
							class="w-full px-3 py-2 text-xs rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 font-mono"
						/>
					</div>

					<!-- Input 3: File Attachment -->
					<div class="space-y-1.5">
						<label class="text-xs font-semibold text-surface-700-300">Upload File Attachment *</label>
						<input
							type="file"
							bind:this={fileInput}
							class="w-full text-xs text-surface-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-amber-500/10 file:text-amber-600 hover:file:bg-amber-500/20 cursor-pointer"
						/>
					</div>
				</div>

				{#if uploadMessage}
					<div class="text-xs p-3 rounded-lg font-medium {uploadMessage.includes('successfully') ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border border-rose-500/20'}">
						{uploadMessage}
					</div>
				{/if}

				<div class="flex items-center justify-end gap-3 pt-3 border-t border-surface-200-800">
					<button
						onclick={closeModal}
						class="px-4 py-2 text-xs font-medium rounded-lg border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800"
					>
						Cancel
					</button>
					<button
						onclick={handleUpload}
						disabled={uploading}
						class="px-5 py-2 text-xs font-semibold rounded-lg bg-amber-600 hover:bg-amber-700 text-white shadow-xs disabled:opacity-50 flex items-center gap-1.5"
					>
						<i class="fa-solid fa-paper-plane text-[11px]"></i>
						<span>{uploading ? 'Uploading...' : 'Submit Evidence'}</span>
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>
