<script lang="ts">
	import { onMount } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';
	import type { PageData } from './$types';

	pageTitle.set('Automated Escalation Rules');

	let { data }: { data: PageData } = $props();

	let loading = $state(false);
	let rules = $state<any[]>([]);
	let logs = $state<any[]>([]);
	let controls = $state<any[]>([]);
	let frameworks = $state<any[]>([]);
	let assignedUsers = $state<any[]>([]);
	let adminUsers = $state<any[]>([]);
	let pendingLinks = $state<any[]>([]);

	let selectedAssignmentIds = $state<string[]>([]);
	let triggeringLevel = $state<number | null>(null);
	let triggerMessage = $state('');

	let scheduleModalOpen = $state(false);
	let scheduleLevelName = $state('L1');
	let scheduleTargetDate = $state('');
	let scheduleGraceDays = $state<number>(0);
	let baselineDueDate = $state('');

	function getLevelBadgeClass(level: string) {
		if (level === 'CLEARED') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
		if (level === 'FINAL_DEFAULTER') return 'bg-rose-950/80 text-rose-300 border-rose-600/50';
		if (level === 'L3_FINAL_GRACE') return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
		if (level === 'L2_GRACE') return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
		if (level === 'L1') return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
		return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
	}

	function getLevelLabel(level: string) {
		if (level === 'CLEARED') return 'CLEARED';
		if (level === 'FINAL_DEFAULTER') return 'FINAL DEFAULTER';
		if (level === 'L3_FINAL_GRACE') return 'L3 FINAL GRACE';
		if (level === 'L2_GRACE') return 'L2 GRACE';
		if (level === 'L1') return 'L1 REMINDER';
		return 'ASSIGNED';
	}

	function openScheduleModal(levelName: string) {
		scheduleLevelName = levelName;
		
		const targetIds = selectedAssignmentIds.length > 0
			? selectedAssignmentIds
			: filteredControls.map((c) => c.assignment?.id).filter(Boolean);
		
		const targetControls = controls.filter((c) => c.assignment && targetIds.includes(c.assignment.id));
		
		let baseDate = '';
		if (targetControls.length > 0) {
			const ctrl = targetControls[0];
			if (levelName === 'L2' && ctrl.assignment?.l1_reminder_date) {
				baseDate = ctrl.assignment.l1_reminder_date;
			} else if (levelName === 'L3' && ctrl.assignment?.l2_grace_deadline) {
				baseDate = ctrl.assignment.l2_grace_deadline;
			} else if (ctrl.assignment?.due_date) {
				baseDate = ctrl.assignment.due_date;
			}
		}

		if (!baseDate) {
			baseDate = new Date().toISOString().split('T')[0];
		}

		baselineDueDate = baseDate;
		const defaultGrace = levelName === 'L1' ? 1 : levelName === 'L2' ? 5 : 3;
		scheduleGraceDays = defaultGrace;

		calculateTargetFromGrace(baseDate, defaultGrace);
		scheduleModalOpen = true;
	}

	function calculateTargetFromGrace(baseStr: string, days: number) {
		if (!baseStr) return;
		const d = new Date(baseStr);
		d.setDate(d.getDate() + (isNaN(days) ? 0 : days));
		scheduleTargetDate = d.toISOString().split('T')[0];
	}

	function setGraceDays(days: number) {
		scheduleGraceDays = days;
		calculateTargetFromGrace(baselineDueDate, days);
	}

	function handleDateChange(e: Event) {
		const val = (e.target as HTMLInputElement).value;
		scheduleTargetDate = val;
		if (val && baselineDueDate) {
			const b = new Date(baselineDueDate).getTime();
			const t = new Date(val).getTime();
			const diff = Math.round((t - b) / (1000 * 3600 * 24));
			scheduleGraceDays = Math.max(0, diff);
		}
	}

	async function submitScheduleDate() {
		if (!scheduleTargetDate) return;
		const targetIds =
			selectedAssignmentIds.length > 0
				? selectedAssignmentIds
				: filteredControls.map((c) => c.assignment.id).filter(Boolean);

		if (targetIds.length === 0) {
			triggerMessage = 'No controls selected for escalation scheduling.';
			scheduleModalOpen = false;
			return;
		}

		try {
			const res = await fetch('/api/escalation-rules/schedule-level/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					level: scheduleLevelName,
					target_date: scheduleTargetDate,
					assignment_ids: targetIds
				})
			});
			const data = await res.json();
			if (res.ok) {
				triggerMessage = data.message || `Scheduled ${scheduleLevelName} escalation successfully!`;
				scheduleModalOpen = false;
				await loadEscalationData();
			} else {
				triggerMessage = data.error || 'Failed to schedule escalation date.';
			}
		} catch {
			triggerMessage = 'Error scheduling escalation date.';
		}
	}

	// Filter state
	let searchQuery = $state('');
	let selectedFrameworkId = $state('');
	let selectedStatusFilter = $state('');
	let selectedUserId = $state('');
	let showLogsTable = $state(false);

	function normalizeRules(rawRules: any[]) {
		return (rawRules || []).map((r: any) => ({
			id: r.id,
			name: r.name || '',
			is_active: r.is_active !== false,
			trigger_baseline: r.trigger_baseline || 'ASSIGNMENT_DATE',
			escalation_steps: {
				level: r.escalation_steps?.level || 1,
				interval_value: r.escalation_steps?.interval_value ?? 1,
				interval_unit: r.escalation_steps?.interval_unit || 'minutes',
				recipient_role: r.escalation_steps?.recipient_role || 'SPOC',
				target_admin_user_id: r.escalation_steps?.target_admin_user_id || ''
			}
		}));
	}

	$effect(() => {
		if (data) {
			rules = normalizeRules(data.rules);
			logs = data.logs || [];
			controls = data.controls || [];
			frameworks = data.frameworks || [];
			assignedUsers = data.assignedUsers || [];
			adminUsers = data.adminUsers || [];
			pendingLinks = data.pendingLinks || [];
		}
	});

	// Filtered Controls
	const filteredControls = $derived(
		controls.filter((c) => {
			if (!c.assignment || !c.assignment.spoc_user) return false;
			if (selectedFrameworkId && c.framework_id !== selectedFrameworkId) return false;

			if (selectedUserId) {
				const isSpoc = c.assignment.spoc_user?.id === selectedUserId;
				const isReviewer = c.assignment.reviewer_user?.id === selectedUserId;
				if (!isSpoc && !isReviewer) return false;
			}

			if (selectedStatusFilter === 'PENDING_REVIEW') {
				const hasPendingReview = pendingLinks.some(
					(pl) => pl.assessment_control?.control_assignment?.id === c.assignment.id && pl.review_status === 'SUBMITTED'
				);
				if (!hasPendingReview) return false;
			} else if (selectedStatusFilter === 'PENDING_SUBMISSION') {
				const isApproved = pendingLinks.some(
					(link) => link.control?.ref_id === c.ref_id && link.review_status === 'APPROVED'
				);
				if (isApproved) return false;
			}

			if (searchQuery.trim()) {
				const q = searchQuery.toLowerCase();
				const refMatch = c.ref_id?.toLowerCase().includes(q);
				const nameMatch = c.name?.toLowerCase().includes(q);
				const spocMatch = c.assignment.spoc_user?.email?.toLowerCase().includes(q);
				const revMatch = c.assignment.reviewer_user?.email?.toLowerCase().includes(q);
				if (!refMatch && !nameMatch && !spocMatch && !revMatch) return false;
			}

			return true;
		})
	);

	async function loadEscalationData() {
		loading = true;
		try {
			const [rRes, lRes, cRes, repoRes, aRes] = await Promise.all([
				fetch('/api/escalation-rules/'),
				fetch('/api/escalation/logs/'),
				fetch('/api/control-assignments/controls/'),
				fetch('/api/evidence-repository/'),
				fetch('/api/escalation/admin-users/')
			]);

			if (rRes.ok) {
				const rData = await rRes.json();
				rules = normalizeRules(rData.results || rData || []);
			}
			if (lRes.ok) {
				const lData = await lRes.json();
				logs = lData.results || lData || [];
			}
			if (aRes.ok) {
				adminUsers = await aRes.json();
			}
			if (repoRes.ok) {
				const repoData = await repoRes.json();
				pendingLinks = repoData.results || repoData || [];
			}
			if (cRes.ok) {
				const cData = await cRes.json();
				const list: any[] = [];
				for (const fw of cData.frameworks || []) {
					for (const c of fw.controls || []) {
						if (c.assignment && c.assignment.spoc_user) {
							list.push({ ...c, framework_name: fw.name, framework_id: fw.id });
						}
					}
				}
				controls = list;
			}
		} catch (err) {
			console.error('Failed to reload escalation data:', err);
		} finally {
			loading = false;
		}
	}

	async function triggerLevelEscalation(level: number) {
		triggeringLevel = level;
		triggerMessage = '';

		const targetIds =
			selectedAssignmentIds.length > 0
				? selectedAssignmentIds
				: filteredControls.map((c) => c.assignment.id).filter(Boolean);

		if (targetIds.length === 0) {
			triggerMessage = 'No controls selected for escalation.';
			triggeringLevel = null;
			return;
		}

		const formData = new FormData();
		formData.append('level', level.toString());
		formData.append('assignment_ids', JSON.stringify(targetIds));

		try {
			const res = await fetch('?/triggerEscalation', {
				method: 'POST',
				body: formData
			});

			const result = await res.json();
			let isSuccess = false;
			let successMsg = `Level ${level} Escalation sent successfully!`;
			let errorMsg = `Failed to send Level ${level} escalation.`;

			if (result.type === 'success') {
				let parsed = result.data;
				if (typeof parsed === 'string') {
					try { parsed = JSON.parse(parsed); } catch (e) {}
				}
				if (Array.isArray(parsed) && parsed.length > 0) {
					parsed = parsed[0];
				}

				if (parsed?.success === false || parsed?.error) {
					errorMsg = parsed?.error || errorMsg;
				} else {
					isSuccess = true;
					if (parsed?.data?.message) successMsg = parsed.data.message;
					else if (parsed?.message) successMsg = parsed.message;
				}
			} else if (result.error) {
				errorMsg = result.error;
			}

			if (isSuccess) {
				triggerMessage = successMsg;
				selectedAssignmentIds = [];
				setTimeout(loadEscalationData, 1000);
			} else {
				triggerMessage = errorMsg;
			}
		} catch (err) {
			triggerMessage = 'Network error triggering escalation.';
		} finally {
			triggeringLevel = null;
		}
	}

	async function saveRule(rule: any) {
		try {
			const steps = rule.escalation_steps || {};
			const lvl = steps.level || rule.level || 1;

			const formData = new FormData();
			formData.append('id', rule.id);
			formData.append('name', rule.name || '');
			formData.append('is_active', (rule.is_active !== false).toString());
			formData.append('trigger_baseline', rule.trigger_baseline || 'ASSIGNMENT_DATE');
			formData.append('level', lvl.toString());
			formData.append('interval_value', (steps.interval_value ?? 1).toString());
			formData.append('interval_unit', steps.interval_unit || 'minutes');
			formData.append('recipient_role', steps.recipient_role || (lvl === 1 ? 'SPOC' : lvl === 2 ? 'REVIEWER' : 'WEBADMIN'));
			if (steps.target_admin_user_id) {
				formData.append('target_admin_user_id', steps.target_admin_user_id);
			}

			const res = await fetch('?/saveRule', {
				method: 'POST',
				body: formData
			});

			const result = await res.json();
			let isSuccess = false;
			let successMsg = `Rule '${rule.name}' updated successfully!`;
			let errorMsg = `Failed to save rule '${rule.name}'.`;

			if (result.type === 'success') {
				let parsed = result.data;
				if (typeof parsed === 'string') {
					try { parsed = JSON.parse(parsed); } catch (e) {}
				}
				if (parsed?.success === false || parsed?.error) {
					errorMsg = parsed?.error || errorMsg;
				} else {
					isSuccess = true;
				}
			} else if (result.error) {
				errorMsg = result.error;
			}

			if (isSuccess) {
				triggerMessage = successMsg;
				setTimeout(() => (triggerMessage = ''), 2500);
				await loadEscalationData();
			} else {
				triggerMessage = errorMsg;
			}
		} catch (err) {
			console.error('Failed to save escalation rule:', err);
			triggerMessage = 'Error saving escalation rule.';
		}
	}

	function toggleSelectAll() {
		if (selectedAssignmentIds.length === filteredControls.length) {
			selectedAssignmentIds = [];
		} else {
			selectedAssignmentIds = filteredControls.map((c) => c.assignment.id).filter(Boolean);
		}
	}

	function toggleSelectControl(id: string) {
		if (selectedAssignmentIds.includes(id)) {
			selectedAssignmentIds = selectedAssignmentIds.filter((item) => item !== id);
		} else {
			selectedAssignmentIds.push(id);
		}
	}
