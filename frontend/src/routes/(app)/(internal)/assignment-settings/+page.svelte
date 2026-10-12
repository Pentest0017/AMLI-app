<script lang="ts">
	import { onMount } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';

	pageTitle.set('Assignment Settings');

	let windowHours = $state(4);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMessage = $state('');

	async function fetchSettings() {
		loading = true;
		error = '';
		try {
			const res = await fetch('/api/compliance/assignment-settings/');
			if (!res.ok) {
				if (res.status === 403) {
					throw new Error('Access denied. Assignment Settings are restricted to Administrators.');
				}
				throw new Error('Failed to load batching settings');
			}
			const data = await res.json();
			windowHours = data.window_hours || 4;
		} catch (err: any) {
			error = err.message || 'Error loading batching settings';
		} finally {
			loading = false;
		}
	}

	async function saveSettings() {
		saving = true;
		error = '';
		successMessage = '';
		try {
			const res = await fetch('/api/compliance/assignment-settings/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ window_hours: windowHours })
			});
			if (!res.ok) throw new Error('Failed to update batching settings');
			const data = await res.json();
			windowHours = data.window_hours;
			successMessage = 'Assignment email batching window updated successfully!';
			setTimeout(() => (successMessage = ''), 3000);
		} catch (err: any) {
			error = err.message || 'Error updating settings';
		} finally {
			saving = false;
		}
	}

	onMount(() => {
		fetchSettings();
	});
</script>

<div class="space-y-6 max-w-4xl">
	<div class="flex items-center justify-between bg-surface-100-900/60 p-4 rounded-xl border border-surface-200-800">
		<div>
			<h1 class="text-xl font-bold text-surface-900-100 flex items-center gap-2.5">
				<i class="fa-solid fa-clock-rotate-left text-primary-500"></i>
				<span>SPOC Control Assignment Email Batching Settings</span>
			</h1>
			<p class="text-xs text-surface-500 mt-0.5">
				Configure the batching window delay for consolidating multiple control assignments assigned to the same SPOC into a single unified assignment digest email.
			</p>
		</div>
	</div>

	{#if successMessage}
		<div class="p-4 rounded-xl border bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs font-semibold flex items-center gap-2">
			<i class="fa-solid fa-circle-check text-base"></i>
			<span>{successMessage}</span>
		</div>
	{/if}

	{#if error}
		<div class="p-4 rounded-xl border bg-rose-500/10 text-rose-500 border-rose-500/20 text-xs font-semibold flex items-center gap-2">
			<i class="fa-solid fa-triangle-exclamation text-base"></i>
			<span>{error}</span>
		</div>
	{/if}

	{#if loading}
		<div class="p-12 text-center text-surface-500 space-y-2">
			<i class="fa-solid fa-spinner fa-spin text-2xl text-primary-500"></i>
			<p class="text-xs">Loading batching settings...</p>
		</div>
	{:else}
		<div class="p-6 rounded-2xl bg-surface-50-950 shadow-xs space-y-6 border border-surface-200-800">
			<div class="space-y-2">
				<label class="text-sm font-semibold text-surface-900-100 block" for="window-input">
					Assignment Consolidation Time Frame (Hours)
				</label>
				<div class="flex items-center gap-3 max-w-xs">
					<input
						id="window-input"
						type="number"
						min="1"
						max="168"
						class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 font-mono font-bold"
						bind:value={windowHours}
					/>
					<span class="text-xs text-surface-600-400 font-medium uppercase tracking-wider">Hours</span>
				</div>
				<p class="text-xs text-surface-500 mt-1">
					When controls are assigned to a SPOC, a batching window starts. All controls assigned within this timeframe will be bundled together and sent as a single email digest when the window expires (Default: 4 hours).
				</p>
			</div>

			<div class="pt-4 border-t border-surface-200-800 flex items-center gap-3">
				<button
					disabled={saving}
					onclick={saveSettings}
					class="px-4 py-2 rounded-xl bg-primary-500 hover:bg-primary-600 text-white font-semibold text-xs shadow-xs flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50"
				>
					{#if saving}
						<i class="fa-solid fa-spinner fa-spin text-xs"></i>
					{:else}
						<i class="fa-solid fa-check text-xs"></i>
					{/if}
					<span>Save Batching Settings</span>
				</button>
			</div>
		</div>
	{/if}
</div>
