<script lang="ts">
	import { onMount } from 'svelte';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	interface AssignmentItem {
		domain_id: string;
		domain_name: string;
		year_name: string;
		spoc_users: { id: string; username: string; email: string; is_admin: boolean }[];
		approving_admins: { id: string; username: string; email: string }[];
	}

	interface UserItem {
		id: string;
		email: string;
		first_name?: string;
		last_name?: string;
		is_superuser?: boolean;
		is_admin?: boolean;
		platform_role?: string;
	}

	let assignments: AssignmentItem[] = $derived(data?.assignments ?? []);
	let allUsers: UserItem[] = $derived(data?.allUsers ?? []);
	let isForbidden = $derived(data?.isForbidden ?? false);

	let isLoading = $state(false);
	let selectedDomainId = $state('');
	let selectedSpocIds: string[] = $state([]);
	let selectedAdminIds: string[] = $state([]);
	let showModal = $state(false);
	let errorMessage = $state('');
	let successMessage = $state('');

	function isSuperAdminUser(u: UserItem): boolean {
		if (u.is_superuser) return true;
		if (u.platform_role && u.platform_role === 'superadmin') return true;
		return false;
	}

	function isUserAdminRole(u: UserItem): boolean {
		if (u.is_superuser) return true;
		if (u.is_admin) return true;
		if (u.platform_role && ['superadmin', 'webadmin', 'admin'].includes(u.platform_role)) return true;
		return false;
	}

	function getUserDisplayName(u: UserItem): string {
		const name = [u.first_name, u.last_name].filter(Boolean).join(' ');
		return name ? `${name} (${u.email})` : u.email;
	}

	async function refreshData() {
		isLoading = true;
		try {
			await invalidateAll();
		} catch (err) {
			console.error(err);
		} finally {
			isLoading = false;
		}
	}

	function openEditModal(item: AssignmentItem) {
		selectedDomainId = item.domain_id;
		selectedSpocIds = item.spoc_users.map((u) => u.id);
		selectedAdminIds = item.approving_admins.map((u) => u.id);
		errorMessage = '';
		successMessage = '';
		showModal = true;
	}

	function toggleSpoc(userId: string) {
		if (selectedSpocIds.includes(userId)) {
			selectedSpocIds = selectedSpocIds.filter((id) => id !== userId);
		} else {
			selectedSpocIds = [...selectedSpocIds, userId];
		}
	}

	function toggleAdmin(userId: string) {
		if (selectedAdminIds.includes(userId)) {
			selectedAdminIds = selectedAdminIds.filter((id) => id !== userId);
		} else {
			selectedAdminIds = [...selectedAdminIds, userId];
		}
	}
</script>

