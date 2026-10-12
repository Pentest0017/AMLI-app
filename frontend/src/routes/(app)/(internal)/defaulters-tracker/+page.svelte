<script lang="ts">
	import { onMount } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';

	pageTitle.set('Defaulters Tracker');

	interface DefaulterItem {
		id: string;
		spoc_email: string;
		spoc_name: string;
		supervisor_email: string;
		control_ref_id: string;
		control_title: string;
		framework_name: string;
		assignment_date: string;
		original_due_date: string;
		l1_reminder_date: string | null;
		l2_grace_deadline: string | null;
		l3_final_deadline: string | null;
		active_deadline: string;
		escalation_level: string;
		is_cleared: boolean;
		days_overdue: number;
	}

	let liveItems: DefaulterItem[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');
	let selectedLevel = $state('');
	let activeTab = $state<'live' | 'benchmark'>('live');

	// Benchmark test cases to display verified state machine behavior
	const benchmarkItems: DefaulterItem[] = [
		{
			id: 'bm-01',
			spoc_email: 'statetest_spoc@test.com',
			spoc_name: 'Audit SPOC 1',
			supervisor_email: 'supervisor_a@test.com',
			control_ref_id: '11.5',
			control_title: 'User Authentication & Password Indication',
			framework_name: 'Irdai Audit Checklist V2',
			assignment_date: '2026-09-01',
			original_due_date: '2026-09-18',
			l1_reminder_date: '2026-09-01',
			l2_grace_deadline: '2026-09-02',
			l3_final_deadline: '2026-09-03',
			active_deadline: '2026-09-03',
			escalation_level: 'CLEARED',
			is_cleared: true,
			days_overdue: 0
		},
		{
			id: 'bm-02',
			spoc_email: 'statetest_spoc2@test.com',
			spoc_name: 'Audit SPOC 2',
			supervisor_email: 'webadmin@test.com',
			control_ref_id: 'TM-999',
			control_title: 'Test Node For State Machine Enforcement',
			framework_name: 'Iso 27001 Checklist V2',
			assignment_date: '2026-09-01',
			original_due_date: '2026-09-02',
			l1_reminder_date: '2026-09-02',
			l2_grace_deadline: '2026-09-03',
			l3_final_deadline: '2026-09-03',
			active_deadline: '2026-09-03',
			escalation_level: 'FINAL_DEFAULTER',
			is_cleared: false,
			days_overdue: 4
		},
		{
			id: 'bm-03',
			spoc_email: 'dev_spoc3@test.com',
			spoc_name: 'Dev Lead SPOC',
			supervisor_email: 'tech_manager@test.com',
			control_ref_id: 'A.12.6.1',
			control_title: 'Management of Technical Vulnerabilities',
			framework_name: 'ISO 27001:2013',
			assignment_date: '2026-08-25',
			original_due_date: '2026-09-01',
			l1_reminder_date: '2026-09-01',
			l2_grace_deadline: '2026-09-05',
			l3_final_deadline: '2026-09-10',
			active_deadline: '2026-09-05',
			escalation_level: 'L2_GRACE',
			is_cleared: false,
			days_overdue: 2
		},
		{
			id: 'bm-04',
			spoc_email: 'ops_spoc4@test.com',
			spoc_name: 'Operations SPOC',
			supervisor_email: 'ciso_office@test.com',
			control_ref_id: 'CC6.1',
			control_title: 'Boundary Infrastructure & Firewalls',
			framework_name: 'SOC 2 Type II',
			assignment_date: '2026-08-20',
			original_due_date: '2026-09-03',
			l1_reminder_date: '2026-09-03',
			l2_grace_deadline: '2026-09-06',
			l3_final_deadline: '2026-09-07',
			active_deadline: '2026-09-07',
			escalation_level: 'L3_FINAL_GRACE',
			is_cleared: false,
			days_overdue: 3
		},
		{
			id: 'bm-05',
			spoc_email: 'infosec_spoc5@test.com',
			spoc_name: 'InfoSec Engineer',
			supervisor_email: 'head_security@test.com',
			control_ref_id: 'SI-3',
			control_title: 'Malicious Code Protection & EDR',
			framework_name: 'NIST SP 800-53',
			assignment_date: '2026-09-01',
			original_due_date: '2026-09-15',
			l1_reminder_date: '2026-09-07',
			l2_grace_deadline: '2026-09-12',
			l3_final_deadline: '2026-09-15',
			active_deadline: '2026-09-07',
			escalation_level: 'L1',
			is_cleared: false,
			days_overdue: 0
		}
	];

	async function fetchDefaulters() {
		loading = true;
		error = '';
		try {
			const res = await fetch('/api/compliance/defaulters-tracker/');
			if (!res.ok) {
				if (res.status === 403) {
					throw new Error('Access denied. Defaulters Tracker is restricted to Supervisors and Administrators.');
				}
				throw new Error('Failed to load defaulters data from backend');
			}
			const data = await res.json();
			liveItems = data.results || [];
		} catch (err: any) {
			error = err.message || 'Error loading defaulters tracker';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchDefaulters();
	});

	const activeItems = $derived(activeTab === 'live' ? liveItems : benchmarkItems);

	const filteredItems = $derived(
		activeItems.filter((item) => {
			const q = searchQuery.toLowerCase().trim();
			const matchesSearch =
				!q ||
				(item.spoc_name || '').toLowerCase().includes(q) ||
				(item.spoc_email || '').toLowerCase().includes(q) ||
				(item.control_ref_id || '').toLowerCase().includes(q) ||
				(item.control_title || '').toLowerCase().includes(q) ||
				(item.framework_name || '').toLowerCase().includes(q);

			const matchesLevel = !selectedLevel || item.escalation_level === selectedLevel;
			return matchesSearch && matchesLevel;
		})
	);

	// Summary stats
	const stats = $derived({
		total: activeItems.length,
		l1: activeItems.filter((i) => i.escalation_level === 'L1' && !i.is_cleared).length,
		l2: activeItems.filter((i) => i.escalation_level === 'L2_GRACE' && !i.is_cleared).length,
		l3: activeItems.filter((i) => i.escalation_level === 'L3_FINAL_GRACE' && !i.is_cleared).length,
		finalDefaulters: activeItems.filter((i) => i.escalation_level === 'FINAL_DEFAULTER' && !i.is_cleared).length,
		cleared: activeItems.filter((i) => i.is_cleared || i.escalation_level === 'CLEARED').length
	});

	function getLevelBadgeClass(level: string, isCleared: boolean) {
		if (isCleared || level === 'CLEARED') return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30';
		if (level === 'FINAL_DEFAULTER') return 'bg-rose-950 text-rose-400 border-rose-600/50 font-bold animate-pulse';
		if (level === 'L3_FINAL_GRACE') return 'bg-rose-500/10 text-rose-500 border-rose-500/30 font-semibold';
		if (level === 'L2_GRACE') return 'bg-orange-500/10 text-orange-500 border-orange-500/30';
		if (level === 'L1') return 'bg-amber-500/10 text-amber-500 border-amber-500/30';
		return 'bg-surface-500/10 text-surface-400 border-surface-500/30';
	}

	function getLevelLabel(level: string, isCleared: boolean) {
		if (isCleared || level === 'CLEARED') return 'CLEARED';
		if (level === 'FINAL_DEFAULTER') return 'FINAL DEFAULTER';
		if (level === 'L3_FINAL_GRACE') return 'L3 FINAL GRACE';
		if (level === 'L2_GRACE') return 'L2 GRACE PERIOD';
		if (level === 'L1') return 'L1 SPOC REMINDER';
		return level || 'PENDING';
	}
</script>

<div class="space-y-6">
	<!-- Top Bar -->
	<div class="flex flex-wrap items-center justify-between gap-4 bg-surface-100-900/60 p-4 rounded-xl border border-surface-200-800 shadow-xs">
		<div>
			<h1 class="text-xl font-bold text-surface-900-100 flex items-center gap-2.5">
				<i class="fa-solid fa-user-clock text-amber-500"></i>
				<span>Defaulters Tracker & Compliance Audit</span>
			</h1>
			<p class="text-xs text-surface-500 mt-0.5">
				Real-time monitoring of evidence submission deadlines, multi-tier escalation stages, and supervisor accountability.
			</p>
		</div>

		<div class="flex items-center gap-3">
			<!-- Tab Switcher -->
			<div class="flex items-center bg-surface-200-800 p-1 rounded-xl border border-surface-300-700">
				<button
					onclick={() => (activeTab = 'live')}
					class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all {activeTab === 'live' ? 'bg-primary-500 text-white shadow-xs' : 'text-surface-600-400 hover:text-surface-900-100'}"
				>
					<i class="fa-solid fa-database text-[10px] mr-1"></i> Live Backend Data
				</button>
				<button
					onclick={() => (activeTab = 'benchmark')}
					class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all {activeTab === 'benchmark' ? 'bg-primary-500 text-white shadow-xs' : 'text-surface-600-400 hover:text-surface-900-100'}"
				>
					<i class="fa-solid fa-vial text-[10px] mr-1"></i> Tested Benchmark Examples
				</button>
			</div>

			<button
				onclick={fetchDefaulters}
				disabled={loading}
				class="px-3.5 py-2 rounded-xl bg-surface-200-800 hover:bg-surface-300-700 text-surface-900-100 text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
			>
				<i class="fa-solid fa-rotate-right text-[11px] {loading ? 'animate-spin' : ''}"></i>
				<span>Refresh</span>
			</button>
		</div>
	</div>

	{#if error}
		<div class="p-4 rounded-xl border bg-rose-500/10 text-rose-500 border-rose-500/20 text-xs font-semibold flex items-center gap-2">
			<i class="fa-solid fa-triangle-exclamation text-base"></i>
			<span>{error}</span>
		</div>
	{/if}

	<!-- KPI Summary Metrics Grid -->
	<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
		<div class="p-3.5 rounded-xl border border-surface-200-800 bg-surface-50-950 shadow-xs space-y-1">
			<span class="text-[10px] font-bold uppercase tracking-wider text-surface-500">Tracked Controls</span>
			<div class="text-xl font-bold text-surface-900-100 font-mono">{stats.total}</div>
		</div>

		<div class="p-3.5 rounded-xl border border-amber-500/20 bg-amber-500/5 shadow-xs space-y-1">
			<span class="text-[10px] font-bold uppercase tracking-wider text-amber-500">L1 Reminders</span>
			<div class="text-xl font-bold text-amber-500 font-mono">{stats.l1}</div>
		</div>

		<div class="p-3.5 rounded-xl border border-orange-500/20 bg-orange-500/5 shadow-xs space-y-1">
			<span class="text-[10px] font-bold uppercase tracking-wider text-orange-500">L2 Grace Period</span>
			<div class="text-xl font-bold text-orange-500 font-mono">{stats.l2}</div>
		</div>

		<div class="p-3.5 rounded-xl border border-rose-500/20 bg-rose-500/5 shadow-xs space-y-1">
			<span class="text-[10px] font-bold uppercase tracking-wider text-rose-500">L3 Final Grace</span>
			<div class="text-xl font-bold text-rose-500 font-mono">{stats.l3}</div>
		</div>

		<div class="p-3.5 rounded-xl border border-rose-700/40 bg-rose-950/20 shadow-xs space-y-1">
			<span class="text-[10px] font-bold uppercase tracking-wider text-rose-400">Final Defaulters</span>
			<div class="text-xl font-bold text-rose-400 font-mono">{stats.finalDefaulters}</div>
		</div>

		<div class="p-3.5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 shadow-xs space-y-1">
			<span class="text-[10px] font-bold uppercase tracking-wider text-emerald-500">Cleared / Compliant</span>
			<div class="text-xl font-bold text-emerald-500 font-mono">{stats.cleared}</div>
		</div>
	</div>

	<!-- Filters Bar -->
	<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-surface-100-900/50 p-3.5 rounded-xl border border-surface-200-800">
		<div class="sm:col-span-2">
			<label class="text-[10px] font-bold text-surface-500 uppercase tracking-wider">Search Control or SPOC</label>
			<div class="relative mt-1">
				<i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-surface-400"></i>
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search ref ID, control title, SPOC name or email..."
					class="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100"
				/>
			</div>
		</div>

		<div>
			<label class="text-[10px] font-bold text-surface-500 uppercase tracking-wider">Escalation Stage</label>
			<select
				bind:value={selectedLevel}
				class="w-full mt-1 px-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100"
			>
				<option value="">All Escalation Stages</option>
				<option value="L1">L1 SPOC Reminder</option>
				<option value="L2_GRACE">L2 Grace Period</option>
				<option value="L3_FINAL_GRACE">L3 Final Grace</option>
				<option value="FINAL_DEFAULTER">Final Defaulter</option>
				<option value="CLEARED">Cleared / Approved</option>
			</select>
		</div>
	</div>

	<!-- Defaulters Table -->
	<div class="border border-surface-200-800 rounded-2xl bg-surface-50-950 shadow-xs overflow-hidden">
		{#if loading}
			<div class="p-12 text-center text-surface-500 space-y-2">
				<i class="fa-solid fa-spinner fa-spin text-2xl text-primary-500"></i>
				<p class="text-xs">Loading defaulters tracking audit data...</p>
			</div>
		{:else if filteredItems.length === 0}
			<div class="p-12 text-center space-y-3">
				<div class="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 flex items-center justify-center mx-auto text-xl">
					<i class="fa-solid fa-shield-check"></i>
				</div>
				<div>
					<h3 class="font-bold text-sm text-surface-900-100">No Outstanding Defaulters Found</h3>
					<p class="text-xs text-surface-500 mt-1 max-w-md mx-auto">
						{activeTab === 'live'
							? 'All assigned controls for your scope are currently up to date or evidence has been submitted successfully.'
							: 'No benchmark items match your search filter.'}
					</p>
				</div>
				{#if activeTab === 'live' && liveItems.length === 0}
					<button
						onclick={() => (activeTab = 'benchmark')}
						class="px-4 py-2 text-xs font-semibold rounded-xl bg-primary-500 text-white shadow-xs hover:bg-primary-600 transition-all inline-flex items-center gap-2 cursor-pointer mt-2"
					>
						<i class="fa-solid fa-vial"></i>
						<span>View Tested Benchmark Examples</span>
					</button>
				{/if}
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-xs text-left">
					<thead class="bg-surface-100-900 border-b border-surface-200-800 text-surface-600-400 uppercase tracking-wider font-bold text-[10px]">
						<tr>
							<th class="py-3 px-4">Control Ref & Title</th>
							<th class="py-3 px-4">Framework</th>
							<th class="py-3 px-4">Assigned SPOC</th>
							<th class="py-3 px-4">Supervisor</th>
							<th class="py-3 px-4 text-center">Original Due</th>
							<th class="py-3 px-4 text-center">Escalation Stage</th>
							<th class="py-3 px-4 text-center">Active Deadline</th>
							<th class="py-3 px-4 text-center">Overdue</th>
							<th class="py-3 px-4 text-right">Action</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-surface-200-800/40">
						{#each filteredItems as item}
							<tr class="hover:bg-surface-100-900/40 transition-colors">
								<td class="py-3 px-4 max-w-xs">
									<div class="font-mono font-bold text-surface-900-100 text-xs">
										{item.control_ref_id}
									</div>
									<div class="text-surface-400 line-clamp-1 mt-0.5" title={item.control_title}>
										{item.control_title}
									</div>
								</td>

								<td class="py-3 px-4 text-surface-400 font-mono text-[11px]">
									{item.framework_name}
								</td>

								<td class="py-3 px-4">
									<div class="font-medium text-surface-900-100">
										{item.spoc_name || item.spoc_email.split('@')[0]}
									</div>
									<div class="text-[10px] text-surface-500 font-mono">
										{item.spoc_email}
									</div>
								</td>

								<td class="py-3 px-4">
									<div class="text-surface-300 font-medium">
										{item.supervisor_email}
									</div>
								</td>

								<td class="py-3 px-4 text-center font-mono text-surface-400">
									{item.original_due_date}
								</td>

								<td class="py-3 px-4 text-center">
									<span class="px-2.5 py-1 rounded-full text-[10px] font-mono border inline-block {getLevelBadgeClass(item.escalation_level, item.is_cleared)}">
										{getLevelLabel(item.escalation_level, item.is_cleared)}
									</span>
								</td>

								<td class="py-3 px-4 text-center font-mono font-semibold text-surface-200">
									{item.active_deadline || item.original_due_date}
								</td>

								<td class="py-3 px-4 text-center">
									{#if item.is_cleared || item.escalation_level === 'CLEARED'}
										<span class="text-emerald-500 font-semibold font-mono">0 d</span>
									{:else if item.days_overdue > 0}
										<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold font-mono text-[11px]">
											+{item.days_overdue} d
										</span>
									{:else}
										<span class="text-surface-400 font-mono text-[11px]">0 d</span>
									{/if}
								</td>

								<td class="py-3 px-4 text-right">
									<a
										href="/control-assignments/submit"
										class="px-2.5 py-1 rounded-lg border border-surface-200-800 bg-surface-100-900 hover:bg-surface-200-800 text-surface-900-100 text-[11px] font-medium transition-all inline-flex items-center gap-1"
									>
										<span>View</span>
										<i class="fa-solid fa-arrow-right text-[9px]"></i>
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
