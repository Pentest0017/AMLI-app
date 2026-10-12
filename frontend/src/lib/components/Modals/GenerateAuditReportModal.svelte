<script lang="ts">
	import { fade, scale } from 'svelte/transition';

	interface Props {
		open: boolean;
		audit: { id: string; name: string; framework_name?: string } | null;
		onClose: () => void;
	}

	let { open, audit, onClose }: Props = $props();

	let reportType = $state<'full' | 'executive' | 'detailed'>('full');
	let generating = $state(false);

	let sections = $state({
		executive_summary: true,
		audit_info: true,
		scope_framework: true,
		compliance_overview: true,
		requirement_results: true,
		evidence_details: true,
		assignments: true,
		findings_observations: true,
		action_plans: true,
		activity_history: true,
		appendix: true
	});

	function handleReportTypeChange(type: 'full' | 'executive' | 'detailed') {
		reportType = type;
		if (type === 'full') {
			sections = {
				executive_summary: true,
				audit_info: true,
				scope_framework: true,
				compliance_overview: true,
				requirement_results: true,
				evidence_details: true,
				assignments: true,
				findings_observations: true,
				action_plans: true,
				activity_history: true,
				appendix: true
			};
		} else if (type === 'executive') {
			sections = {
				executive_summary: true,
				audit_info: true,
				scope_framework: true,
				compliance_overview: true,
				requirement_results: false,
				evidence_details: false,
				assignments: false,
				findings_observations: true,
				action_plans: true,
				activity_history: false,
				appendix: false
			};
		} else if (type === 'detailed') {
			sections = {
				executive_summary: true,
				audit_info: true,
				scope_framework: false,
				compliance_overview: true,
				requirement_results: true,
				evidence_details: true,
				assignments: true,
				findings_observations: true,
				action_plans: true,
				activity_history: true,
				appendix: true
			};
		}
	}

	let errorMessage = $state('');

	function getCookie(name: string): string {
		if (typeof document === 'undefined') return '';
		const value = `; ${document.cookie}`;
		const parts = value.split(`; ${name}=`);
		if (parts.length === 2) return parts.pop()?.split(';').shift() || '';
		return '';
	}

	async function generatePDF() {
		if (!audit) return;
		generating = true;
		errorMessage = '';

		const activeSections = Object.entries(sections)
			.filter(([_, enabled]) => enabled)
			.map(([key]) => key);

		try {
			let token = getCookie('csrftoken');
			if (!token) {
				try {
					const csrfRes = await fetch('/api/csrf/', { credentials: 'include' });
					if (csrfRes.ok) {
						const csrfData = await csrfRes.json();
						token = csrfData.csrfToken || '';
					}
				} catch (e) {}
			}

			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
				'Accept': 'application/pdf, application/json'
			};
			if (token) {
				headers['X-CSRFToken'] = token;
			}

			const res = await fetch(`/compliance-assessments/${audit.id}/generate-pdf-report`, {
				method: 'POST',
				headers,
				credentials: 'include',
				body: JSON.stringify({
					report_type: reportType,
					sections: activeSections
				})
			});

			if (!res.ok) {
				let errText = 'Failed to generate audit report PDF.';
				try {
					const err = await res.json();
					errText = err.error || errText;
				} catch (e) {}
				errorMessage = errText;
				return;
			}

			// Extract filename from header if present
			const disposition = res.headers.get('Content-Disposition');
			let filename = `${audit.name.replace(/[^a-zA-Z0-9_-]/g, '_')}_Audit_Report.pdf`;
			if (disposition && disposition.includes('filename=')) {
				const match = disposition.match(/filename="?([^"]+)"?/);
				if (match && match[1]) filename = match[1];
			}

			const blob = await res.blob();
			const downloadUrl = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = downloadUrl;
			link.download = filename;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			window.URL.revokeObjectURL(downloadUrl);

			onClose();
		} catch (err: any) {
			console.error('Error generating report:', err);
			errorMessage = 'Network error generating PDF report: ' + (err.message || err);
		} finally {
			generating = false;
		}
	}
</script>

