<script lang="ts">
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import { page } from '$app/stores';

	interface ReportItem {
		id: string;
		title: string;
		file_path: string;
		compliance_status: 'COMPLIANT' | 'NON_COMPLIANT';
		approval_status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED';
		submitted_by?: string;
		approved_by?: string;
		reviewer_feedback?: string;
		expiry_date?: string;
		created_at?: string;
	}

	interface FolderNode {
		id: string;
		name: string;
		description: string;
		folder_type: 'ROOT' | 'YEAR' | 'DOMAIN' | 'PARTNER';
		parent?: string;
		children?: FolderNode[];
		reports?: ReportItem[];
	}

	interface ClipboardItem {
		id: string;
		name: string;
		type: 'FOLDER' | 'FILE';
		folder_type?: string;
		mode: 'CUT' | 'COPY';
	}

	let { data } = $props();

	let treeData: FolderNode | null = $derived(data.treeData ?? null);

	// Navigation & selection state tracking by ID
	let activeFolderId: string | null = $state(null);
	let selectedItemId: string | null = $state(null);
	let selectedItemType: 'FOLDER' | 'FILE' = $state('FOLDER');

	// Clipboard state
	let clipboard: ClipboardItem | null = $state(null);

	// Modal State
	let showNewModal = $state(false);
	let modalMode: 'FOLDER' | 'FILE' = $state('FOLDER');
	let newFolderType: 'YEAR' | 'DOMAIN' | 'PARTNER' = $state('YEAR');
	let newItemName = $state('');
	let newItemFilePath = $state('');
	let newItemComplianceStatus: 'COMPLIANT' | 'NON_COMPLIANT' = $state('COMPLIANT');
	let newItemExpiryDate = $state('');
	let modalErrorMsg = $state('');
	let isSubmitting = $state(false);
	let selectedFileObj: File | null = $state(null);

	// Review Modal
	let showReviewModal = $state(false);
	let selectedReportForReview: ReportItem | null = $state(null);
	let reviewFeedback = $state('');

	// In-App Delete Confirm Modal State
	let showDeleteConfirmModal = $state(false);

	let pendingDomainIds: string[] = $state([]);
	let pendingPartnerIds: string[] = $state([]);
	let pendingYearIds: string[] = $state([]);
	let pendingFolderIds: string[] = $state([]);

	async function fetchPendingStatus() {
		try {
			const res = await fetch('/api/intermediary-compliance/pending-status/', { credentials: 'include' });
			if (res.ok) {
				const resData = await res.json();
				pendingDomainIds = resData.pending_domain_ids || [];
				pendingPartnerIds = resData.pending_partner_ids || [];
				pendingYearIds = resData.pending_year_ids || [];
				pendingFolderIds = resData.pending_folder_ids || [];
			}
		} catch (e) {
			console.error('Error fetching pending status:', e);
		}
	}

	let pendingSet = $derived(
		new Set([...pendingFolderIds, ...pendingDomainIds, ...pendingPartnerIds, ...pendingYearIds])
	);

	function isFolderPending(id: string): boolean {
		return pendingSet.has(id);
	}

	$effect(() => {
		fetchPendingStatus();
		const folderIdParam = $page.url.searchParams.get('folder_id');
		if (folderIdParam && treeData) {
			const targetNode = findFolderById(treeData, folderIdParam);
			if (targetNode) {
				activeFolderId = targetNode.id;
				selectedItemId = targetNode.id;
				selectedItemType = 'FOLDER';
			}
		}
	});

	function findFolderById(node: FolderNode, id: string): FolderNode | null {
		if (node.id === id) return node;
		for (const child of node.children || []) {
			const found = findFolderById(child, id);
			if (found) return found;
		}
		return null;
	}

	function findReportById(node: FolderNode, id: string): ReportItem | null {
		for (const rep of node.reports || []) {
			if (rep.id === id) return rep;
		}
		for (const child of node.children || []) {
			const found = findReportById(child, id);
			if (found) return found;
		}
		return null;
	}

	// Svelte 5 derived state
	let activeFolder: FolderNode | null = $derived.by(() => {
		if (!treeData) return null;
		if (!activeFolderId) return treeData;
		return findFolderById(treeData, activeFolderId) || treeData;
	});

	let selectedItem = $derived.by(() => {
		if (!treeData || !selectedItemId) return null;
		if (selectedItemType === 'FOLDER') {
			const folder = findFolderById(treeData, selectedItemId);
			return folder ? { id: folder.id, name: folder.name, type: 'FOLDER' as const, node: folder } : null;
		}
		const report = findReportById(treeData, selectedItemId);
		return report ? { id: report.id, name: report.title, type: 'FILE' as const, report } : null;
	});

	function selectFolder(folder: FolderNode) {
		selectedItemId = folder.id;
		selectedItemType = 'FOLDER';
	}

	function selectReport(report: ReportItem) {
		selectedItemId = report.id;
		selectedItemType = 'FILE';
	}

	function navigateInto(folder: FolderNode) {
		activeFolderId = folder.id;
		selectedItemId = folder.id;
		selectedItemType = 'FOLDER';
	}

	function getBreadcrumbPath(root: FolderNode | null, targetId: string): FolderNode[] {
		if (!root) return [];
		const path: FolderNode[] = [];
		function search(node: FolderNode): boolean {
			path.push(node);
			if (node.id === targetId) return true;
			for (const child of node.children || []) {
				if (search(child)) return true;
			}
			path.pop();
			return false;
		}
		search(root);
		return path;
	}

	function openNewFolderModal() {
		const current = activeFolder || treeData;
		modalMode = 'FOLDER';
		newItemName = '';
		modalErrorMsg = '';

		if (!current || current.folder_type === 'ROOT') {
			newFolderType = 'YEAR';
		} else if (current.folder_type === 'YEAR') {
			newFolderType = 'DOMAIN';
		} else {
			newFolderType = 'PARTNER';
		}

		showNewModal = true;
	}

	function openUploadFileModal() {
		modalMode = 'FILE';
		newItemName = '';
		newItemFilePath = '';
		selectedFileObj = null;
		newItemComplianceStatus = 'COMPLIANT';
		newItemExpiryDate = '';
		modalErrorMsg = '';
		showNewModal = true;
	}

	function handleFileChange(event: Event) {
		const input = event.target as HTMLInputElement;
		if (input.files && input.files[0]) {
			const file = input.files[0];
			selectedFileObj = file;
			newItemFilePath = file.name;
			if (!newItemName.trim()) {
				newItemName = file.name.replace(/\.[^/.]+$/, '');
			}
		}
	}

	function handleCut() {
		if (!selectedItem) return;
		clipboard = { id: selectedItem.id, name: selectedItem.name, type: selectedItem.type, mode: 'CUT' };
	}

	function handleCopy() {
		if (!selectedItem) return;
		clipboard = { id: selectedItem.id, name: selectedItem.name, type: selectedItem.type, mode: 'COPY' };
	}

	let reviewComplianceStatus: 'COMPLIANT' | 'NON_COMPLIANT' = $state('COMPLIANT');
	let reviewExpiryDate = $state('');
	let reviewErrorMsg = $state('');
	let isReviewAllowed = $state(true);

	function isUserAllowedToReview(report: ReportItem): boolean {
		const currentUser = data?.user;
		if (!currentUser) return true;
		if (currentUser.is_superuser || currentUser.platform_role === 'superadmin' || currentUser.platform_role === 'webadmin') {
			return true;
		}
		if (currentUser.platform_role === 'admin' || currentUser.is_admin) {
			let domainFolder = activeFolder;
			while (domainFolder && domainFolder.folder_type !== 'DOMAIN' && domainFolder.parent) {
				domainFolder = findFolderById(treeData!, domainFolder.parent);
			}
			if (domainFolder && (domainFolder as any).assignments?.approving_admins) {
				const approvers = (domainFolder as any).assignments.approving_admins;
				if (approvers && approvers.length > 0) {
					return approvers.some(
						(u: any) => u.id === currentUser.id || u.email?.toLowerCase() === currentUser.email?.toLowerCase()
					);
				}
			}
			return true;
		}
		return false;
	}

	const canManageRepository = $derived(
		Boolean(
			data.currentUser?.is_superuser ||
			data.currentUser?.is_admin ||
			['superadmin', 'webadmin', 'admin'].includes(data.currentUser?.platform_role)
		)
	);

	function openReviewModal(report: ReportItem) {
		reviewErrorMsg = '';
		isReviewAllowed = isUserAllowedToReview(report);
		if (!isReviewAllowed) {
			reviewErrorMsg = 'Review access restricted: Only assigned Approving Admins (Reviewers), Web Admins, and Superadmins can submit reviews.';
		}
		selectedReportForReview = report;
		reviewFeedback = report.reviewer_feedback || '';
		reviewComplianceStatus = report.compliance_status || 'COMPLIANT';
		reviewExpiryDate = report.expiry_date || '';
		showReviewModal = true;
	}

	async function handleReviewSubmit(actionType: 'APPROVE' | 'REJECT') {
		if (!selectedReportForReview || !isReviewAllowed) return;
		reviewErrorMsg = '';
		try {
			let token = '';
			if (typeof document !== 'undefined') {
				const match = document.cookie.match(/csrftoken=([^;]+)/);
				if (match) token = match[1];
			}
			if (!token) {
				try {
					const csrfRes = await fetch('/api/csrf/', { credentials: 'include' });
					if (csrfRes.ok) {
						const csrfData = await csrfRes.json();
						token = csrfData.csrfToken || '';
					}
				} catch (e) {}
			}

			const headers: Record<string, string> = { 'Content-Type': 'application/json' };
			if (token) headers['X-CSRFToken'] = token;

			const res = await fetch(`/intermediary-compliance/repository/${selectedReportForReview.id}/review`, {
				method: 'POST',
				headers,
				credentials: 'include',
				body: JSON.stringify({
					action: actionType,
					feedback: reviewFeedback,
					compliance_status: actionType === 'APPROVE' ? 'COMPLIANT' : 'NON_COMPLIANT',
					expiry_date: reviewExpiryDate || null
				})
			});
			if (res.ok) {
				showReviewModal = false;
				await invalidateAll();
			} else {
				let errText = 'Failed to submit review';
				try {
					const err = await res.json();
					errText = err.error || errText;
				} catch (e) {}
				reviewErrorMsg = errText;
			}
		} catch (err: any) {
			reviewErrorMsg = err.message || 'Error submitting review';
		}
	}