<div class="p-6 space-y-6">
	<div class="flex justify-between items-center">
		<div>
			<h1 class="text-2xl font-bold text-surface-900-100">Intermediary Compliance - Assignments</h1>
			<p class="text-sm text-surface-600-400">Assign SPOCs and Approving Admins (Reviewers) to Business Functions folders.</p>
		</div>
		{#if !isForbidden}
			<button class="btn variant-filled-primary cursor-pointer" onclick={refreshData}>
				<i class="fa-solid fa-rotate-right mr-2"></i> Refresh
			</button>
		{/if}
	</div>

	{#if isForbidden}
		<div class="card p-16 text-center space-y-4 bg-surface-50-950 border border-surface-200-800 shadow-xl rounded-container">
			<i class="fa-solid fa-lock text-6xl text-surface-400"></i>
			<h2 class="text-3xl font-extrabold tracking-tight">NO TASKS ARE ASSIGNED</h2>
			<p class="text-surface-600-400 max-w-md mx-auto">
				Business Functions management is only accessible to Web Admins and Superadmins.
			</p>
		</div>
	{:else if isLoading}
		<div class="flex justify-center p-12">
			<i class="fa-solid fa-spinner fa-spin text-3xl text-primary-500"></i>
		</div>
	{:else}
		<div class="table-container card border border-surface-200-800 shadow-md">
			<table class="table table-hover">
				<thead>
					<tr>
						<th>Year Folder</th>
						<th>Business Functions Folder</th>
						<th>Assigned SPOCs (Users & Admins)</th>
						<th>Assigned Reviewers (Admins)</th>
						<th class="text-right">Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each assignments as item}
						<tr>
							<td class="font-semibold text-surface-600-400">{item.year_name}</td>
							<td class="font-bold text-primary-500">{item.domain_name}</td>
							<td>
								{#if item.spoc_users.length > 0}
									<div class="flex flex-wrap gap-1">
										{#each item.spoc_users as spoc}
											<span class="badge variant-soft-primary text-xs">
												<i class="fa-solid fa-user text-xs mr-1"></i>
												{getUserDisplayName(spoc)}
											</span>
										{/each}
									</div>
								{:else}
									<span class="text-xs text-surface-400 italic">None</span>
								{/if}
							</td>
							<td>
								{#if item.approving_admins.length > 0}
									<div class="flex flex-wrap gap-1">
										{#each item.approving_admins as admin}
											<span class="badge variant-soft-warning text-xs">
												<i class="fa-solid fa-user-shield text-xs mr-1"></i>
												{getUserDisplayName(admin)}
											</span>
										{/each}
									</div>
								{:else}
									<span class="text-xs text-surface-400 italic">None</span>
								{/if}
							</td>
							<td class="text-right">
								<button class="btn btn-sm variant-filled-primary cursor-pointer" onclick={() => openEditModal(item)}>
									<i class="fa-solid fa-user-gear mr-1"></i> Manage
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

{#if showModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-surface-900/60 p-4">
		<div class="card p-6 w-full max-w-2xl bg-surface-50-950 shadow-2xl space-y-4 rounded-container border border-surface-200-800">
			<h2 class="text-xl font-bold">Manage Business Functions Assignment</h2>

			{#if errorMessage}
				<div class="alert variant-filled-error p-3 rounded-base text-sm">{errorMessage}</div>
			{/if}
			{#if successMessage}
				<div class="alert variant-filled-success p-3 rounded-base text-sm">{successMessage}</div>
			{/if}

			<form
				action="?/saveAssignment"
				method="POST"
				use:enhance={() => {
					isLoading = true;
					errorMessage = '';
					successMessage = '';
					return async ({ result }) => {
						isLoading = false;
						if (result.type === 'success' && (result.data as any)?.success) {
							successMessage = 'Assignments updated successfully!';
							if (typeof window !== 'undefined') {
								window.dispatchEvent(new CustomEvent('notification-update'));
							}
							await invalidateAll();
							setTimeout(() => { showModal = false; }, 800);
						} else if (result.type === 'success' && !(result.data as any)?.success) {
							errorMessage = (result.data as any)?.error || 'Failed to update assignment.';
						} else {
							errorMessage = 'Error saving assignment.';
						}
					};
				}}
			>
				<input type="hidden" name="domain_id" value={selectedDomainId} />
				<input type="hidden" name="spoc_user_ids" value={JSON.stringify(selectedSpocIds)} />
				<input type="hidden" name="approving_admin_ids" value={JSON.stringify(selectedAdminIds)} />

				<div class="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
					<div>
						<h3 class="text-sm font-semibold mb-2">Assign SPOCs (Users & Admins)</h3>
						<div class="space-y-1">
							{#each allUsers as user}
								<label class="flex items-center space-x-2 text-sm p-1 rounded hover:bg-surface-200-800 cursor-pointer">
									<input
										type="checkbox"
										class="checkbox cursor-pointer"
										checked={selectedSpocIds.includes(user.id)}
										onchange={() => toggleSpoc(user.id)}
									/>
									<span>{getUserDisplayName(user)}</span>
									{#if isUserAdminRole(user)}
										<span class="badge variant-soft-warning text-xs">{user.platform_role || 'Admin'}</span>
									{:else}
										<span class="badge variant-soft-surface text-xs">User</span>
									{/if}
								</label>
							{/each}
						</div>
					</div>

					<hr class="opacity-20" />

					<div>
						<h3 class="text-sm font-semibold mb-2">Assign Approving Admins / Reviewers (Admins Only)</h3>
						<div class="space-y-1">
							{#each allUsers.filter(isUserAdminRole) as admin}
								<label class="flex items-center space-x-2 text-sm p-1 rounded hover:bg-surface-200-800 cursor-pointer">
									<input
										type="checkbox"
										class="checkbox cursor-pointer"
										checked={selectedAdminIds.includes(admin.id)}
										onchange={() => toggleAdmin(admin.id)}
									/>
									<span>{getUserDisplayName(admin)}</span>
									<span class="badge variant-soft-warning text-xs">{admin.platform_role || 'Admin'}</span>
								</label>
							{/each}
						</div>
					</div>
				</div>

				<div class="flex justify-end space-x-2 pt-4">
					<button type="button" class="btn variant-soft cursor-pointer" onclick={() => (showModal = false)}>Cancel</button>
					<button type="submit" class="btn variant-filled-primary cursor-pointer">Save Changes</button>
				</div>
			</form>
		</div>
	</div>
{/if}