</script>

<div class="space-y-6">
	<!-- Top Bar -->
	<div class="flex flex-wrap items-center justify-between gap-4 bg-surface-100-900/60 p-4 rounded-xl border border-surface-200-800">
		<div>
			<h3 class="font-bold text-base text-surface-900-100 flex items-center gap-2">
				<i class="fa-solid fa-bell text-rose-500"></i>
				<span>Automated Email & Notification Escalation Engine</span>
			</h3>
			<p class="text-xs text-surface-500">
				Configure intervals (minutes to days) and recipient target accounts for automated and manual bulk escalations.
			</p>
		</div>
	</div>

	{#if triggerMessage}
		<div class="text-xs p-3.5 rounded-xl font-semibold border flex items-center justify-between {triggerMessage.toLowerCase().includes('success') || triggerMessage.toLowerCase().includes('scheduled') || triggerMessage.toLowerCase().includes('updated') ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border-rose-500/30'}">
			<div class="flex items-center gap-2">
				<i class="fa-solid {triggerMessage.toLowerCase().includes('success') || triggerMessage.toLowerCase().includes('scheduled') || triggerMessage.toLowerCase().includes('updated') ? 'fa-circle-check text-emerald-400 text-sm' : 'fa-circle-exclamation text-rose-400 text-sm'}"></i>
				<span>{triggerMessage}</span>
			</div>
			<button onclick={() => (triggerMessage = '')} class="hover:opacity-75 cursor-pointer">
				<i class="fa-solid fa-xmark"></i>
			</button>
		</div>
	{/if}



	<!-- Bulk Control Escalation Panel -->
	<div class="p-5 rounded-2xl border border-surface-200-800 bg-surface-50-950 shadow-xs space-y-4">
		<div class="flex flex-wrap items-center justify-between gap-4 border-b border-surface-200-800 pb-3">
			<div>
				<h4 class="font-bold text-sm text-surface-900-100 uppercase tracking-wider flex items-center gap-2">
					<i class="fa-solid fa-paper-plane text-rose-500"></i>
					<span>1. Escalation Target Date Scheduler & Bulk Controls</span>
				</h4>
				<p class="text-xs text-surface-500 mt-0.5">
					Select assigned controls and click Level 1, Level 2, or Level 3 to dispatch instant escalation alerts.
				</p>
			</div>

			<!-- Level Escalation Buttons -->
			<div class="flex items-center gap-2 flex-wrap">
				<button
					onclick={() => openScheduleModal('L1')}
					disabled={filteredControls.length === 0}
					class="px-3.5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs shadow-xs flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
				>
					<i class="fa-solid fa-calendar-day text-[10px]"></i>
					<span>Schedule L1 (SPOC Reminder)</span>
				</button>
				<button
					onclick={() => openScheduleModal('L2')}
					disabled={filteredControls.length === 0}
					class="px-3.5 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs shadow-xs flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
				>
					<i class="fa-solid fa-calendar-week text-[10px]"></i>
					<span>Schedule L2 (Grace Period & Supervisor)</span>
				</button>
				<button
					onclick={() => openScheduleModal('L3')}
					disabled={filteredControls.length === 0}
					class="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs shadow-xs flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
				>
					<i class="fa-solid fa-calendar-xmark text-[10px]"></i>
					<span>Schedule L3 (FINAL Grace & Webadmin)</span>
				</button>
			</div>
		</div>

		<!-- Filters Bar -->
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 bg-surface-100-900/50 p-3 rounded-xl border border-surface-200-800">
			<div>
				<label class="text-[10px] font-bold text-surface-500 uppercase tracking-wider">Search Control</label>
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search ID or title..."
					class="w-full px-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100"
				/>
			</div>

			<div>
				<label class="text-[10px] font-bold text-surface-500 uppercase tracking-wider">Framework</label>
				<select
					bind:value={selectedFrameworkId}
					class="w-full px-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100"
				>
					<option value="">All Frameworks</option>
					{#each frameworks as fw}
						<option value={fw.id}>{fw.name}</option>
					{/each}
				</select>
			</div>

			<div>
				<label class="text-[10px] font-bold text-surface-500 uppercase tracking-wider">Status</label>
				<select
					bind:value={selectedStatusFilter}
					class="w-full px-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100"
				>
					<option value="">All Assigned Statuses</option>
					<option value="PENDING_SUBMISSION">Pending Evidence Submission</option>
					<option value="PENDING_REVIEW">Pending Reviewer Approval</option>
				</select>
			</div>

			<div>
				<label class="text-[10px] font-bold text-surface-500 uppercase tracking-wider">Assigned User (SPOC/Reviewer)</label>
				<select
					bind:value={selectedUserId}
					class="w-full px-3 py-1.5 text-xs rounded-lg border border-surface-200-800 bg-surface-50-950 text-surface-900-100"
				>
					<option value="">All Users</option>
					{#each assignedUsers as u}
						<option value={u.id}>{u.email}</option>
					{/each}
				</select>
			</div>
		</div>

		<!-- Table of Assigned Controls -->
		<div class="table-container border border-surface-200-800 rounded-xl overflow-hidden">
			<table class="table table-hover w-full text-xs">
				<thead class="bg-surface-100-900 border-b border-surface-200-800 text-surface-600-400">
					<tr>
						<th class="w-10 text-center py-3">
							<input
								type="checkbox"
								checked={filteredControls.length > 0 && selectedAssignmentIds.length === filteredControls.length}
								onchange={toggleSelectAll}
								class="rounded text-rose-600"
							/>
						</th>
						<th>Control Ref</th>
						<th>Title</th>
						<th>Framework</th>
						<th>Assigned SPOC</th>
						<th>Original Due</th>
						<th>L1 Date</th>
						<th>L2 Date</th>
						<th>L3 Date</th>
						<th>Level</th>
					</tr>
				</thead>
				<tbody>
					{#if filteredControls.length === 0}
						<tr>
							<td colspan="10" class="p-6 text-center text-surface-500">
								No assigned controls match your filters.
							</td>
						</tr>
					{:else}
						{#each filteredControls as c}
							<tr class="border-b border-surface-200-800/40">
								<td class="text-center">
									<input
										type="checkbox"
										checked={selectedAssignmentIds.includes(c.assignment.id)}
										onchange={() => toggleSelectControl(c.assignment.id)}
										class="rounded text-rose-600"
									/>
								</td>
								<td class="font-mono font-bold text-rose-500">{c.ref_id}</td>
								<td class="font-semibold text-surface-900-100">{c.name}</td>
								<td class="text-surface-500">{c.framework_name}</td>
								<td>
									<span class="text-amber-500 font-medium">{c.assignment.spoc_user?.email || 'Unassigned'}</span>
								</td>
								<td>
									{#if c.assignment.due_date}
										<span class="badge preset-outlined-surface-500 font-mono text-[11px]">{c.assignment.due_date}</span>
									{:else}
										<span class="text-surface-400 text-[11px] italic">Not set</span>
									{/if}
								</td>
								<td>
									{#if c.assignment.l1_reminder_date}
										<span class="badge preset-filled-warning-500 font-mono text-[11px]">{c.assignment.l1_reminder_date}</span>
									{:else}
										<span class="text-surface-400 text-[11px] italic">Not scheduled</span>
									{/if}
								</td>
								<td>
									{#if c.assignment.l2_grace_deadline}
										<span class="badge preset-filled-orange-500 font-mono text-[11px]">{c.assignment.l2_grace_deadline}</span>
									{:else}
										<span class="text-surface-400 text-[11px] italic">Not scheduled</span>
									{/if}
								</td>
								<td>
									{#if c.assignment.l3_final_deadline}
										<span class="badge preset-filled-error-500 font-mono text-[11px]">{c.assignment.l3_final_deadline}</span>
									{:else}
										<span class="text-surface-400 text-[11px] italic">Not scheduled</span>
									{/if}
								</td>
								<td>
									<span class="px-2.5 py-1 rounded-full text-[10px] font-mono font-bold border inline-block {getLevelBadgeClass(c.assignment.escalation_level)}">
										{getLevelLabel(c.assignment.escalation_level)}
									</span>
								</td>
							</tr>
						{/each}
					{/if}
				</tbody>
			</table>
		</div>
	</div>

	<!-- Escalation History Section (Collapsible & Hidden by Default) -->
	<div class="p-5 rounded-2xl border border-surface-200-800 bg-surface-50-950 shadow-xs space-y-4">
		<div class="flex items-center justify-between">
			<h4 class="font-bold text-sm text-surface-900-100 uppercase tracking-wider flex items-center gap-2">
				<i class="fa-solid fa-history text-rose-500"></i>
				<span>2. Escalation Audit Log History</span>
				<span class="px-2 py-0.5 rounded-full bg-surface-200-800 text-xs font-mono font-medium text-surface-700-300">
					{logs.length} logs
				</span>
			</h4>
			<button
				type="button"
				onclick={() => (showLogsTable = !showLogsTable)}
				class="px-3.5 py-1.5 rounded-lg border border-surface-200-800 bg-surface-100-900 text-xs font-medium text-surface-700-300 hover:bg-surface-200-800 hover:text-surface-900-100 transition-all flex items-center gap-2 cursor-pointer"
			>
				<i class="fa-solid {showLogsTable ? 'fa-chevron-up' : 'fa-chevron-down'} text-[10px]"></i>
				<span>{showLogsTable ? 'Hide Escalation Logs' : 'Show Escalation Logs'}</span>
			</button>
		</div>

		{#if showLogsTable}
			<div class="table-container border border-surface-200-800 rounded-xl overflow-hidden">
				<table class="table table-hover w-full text-xs">
					<thead class="bg-surface-100-900 border-b border-surface-200-800 text-surface-600-400">
						<tr>
							<th>Triggered Date</th>
							<th>Step / Level</th>
							<th>Recipient Email</th>
							<th>Control Ref</th>
							<th>Status</th>
						</tr>
					</thead>
					<tbody>
						{#if logs.length === 0}
							<tr>
								<td colspan="5" class="p-6 text-center text-surface-500">
									No escalation log records registered yet.
								</td>
							</tr>
						{:else}
							{#each logs as log}
								<tr class="border-b border-surface-200-800/40">
									<td class="font-mono text-surface-400">{log.created_at || log.escalation_date}</td>
									<td class="font-mono font-semibold text-surface-900-100">{log.step_label}</td>
									<td class="text-rose-500 font-medium">{log.recipient_email}</td>
									<td class="font-mono text-surface-300">{log.control_ref_id || 'N/A'}</td>
									<td>
										<span class="badge {log.email_sent ? 'variant-filled-success' : 'variant-filled-error'}">
											{log.email_sent ? 'DELIVERED' : 'FAILED'}
										</span>
									</td>
								</tr>
							{/each}
						{/if}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>

{#if scheduleModalOpen}
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
		<div class="w-full max-w-lg bg-surface-50-950 rounded-2xl border border-surface-200-800 shadow-2xl p-6 space-y-5">
			<div class="flex items-center justify-between border-b border-surface-200-800 pb-3">
				<h3 class="text-lg font-bold text-surface-900-100 flex items-center gap-2">
					<i class="fa-solid fa-calendar-check text-rose-500"></i>
					<span>Schedule {scheduleLevelName} Escalation</span>
				</h3>
				<button onclick={() => (scheduleModalOpen = false)} class="text-surface-400 hover:text-surface-900-100">
					<i class="fa-solid fa-xmark text-lg"></i>
				</button>
			</div>

			<div class="space-y-4">
				<div class="p-3 rounded-xl border border-surface-200-800 bg-surface-100-900/60 text-xs space-y-1.5">
					<div class="flex justify-between items-center">
						<span class="text-surface-400 font-medium">Original / Baseline Due Date:</span>
						<span class="font-mono font-bold text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
							{baselineDueDate || 'Not set'}
						</span>
					</div>
					<p class="text-surface-400 text-[11px]">
						Target Recipients: <strong class="text-surface-200">{scheduleLevelName === 'L1' ? 'SPOC' : scheduleLevelName === 'L2' ? 'SPOC & Supervisor' : 'SPOC, Supervisor & Webadmin'}</strong>
					</p>
				</div>

				<div class="space-y-2">
					<label class="text-xs font-semibold text-surface-700-300" for="grace-period-days">
						Grace Period (Days after Original Due / Baseline Date):
					</label>
					<div class="flex items-center gap-2">
						<input
							id="grace-period-days"
							type="number"
							min="0"
							bind:value={scheduleGraceDays}
							oninput={(e) => setGraceDays(parseInt((e.target as HTMLInputElement).value || '0'))}
							class="w-28 px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 font-mono"
						/>
						<span class="text-xs text-surface-400">days grace</span>
					</div>

					<!-- Quick Grace Presets -->
					<div class="flex flex-wrap gap-1.5 pt-1">
						<span class="text-[11px] text-surface-400 self-center mr-1">Quick Presets:</span>
						<button type="button" onclick={() => setGraceDays(1)} class="px-2.5 py-1 text-xs rounded border border-surface-200-800 bg-surface-100-900 hover:bg-surface-200-800 text-surface-300">+1 Day</button>
						<button type="button" onclick={() => setGraceDays(3)} class="px-2.5 py-1 text-xs rounded border border-surface-200-800 bg-surface-100-900 hover:bg-surface-200-800 text-surface-300">+3 Days</button>
						<button type="button" onclick={() => setGraceDays(5)} class="px-2.5 py-1 text-xs rounded border border-surface-200-800 bg-surface-100-900 hover:bg-surface-200-800 text-surface-300 font-bold text-rose-400">+5 Days</button>
						<button type="button" onclick={() => setGraceDays(7)} class="px-2.5 py-1 text-xs rounded border border-surface-200-800 bg-surface-100-900 hover:bg-surface-200-800 text-surface-300">+7 Days</button>
						<button type="button" onclick={() => setGraceDays(14)} class="px-2.5 py-1 text-xs rounded border border-surface-200-800 bg-surface-100-900 hover:bg-surface-200-800 text-surface-300">+14 Days</button>
					</div>
				</div>

				<div class="space-y-1.5 pt-1 border-t border-surface-200-800">
					<label class="text-xs font-semibold text-surface-700-300" for="escalation-target-date">
						Calculated Dispatch / Grace Deadline Date:
					</label>
					<input
						id="escalation-target-date"
						type="date"
						value={scheduleTargetDate}
						onchange={handleDateChange}
						class="w-full px-3 py-2 text-sm rounded-lg border border-surface-200-800 bg-surface-100-900 text-surface-900-100 font-mono"
					/>
				</div>

				<!-- Live Preview Box -->
				<div class="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-xs space-y-1">
					<div class="font-bold text-rose-400 flex items-center gap-1.5">
						<i class="fa-solid fa-clock"></i>
						<span>Schedule Summary Preview:</span>
					</div>
					<div class="text-surface-300">
						Original Due: <strong>{baselineDueDate || 'Not set'}</strong> &nbsp;+&nbsp; Grace: <strong>{scheduleGraceDays} Days</strong> &nbsp;➔&nbsp; <strong class="text-white bg-rose-600 px-1.5 py-0.5 rounded">{scheduleTargetDate}</strong>
					</div>
				</div>
			</div>

			<div class="flex items-center justify-end gap-3 pt-3 border-t border-surface-200-800">
				<button
					onclick={() => (scheduleModalOpen = false)}
					class="px-4 py-2 text-xs font-medium rounded-lg border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800"
				>
					Cancel
				</button>
				<button
					onclick={submitScheduleDate}
					disabled={!scheduleTargetDate}
					class="px-5 py-2 text-xs font-semibold rounded-lg bg-rose-600 text-white shadow-xs hover:bg-rose-700 disabled:opacity-50"
				>
					Confirm Schedule Date
				</button>
			</div>
		</div>
	</div>
{/if}