</script>

<div class="p-6 space-y-6">
	<!-- Page Header & Top Right Function Toolbar -->
	<div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
		<div>
			<h1 class="text-2xl font-bold text-surface-900-100">Report Repository</h1>
			<p class="text-xs text-surface-600-400">
				Hierarchical Structure: <code>Report Repository</code> &rarr; <code>Year</code> &rarr; <code>Business Functions</code> &rarr; <code>Partner</code> &rarr; <code>Subfolders / Reports</code>.
			</p>
		</div>

		<!-- Top Right Action Toolbar -->
		<div class="flex flex-wrap items-center gap-2 bg-surface-100-900 p-2 rounded-container border border-surface-200-800 shadow-sm">
			{#if clipboard}
				<div class="flex items-center gap-1.5 px-3 py-1 bg-primary-500/10 text-primary-500 text-xs font-semibold rounded border border-primary-500/20 mr-2">
					<i class={clipboard.mode === 'CUT' ? 'fa-solid fa-scissors' : 'fa-solid fa-copy'}></i>
					<span>{clipboard.mode}: {clipboard.name}</span>
					<button class="hover:text-error-500 ml-1 cursor-pointer" onclick={() => (clipboard = null)} title="Clear Clipboard">&times;</button>
				</div>
			{/if}

			<button
				class="btn btn-sm variant-filled-primary font-semibold flex items-center gap-1.5 cursor-pointer"
				onclick={openNewFolderModal}
				title="Create New Folder in Current Location"
			>
				<i class="fa-solid fa-folder-plus"></i>
				<span>+ New Folder</span>
			</button>

			<button
				class="btn btn-sm variant-filled-tertiary font-semibold flex items-center gap-1.5 cursor-pointer"
				onclick={openUploadFileModal}
				title="Upload Report File to Current Location"
			>
				<i class="fa-solid fa-file-arrow-up"></i>
				<span>+ Upload File</span>
			</button>

			<button
				class="btn btn-sm variant-soft-secondary flex items-center gap-1.5 disabled:opacity-40 cursor-pointer"
				disabled={!selectedItem}
				onclick={handleCut}
				title="Cut Selected Item"
			>
				<i class="fa-solid fa-scissors"></i>
				<span>Cut</span>
			</button>

			<button
				class="btn btn-sm variant-soft-secondary flex items-center gap-1.5 disabled:opacity-40 cursor-pointer"
				disabled={!selectedItem}
				onclick={handleCopy}
				title="Copy Selected Item"
			>
				<i class="fa-solid fa-copy"></i>
				<span>Copy</span>
			</button>

			{#if clipboard && activeFolder}
				<form
					action="?/copyPaste"
					method="POST"
					use:enhance={() => {
						return async ({ result }) => {
							if (result.type === 'success') {
								clipboard = null;
								await invalidateAll();
							}
						};
					}}
				>
					<input type="hidden" name="id" value={clipboard.id} />
					<input type="hidden" name="type" value={clipboard.type} />
					<input type="hidden" name="target_id" value={activeFolder.id} />
					<input type="hidden" name="mode" value={clipboard.mode} />
					<button class="btn btn-sm variant-soft-success flex items-center gap-1.5 cursor-pointer" type="submit">
						<i class="fa-solid fa-paste"></i>
						<span>Paste</span>
					</button>
				</form>
			{:else}
				<button class="btn btn-sm variant-soft-success flex items-center gap-1.5 disabled:opacity-40" disabled>
					<i class="fa-solid fa-paste"></i>
					<span>Paste</span>
				</button>
			{/if}

			{#if selectedItem}
				<button
					class="btn btn-sm variant-soft-error flex items-center gap-1.5 cursor-pointer"
					type="button"
					onclick={() => (showDeleteConfirmModal = true)}
				>
					<i class="fa-solid fa-trash"></i>
					<span>Delete</span>
				</button>
			{:else}
				<button class="btn btn-sm variant-soft-error flex items-center gap-1.5 disabled:opacity-40" disabled>
					<i class="fa-solid fa-trash"></i>
					<span>Delete</span>
				</button>
			{/if}

			<div class="h-5 w-px bg-surface-300-700 mx-1"></div>

			<button class="btn btn-sm variant-filled-surface flex items-center gap-1.5 cursor-pointer" onclick={() => invalidateAll()} title="Refresh Repository">
				<i class="fa-solid fa-rotate-right"></i>
				<span>Refresh</span>
			</button>
		</div>
	</div>

	<!-- Breadcrumb Path Bar -->
	{#if treeData && activeFolder}
		<div class="flex items-center space-x-2 text-sm card p-3 variant-soft-surface">
			<i class="fa-solid fa-folder-tree text-primary-500 mr-1"></i>
			{#each getBreadcrumbPath(treeData, activeFolder.id) as step, idx}
				{#if idx > 0}<span class="text-surface-400">&gt;</span>{/if}
				<button
					class="font-medium hover:underline text-surface-900-100 flex items-center gap-1 cursor-pointer"
					onclick={() => navigateInto(step)}
				>
					<span>{step.name}</span>
					<span class="badge variant-soft text-xs">{step.folder_type}</span>
				</button>
			{/each}
		</div>
	{/if}

	{#if treeData && treeData.children && treeData.children.length > 0 && activeFolder}
		<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
			<!-- Left: Full Folder Tree View -->
			<div class="card p-4 shadow-md bg-surface-50-950 space-y-3 lg:col-span-1 border border-surface-200-800">
				<h2 class="text-sm font-bold uppercase tracking-wider text-surface-600-400 border-b border-surface-200-800 pb-2">
					Folder Hierarchy
				</h2>

				<div class="space-y-1 max-h-[600px] overflow-y-auto pr-1">
					{#snippet renderTreeNode(node: FolderNode, level: number, pSet: Set<string>)}
						<div
							class="flex items-center justify-between p-2 rounded cursor-pointer transition-colors text-sm hover:bg-surface-200-800
							{selectedItemId === node.id ? 'ring-2 ring-primary-500 bg-primary-500/10 font-bold' : ''}
							{activeFolderId === node.id || (!activeFolderId && node.folder_type === 'ROOT') ? 'bg-surface-200-800' : ''}"
							style="padding-left: {level * 16 + 8}px;"
							onclick={() => selectFolder(node)}
							ondblclick={() => navigateInto(node)}
						>
							<div class="flex items-center space-x-2 truncate">
								{#if node.folder_type === 'ROOT'}
									<i class="fa-solid fa-folder-tree text-amber-500"></i>
								{:else if node.folder_type === 'YEAR'}
									<i class="fa-solid fa-folder text-amber-500"></i>
								{:else if node.folder_type === 'DOMAIN'}
									<i class="fa-solid fa-folder-open text-primary-500"></i>
								{:else}
									<i class="fa-solid fa-building text-tertiary-500"></i>
								{/if}
								<span class="truncate">{node.name}</span>
								{#if pSet.has(node.id)}
									<span class="ml-1 inline-flex h-2.5 w-2.5 relative" title="Pending Action Required">
										<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-error-400 opacity-75"></span>
										<span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-error-500"></span>
									</span>
								{/if}
							</div>
							<span class="text-xs text-surface-400 font-mono">({node.children?.length || 0})</span>
						</div>

						{#each node.children || [] as child}
							{@render renderTreeNode(child, level + 1, pSet)}
						{/each}
					{/snippet}

					{@render renderTreeNode(treeData, 0, pendingSet)}
				</div>
			</div>

			<!-- Right: Active Directory Explorer View -->
			<div class="card p-6 shadow-md bg-surface-50-950 space-y-6 lg:col-span-3 border border-surface-200-800">
				<div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-surface-200-800 pb-3">
					<div>
						<h2 class="text-lg font-bold flex items-center gap-2">
							<i class="fa-solid fa-folder-open text-primary-500"></i>
							<span>{activeFolder.name}</span>
							<span class="badge variant-soft-primary text-xs">{activeFolder.folder_type}</span>
						</h2>
						<p class="text-xs text-surface-500">{activeFolder.description || 'Single click items to select for Cut/Copy/Delete.'}</p>
					</div>

					<!-- Folder Specific Actions -->
					{#if canManageRepository}
						<div class="flex items-center gap-2">
							<button class="btn btn-sm variant-soft-primary text-xs cursor-pointer" onclick={openNewFolderModal}>
								<i class="fa-solid fa-folder-plus mr-1"></i> + New Subfolder
							</button>
							<button class="btn btn-sm variant-soft-tertiary text-xs cursor-pointer" onclick={openUploadFileModal}>
								<i class="fa-solid fa-file-circle-plus mr-1"></i> + Add Report File
							</button>
						</div>
					{/if}
				</div>

				<!-- Subfolders Section (Enabled in ALL Folders) -->
				<div class="space-y-3">
					<div class="flex justify-between items-center">
						<h3 class="text-xs font-bold uppercase tracking-wider text-surface-600-400">
							Subfolders ({activeFolder.children?.length || 0})
						</h3>
					</div>

					{#if (activeFolder.children || []).length > 0}
						<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
							{#each activeFolder.children || [] as child}
								<div
									class="card p-3 cursor-pointer border transition-all hover:border-primary-500 flex items-center justify-between
									{selectedItemId === child.id ? 'ring-2 ring-primary-500 bg-primary-500/10' : 'bg-surface-100-900 border-surface-200-800'}"
									onclick={() => selectFolder(child)}
									ondblclick={() => navigateInto(child)}
								>
									<div class="flex items-center space-x-3 truncate">
										<i class="fa-solid fa-folder text-2xl text-amber-500"></i>
										<div class="truncate">
											<p class="font-semibold text-sm truncate flex items-center gap-1.5">
												<span>{child.name}</span>
												{#if isFolderPending(child.id)}
													<span class="ml-1 inline-flex h-2.5 w-2.5 relative" title="Pending Action Required">
														<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-error-400 opacity-75"></span>
														<span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-error-500"></span>
													</span>
												{/if}
											</p>
											<p class="text-xs text-surface-400">{child.folder_type}</p>
										</div>
									</div>
									<button class="btn btn-sm variant-soft cursor-pointer" onclick={(e) => { e.stopPropagation(); navigateInto(child); }}>
										<i class="fa-solid fa-arrow-right text-xs"></i>
									</button>
								</div>
							{/each}
						</div>
					{:else}
						<div class="p-4 text-center border border-dashed border-surface-300-700 rounded text-xs text-surface-500">
							No subfolders in this location.
						</div>
					{/if}
				</div>

				<!-- Reports / Files Section (Enabled in ALL Folders) -->
				<div class="space-y-3 pt-4 border-t border-surface-200-800">
					<div class="flex justify-between items-center">
						<h3 class="text-xs font-bold uppercase tracking-wider text-surface-600-400">
							Reports / Files ({activeFolder.reports?.length || 0})
						</h3>
					</div>

					{#if (activeFolder.reports || []).length > 0}
						<div class="space-y-2">
							{#each activeFolder.reports || [] as report}
								<div
									class="flex items-center justify-between p-3 rounded border transition-all cursor-pointer
									{selectedItemId === report.id ? 'ring-2 ring-primary-500 bg-primary-500/10' : 'bg-surface-100-900 border-surface-200-800'}"
									onclick={() => selectReport(report)}
								>
									<div class="flex items-center space-x-3">
										<i class="fa-solid fa-file-pdf text-2xl text-error-500"></i>
										<div>
											<p class="font-semibold text-sm">{report.title}</p>
											<div class="flex items-center gap-2 text-xs mt-1">
												{#if report.compliance_status === 'COMPLIANT'}
													<span class="badge variant-filled-success">Compliant</span>
												{:else}
													<span class="badge variant-filled-error">Not Compliant</span>
												{/if}

												{#if report.approval_status === 'APPROVED'}
													<span class="badge variant-soft-success">Approved</span>
												{:else if report.approval_status === 'REJECTED'}
													<span class="badge variant-soft-error">Rejected</span>
												{:else}
													<span class="badge variant-soft-warning">Pending Approval</span>
												{/if}

												{#if report.expiry_date}
													<span class="text-surface-400">Expires: {report.expiry_date}</span>
												{/if}
											</div>
										</div>
									</div>

									<button class="btn btn-sm variant-soft-primary text-xs cursor-pointer" onclick={(e) => { e.stopPropagation(); openReviewModal(report); }}>
										Review Status
									</button>
								</div>
							{/each}
						</div>
					{:else}
						<div class="p-4 text-center border border-dashed border-surface-300-700 rounded text-xs text-surface-500">
							No report files attached to this location.
						</div>
					{/if}
				</div>
			</div>
		</div>
	{:else}
		<div class="card p-16 text-center space-y-4 bg-surface-50-950 border border-surface-200-800 shadow-xl rounded-container">
			<i class="fa-solid fa-folder-open text-6xl text-surface-400"></i>
			<h2 class="text-3xl font-extrabold tracking-tight">NO REPOSITORY FOLDERS FOUND</h2>
			<p class="text-surface-600-400 max-w-md mx-auto">
				Click "+ New Folder" above to create the first Year folder (e.g. 2025-2026).
			</p>
		</div>
	{/if}

<!-- Modal: New Folder / Upload File -->
{#if showNewModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-surface-900/60 p-4">
		<div class="card p-6 w-full max-w-md bg-surface-50-950 shadow-2xl space-y-4 rounded-container border border-surface-200-800">
			<h2 class="text-xl font-bold">
				{#if modalMode === 'FILE'}
					Upload Report File
				{:else}
					Create New {newFolderType} Folder
				{/if}
			</h2>

			<p class="text-xs text-surface-400">
				Location: <strong>{activeFolder?.name || 'Report Repository'}</strong>
			</p>

			{#if modalErrorMsg}
				<div class="alert variant-filled-error p-3 rounded-base text-sm">{modalErrorMsg}</div>
			{/if}

			<form
				action={modalMode === 'FILE' ? '?/createReport' : '?/createFolder'}
				method="POST"
				enctype="multipart/form-data"
				use:enhance={() => {
					isSubmitting = true;
					return async ({ result }) => {
						isSubmitting = false;
						if (result.type === 'success') {
							showNewModal = false;
							await invalidateAll();
						} else if (result.type === 'failure' && result.data?.error) {
							modalErrorMsg = result.data.error;
						}
					};
				}}
			>
				<input type="hidden" name="parent" value={activeFolder?.id || treeData?.id || 'GL'} />
				<input type="hidden" name="partner_folder_id" value={activeFolder?.id || treeData?.id || 'GL'} />
				<input type="hidden" name="folder_type" value={newFolderType} />

				{#if modalMode === 'FILE'}
					<div class="space-y-3">
						<div>
							<label class="label text-sm font-medium mb-1">Select File</label>
							<input
								class="input text-xs cursor-pointer file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-primary-500 file:text-white hover:file:bg-primary-600"
								type="file"
								name="file"
								onchange={handleFileChange}
								required
							/>
							{#if selectedFileObj}
								<p class="text-xs text-success-500 mt-1 font-semibold">
									<i class="fa-solid fa-check mr-1"></i> File selected: {selectedFileObj.name} ({Math.round(selectedFileObj.size / 1024)} KB)
								</p>
							{/if}
						</div>

						<div>
							<label class="label text-sm font-medium mb-1">Report Title</label>
							<input class="input" type="text" name="title" bind:value={newItemName} placeholder="Annual Compliance Audit 2026" required />
						</div>

						<input type="hidden" name="file_path" value={newItemFilePath} />
					</div>
				{:else}
					<div>
						<label class="label text-sm font-medium mb-1">
							{#if newFolderType === 'YEAR'}
								Year Name
							{:else if newFolderType === 'DOMAIN'}
								Business Functions Name
							{:else}
								Folder / Partner Name
							{/if}
						</label>
						<input
							class="input"
							type="text"
							name="name"
							bind:value={newItemName}
							placeholder={newFolderType === 'YEAR' ? '2026' : newFolderType === 'DOMAIN' ? 'IT Security' : 'Vendor Corp'}
							required
						/>
					</div>
				{/if}

				<div class="flex justify-end space-x-2 pt-4">
					<button type="button" class="btn variant-soft cursor-pointer" onclick={() => (showNewModal = false)} disabled={isSubmitting}>Cancel</button>
					<button type="submit" class="btn variant-filled-primary cursor-pointer" disabled={isSubmitting}>
						{#if isSubmitting}
							<i class="fa-solid fa-spinner fa-spin mr-1"></i> Saving...
						{:else if modalMode === 'FILE'}
							Upload File
						{:else}
							Create Folder
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}

<!-- Review Report Status Modal -->
{#if showReviewModal && selectedReportForReview}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-surface-900/60 p-4">
		<div class="card p-6 w-full max-w-md bg-surface-50-950 shadow-2xl space-y-4 rounded-container border border-surface-200-800">
			<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
				<h2 class="text-xl font-bold text-surface-900-100 flex items-center gap-2">
					<i class="fa-solid fa-clipboard-check text-indigo-500"></i>
					<span>Review Report File</span>
				</h2>
				<button onclick={() => (showReviewModal = false)} class="text-surface-400 hover:text-surface-900-100 cursor-pointer">
					<i class="fa-solid fa-xmark text-lg"></i>
				</button>
			</div>

			{#if reviewErrorMsg}
				<div class="p-3 rounded-xl bg-rose-500/20 text-rose-300 border border-rose-500/40 text-xs flex items-center gap-2">
					<i class="fa-solid fa-triangle-exclamation text-rose-400 shrink-0"></i>
					<span>{reviewErrorMsg}</span>
				</div>
			{/if}

			<div class="space-y-1">
				<p class="text-xs text-surface-500 font-bold uppercase tracking-wider">Report Title</p>
				<p class="text-sm font-semibold text-surface-900-100">{selectedReportForReview.title}</p>
			</div>

			{#if selectedReportForReview.file_path}
				<div class="p-3 rounded-xl bg-surface-100-900 border border-surface-200-800 flex items-center justify-between gap-2">
					<div class="flex items-center gap-2 truncate min-w-0">
						<i class="fa-solid fa-file-lines text-indigo-500 text-sm shrink-0"></i>
						<span class="text-xs font-mono text-surface-700-300 truncate">{selectedReportForReview.title} Attachment</span>
					</div>
					<a
						href={`/intermediary-compliance/repository/${selectedReportForReview.id}/download`}
						target="_blank"
						download
						class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
					>
						<i class="fa-solid fa-download"></i>
						<span>View Attachment</span>
					</a>
				</div>
			{/if}

			<div>
				<label class="label text-xs font-bold uppercase tracking-wider text-surface-500 mb-1 block">Expiry Date</label>
				<input class="input text-sm" type="date" bind:value={reviewExpiryDate} disabled={!isReviewAllowed} />
			</div>

			<div>
				<label class="label text-xs font-bold uppercase tracking-wider text-surface-500 mb-1 block">Reviewer Description & Feedback</label>
				<textarea class="textarea text-sm" rows="3" bind:value={reviewFeedback} placeholder="Enter review comments and notes..." disabled={!isReviewAllowed}></textarea>
			</div>

			<div class="flex justify-end space-x-2 pt-2 border-t border-surface-200-800">
				<button class="btn variant-soft cursor-pointer text-xs font-semibold" onclick={() => (showReviewModal = false)}>Cancel</button>
				<button class="btn variant-filled-error cursor-pointer text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed" disabled={!isReviewAllowed} onclick={() => handleReviewSubmit('REJECT')}>Reject Report</button>
				<button class="btn variant-filled-success cursor-pointer text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed" disabled={!isReviewAllowed} onclick={() => handleReviewSubmit('APPROVE')}>Approve Report</button>
			</div>
		</div>
	</div>
{/if}

<!-- In-App Delete Confirmation Modal -->
{#if showDeleteConfirmModal && selectedItem}
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
		<div class="w-full max-w-md bg-surface-50-950 rounded-2xl border border-surface-200-800 shadow-2xl p-6 space-y-5">
			<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
				<h3 class="text-lg font-bold text-surface-900-100 flex items-center gap-2">
					<i class="fa-solid fa-triangle-exclamation text-rose-500"></i>
					<span>Confirm Deletion</span>
				</h3>
				<button onclick={() => (showDeleteConfirmModal = false)} class="text-surface-400 hover:text-surface-900-100 cursor-pointer">
					<i class="fa-solid fa-xmark text-lg"></i>
				</button>
			</div>

			<div class="space-y-2">
				<p class="text-sm text-surface-700-300">
					Are you sure you want to delete <strong class="text-surface-900-100">"{selectedItem.name}"</strong>?
				</p>
				<p class="text-xs text-surface-400">
					This action cannot be undone. All contents inside this folder will be permanently deleted.
				</p>
			</div>

			<div class="flex items-center justify-end gap-3 pt-3 border-t border-surface-200-800">
				<button
					type="button"
					onclick={() => (showDeleteConfirmModal = false)}
					class="px-4 py-2 text-xs font-medium rounded-lg border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800 cursor-pointer"
				>
					Cancel
				</button>
				<form
					action="?/deleteItem"
					method="POST"
					use:enhance={() => {
						return async ({ result }) => {
							if (result.type === 'success') {
								showDeleteConfirmModal = false;
								selectedItemId = null;
								await invalidateAll();
							}
						};
					}}
				>
					<input type="hidden" name="id" value={selectedItem.id} />
					<input type="hidden" name="type" value={selectedItem.type} />
					<button
						type="submit"
						class="px-5 py-2 text-xs font-semibold rounded-lg bg-rose-600 text-white shadow-xs hover:bg-rose-700 cursor-pointer"
					>
						Delete Permanently
					</button>
				</form>
			</div>
		</div>
	</div>
{/if}
</div>