{#if open && audit}
	<div
		transition:fade={{ duration: 150 }}
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
	>
		<div
			transition:scale={{ duration: 150, start: 0.95 }}
			class="w-full max-w-2xl bg-surface-100-900 border border-surface-200-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
		>
			<!-- Header -->
			<div class="px-6 py-4 border-b border-surface-200-800 bg-surface-50-950 flex items-center justify-between">
				<div class="flex items-center gap-3">
					<div class="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-500 border border-indigo-500/20 flex items-center justify-center text-lg">
						<i class="fa-solid fa-file-pdf"></i>
					</div>
					<div>
						<h3 class="font-bold text-base text-surface-900-100">Generate Audit PDF Report</h3>
						<p class="text-xs text-surface-500 font-mono truncate max-w-md">{audit.name}</p>
					</div>
				</div>
				<button
					onclick={onClose}
					disabled={generating}
					class="p-2 text-surface-500 hover:text-surface-900-100 rounded-lg transition-colors cursor-pointer"
				>
					<i class="fa-solid fa-xmark text-lg"></i>
				</button>
			</div>

			<!-- Body -->
			<div class="p-6 overflow-y-auto space-y-6">
				{#if errorMessage}
					<div class="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs font-semibold flex items-center justify-between">
						<span class="flex items-center gap-2">
							<i class="fa-solid fa-circle-exclamation"></i>
							<span>{errorMessage}</span>
						</span>
						<button onclick={() => (errorMessage = '')} class="hover:opacity-75">
							<i class="fa-solid fa-xmark"></i>
						</button>
					</div>
				{/if}
				<!-- Report Type Cards -->
				<div>
					<label class="block text-xs font-bold uppercase tracking-wider text-surface-500 mb-3">Report Type</label>
					<div class="grid grid-cols-3 gap-3">
						<button
							type="button"
							onclick={() => handleReportTypeChange('full')}
							class="p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between {reportType === 'full' ? 'bg-indigo-500/10 border-indigo-500 text-indigo-500 ring-2 ring-indigo-500/20' : 'bg-surface-50-950 border-surface-200-800 hover:border-surface-400'}"
						>
							<div class="flex items-center justify-between w-full mb-1">
								<span class="font-bold text-sm">Full Audit Report</span>
								<i class="fa-solid fa-book text-xs"></i>
							</div>
							<p class="text-[11px] opacity-80">Complete audit dossier containing all requirements, evidence, and activity log.</p>
						</button>

						<button
							type="button"
							onclick={() => handleReportTypeChange('executive')}
							class="p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between {reportType === 'executive' ? 'bg-indigo-500/10 border-indigo-500 text-indigo-500 ring-2 ring-indigo-500/20' : 'bg-surface-50-950 border-surface-200-800 hover:border-surface-400'}"
						>
							<div class="flex items-center justify-between w-full mb-1">
								<span class="font-bold text-sm">Executive Summary</span>
								<i class="fa-solid fa-chart-pie text-xs"></i>
							</div>
							<p class="text-[11px] opacity-80">Management-oriented report with high-level compliance metrics & findings.</p>
						</button>

						<button
							type="button"
							onclick={() => handleReportTypeChange('detailed')}
							class="p-3.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between {reportType === 'detailed' ? 'bg-indigo-500/10 border-indigo-500 text-indigo-500 ring-2 ring-indigo-500/20' : 'bg-surface-50-950 border-surface-200-800 hover:border-surface-400'}"
						>
							<div class="flex items-center justify-between w-full mb-1">
								<span class="font-bold text-sm">Controls & Evidence</span>
								<i class="fa-solid fa-list-check text-xs"></i>
							</div>
							<p class="text-[11px] opacity-80">Focuses on control register, evidence verification, and review history.</p>
						</button>
					</div>
				</div>

				<!-- Section Checkboxes -->
				<div>
					<label class="block text-xs font-bold uppercase tracking-wider text-surface-500 mb-3">Include Report Sections</label>
					<div class="grid grid-cols-2 gap-2.5 bg-surface-50-950 p-4 rounded-xl border border-surface-200-800 text-xs">
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.executive_summary} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Executive Summary & Metrics</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.audit_info} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Audit Information & Metadata</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.scope_framework} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Scope & Framework Details</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.compliance_overview} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Domain-Level Breakdown</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.requirement_results} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Full Control & Requirement Register</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.evidence_details} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Evidence Register & History</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.assignments} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Control Assignments</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.findings_observations} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Reviewer Findings & Observations</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.action_plans} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Action Plans / Remediation</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer">
							<input type="checkbox" bind:checked={sections.activity_history} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Audit Activity & Chronological Log</span>
						</label>
						<label class="flex items-center gap-2.5 cursor-pointer col-span-2">
							<input type="checkbox" bind:checked={sections.appendix} class="rounded border-surface-300 text-indigo-600 focus:ring-indigo-500" />
							<span>Official Audit Sign-Off Block & Appendix</span>
						</label>
					</div>
				</div>
			</div>

			<!-- Footer -->
			<div class="px-6 py-4 border-t border-surface-200-800 bg-surface-50-950 flex items-center justify-end gap-3">
				<button
					type="button"
					onclick={onClose}
					disabled={generating}
					class="px-4 py-2 rounded-xl border border-surface-200-800 text-surface-700-300 hover:bg-surface-200-800 text-xs font-semibold transition-all cursor-pointer"
				>
					Cancel
				</button>
				<button
					type="button"
					onclick={generatePDF}
					disabled={generating}
					class="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-md flex items-center gap-2 cursor-pointer disabled:opacity-50"
				>
					{#if generating}
						<i class="fa-solid fa-circle-notch fa-spin"></i>
						<span>Compiling PDF Report...</span>
					{:else}
						<i class="fa-solid fa-file-pdf"></i>
						<span>Generate PDF</span>
					{/if}
				</button>
			</div>
		</div>
	</div>
{/if}
