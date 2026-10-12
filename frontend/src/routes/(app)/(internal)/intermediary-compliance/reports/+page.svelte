<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	interface SummaryData {
		scope_type: 'FULL' | 'YEAR' | 'DOMAIN';
		scope_id: string;
		target_name: string;
		reporting_period: string;
		total_assigned: number;
		pending_evidence_count: number;
		under_review_count: number;
		approved_count: number;
		rejected_count: number;
		approved_compliance_rate: number;
		compliance_coverage: number;
		business_function_breakdown: Array<{
			domain_id: string;
			domain_name: string;
			year_name: string;
			total_assigned: number;
			pending_evidence: number;
			under_review: number;
			approved: number;
			rejected: number;
			compliance_rate: number;
			coverage: number;
		}>;
		partner_breakdown: Array<{
			partner_id: string;
			partner_name: string;
			domain_name: string;
			year_name: string;
			status: string;
			spoc: string;
			reviewer: string;
			last_submitted: string | null;
			last_reviewed: string | null;
			report_title?: string;
		}>;
		non_compliant_business_functions: any[];
		non_compliant_partners: any[];
	}

	interface GeneratedReport {
		id: string;
		title: string;
		scope_type: string;
		scope_name: string;
		reporting_period: string;
		generated_by: string;
		created_at: string;
		file_url: string;
	}

	let summary: SummaryData | null = $state(data?.summary ?? null);
	let scopesData = $state(data?.scopesData ?? { full_repository: null, years: [], business_functions: [] });
	let generatedReports: GeneratedReport[] = $state(data?.generatedReports ?? []);
	let isForbidden = $state(data?.isForbidden ?? false);

	// Scope Selector State
	let selectedScopeType: 'FULL' | 'YEAR' | 'DOMAIN' = $state('FULL');
	let selectedScopeId = $state('');
	let isLoading = $state(false);
	let isPdfGenerating = $state(false);

	$effect(() => {
		if (data?.summary) summary = data.summary;
		if (data?.scopesData) scopesData = data.scopesData;
		if (data?.generatedReports) generatedReports = data.generatedReports;
		if (typeof data?.isForbidden === 'boolean') isForbidden = data.isForbidden;
	});

	async function loadSummary() {
		isLoading = true;
		try {
			const targetId = selectedScopeType === 'FULL' ? '' : selectedScopeId;
			const url = `/api/intermediary-compliance/generate-report/?scope_type=${selectedScopeType}&scope_id=${targetId}`;
			const res = await fetch(url);
			if (res.status === 403) {
				isForbidden = true;
				summary = null;
			} else if (res.ok) {
				isForbidden = false;
				summary = await res.json();
			} else {
				summary = null;
			}
		} catch (err) {
			console.error('Error fetching intermediary compliance summary:', err);
			summary = null;
		} finally {
			isLoading = false;
		}
	}

	async function generatePdfDossier() {
		isPdfGenerating = true;
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

			const targetId = selectedScopeType === 'FULL' ? '' : selectedScopeId;
			const res = await fetch('/intermediary-compliance/reports/generate-pdf', {
				method: 'POST',
				headers,
				credentials: 'include',
				body: JSON.stringify({
					scope_type: selectedScopeType,
					scope_id: targetId
				})
			});

			if (res.ok) {
				const blob = await res.blob();
				const downloadUrl = window.URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = downloadUrl;
				a.download = `Intermediary_Compliance_${selectedScopeType}_${new Date().toISOString().slice(0, 10)}.pdf`;
				document.body.appendChild(a);
				a.click();
				a.remove();
				window.URL.revokeObjectURL(downloadUrl);

				// Refresh generated reports list
				const genRes = await fetch('/api/intermediary-compliance/generated-reports/', { credentials: 'include' });
				if (genRes.ok) {
					generatedReports = await genRes.json();
				}
			} else {
				let errText = 'Failed to generate PDF report.';
				try {
					const err = await res.json();
					errText = err.error || errText;
				} catch (e) {}
				alert(errText);
			}
		} catch (err) {
			console.error('Error generating PDF dossier:', err);
			alert('An error occurred during PDF generation.');
		} finally {
			isPdfGenerating = false;
		}
	}

	async function downloadGeneratedPdf(reportId: string, title: string) {
		try {
			const res = await fetch(`/api/intermediary-compliance/generated-reports/${reportId}/download/`);
			if (res.ok) {
				const blob = await res.blob();
				const downloadUrl = window.URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = downloadUrl;
				a.download = `${title}.pdf`;
				document.body.appendChild(a);
				a.click();
				a.remove();
				window.URL.revokeObjectURL(downloadUrl);
			}
		} catch (e) {
			console.error('Error downloading generated PDF:', e);
		}
	}
</script>

<div class="p-6 space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
		<div>
			<h1 class="text-2xl font-bold text-surface-900-100">Intermediary Compliance - Management Reporting</h1>
			<p class="text-sm text-surface-600-400">
				Executive compliance summaries, Business Function breakdowns, partner status tracking, and PDF audit dossiers.
			</p>
		</div>
		<div>
			<button
				class="btn variant-filled-primary font-semibold cursor-pointer disabled:opacity-50"
				disabled={isPdfGenerating || isForbidden}
				onclick={generatePdfDossier}
			>
				{#if isPdfGenerating}
					<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Generating PDF...
				{:else}
					<i class="fa-solid fa-file-pdf mr-1.5"></i> Generate PDF Audit Dossier
				{/if}
			</button>
		</div>
	</div>

	{#if !isForbidden}
		<!-- Strictly Controlled Hierarchical Scope Selector Card -->
		<div class="card p-5 shadow bg-surface-50-950 border border-surface-200-800 space-y-4">
			<div class="flex items-center space-x-2 border-b border-surface-200-800 pb-3">
				<i class="fa-solid fa-layer-group text-primary-500"></i>
				<h2 class="text-sm font-bold uppercase tracking-wider text-surface-900-100">Select Reporting Scope</h2>
			</div>

			<div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
				<!-- Scope Type -->
				<div>
					<label for="scope-type-select" class="text-xs font-bold text-surface-600-400 uppercase mb-1 block">Scope Level</label>
					<select
						id="scope-type-select"
						class="select w-full"
						bind:value={selectedScopeType}
						onchange={() => { selectedScopeId = ''; loadSummary(); }}
					>
						<option value="FULL">Full Repository (All Business Functions)</option>
						<option value="YEAR">Year Level Scope</option>
						<option value="DOMAIN">Business Function Scope</option>
					</select>
				</div>

				<!-- Scope Target Selector -->
				<div>
					{#if selectedScopeType === 'FULL'}
						<label for="full-repo-input" class="text-xs font-bold text-surface-600-400 uppercase mb-1 block">Target Scope</label>
						<input
							id="full-repo-input"
							type="text"
							class="input w-full bg-surface-100-900 cursor-not-allowed"
							value="All Available Business Functions & Years"
							disabled
						/>
					{:else if selectedScopeType === 'YEAR'}
						<label for="year-scope-select" class="text-xs font-bold text-surface-600-400 uppercase mb-1 block">Select Year</label>
						<select id="year-scope-select" class="select w-full" bind:value={selectedScopeId} onchange={loadSummary}>
							<option value="">-- Select Year --</option>
							{#each scopesData.years as y}
								<option value={y.id}>{y.name}</option>
							{/each}
						</select>
					{:else if selectedScopeType === 'DOMAIN'}
						<label for="domain-scope-select" class="text-xs font-bold text-surface-600-400 uppercase mb-1 block">Select Business Function</label>
						<select id="domain-scope-select" class="select w-full" bind:value={selectedScopeId} onchange={loadSummary}>
							<option value="">-- Select Business Function --</option>
							{#each scopesData.business_functions as d}
								<option value={d.id}>{d.name} ({d.year_name})</option>
							{/each}
						</select>
					{/if}
				</div>

				<!-- Action Button -->
				<div>
					<button
						class="btn variant-filled-primary w-full cursor-pointer disabled:opacity-50"
						disabled={isLoading}
						onclick={loadSummary}
					>
						{#if isLoading}
							<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Loading Metrics...
						{:else}
							<i class="fa-solid fa-filter mr-1.5"></i> Apply Scope
						{/if}
					</button>
				</div>
			</div>
		</div>
	{/if}

	{#if isForbidden}
		<div class="card p-16 text-center space-y-4 bg-surface-50-950 border border-surface-200-800 shadow-xl rounded-container">
			<i class="fa-solid fa-shield-halved text-6xl text-surface-400"></i>
			<h2 class="text-3xl font-extrabold tracking-tight">ACCESS RESTRICTED</h2>
			<p class="text-surface-600-400 max-w-md mx-auto">
				Report generation is available only to assigned SPOCs, Reviewers, and System Administrators.
			</p>
		</div>
	{:else if summary}
		<!-- KPI Executive Summary Cards -->
		<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
			<div class="card p-3 bg-surface-100-900 border border-surface-200-800 text-center">
				<p class="text-2xl font-black text-surface-900-100">{summary.total_assigned}</p>
				<p class="text-[10px] uppercase font-bold text-surface-500 tracking-wider mt-1">Total Assigned</p>
			</div>

			<div class="card p-3 bg-surface-100-900 border border-surface-200-800 text-center">
				<p class="text-2xl font-black text-surface-500">{summary.pending_evidence_count}</p>
				<p class="text-[10px] uppercase font-bold text-surface-500 tracking-wider mt-1">Pending Evidence</p>
			</div>

			<div class="card p-3 bg-amber-500/10 border border-amber-500/20 text-center">
				<p class="text-2xl font-black text-amber-500">{summary.under_review_count}</p>
				<p class="text-[10px] uppercase font-bold text-amber-500 tracking-wider mt-1">Under Review</p>
			</div>

			<div class="card p-3 bg-success-500/10 border border-success-500/20 text-center">
				<p class="text-2xl font-black text-success-500">{summary.approved_count}</p>
				<p class="text-[10px] uppercase font-bold text-success-500 tracking-wider mt-1">Approved</p>
			</div>

			<div class="card p-3 bg-error-500/10 border border-error-500/20 text-center">
				<p class="text-2xl font-black text-error-500">{summary.rejected_count}</p>
				<p class="text-[10px] uppercase font-bold text-error-500 tracking-wider mt-1">Rejected</p>
			</div>

			<div class="card p-3 bg-primary-500/10 border border-primary-500/20 text-center">
				<p class="text-2xl font-black text-primary-500">{summary.approved_compliance_rate}%</p>
				<p class="text-[10px] uppercase font-bold text-primary-500 tracking-wider mt-1">Approved Rate</p>
			</div>

			<div class="card p-3 bg-sky-500/10 border border-sky-500/20 text-center">
				<p class="text-2xl font-black text-sky-500">{summary.compliance_coverage}%</p>
				<p class="text-[10px] uppercase font-bold text-sky-500 tracking-wider mt-1">Coverage Rate</p>
			</div>
		</div>

		<!-- Business Function Breakdown Table -->
		<div class="card p-6 shadow-md bg-surface-50-950 space-y-4 border border-surface-200-800">
			<div class="flex justify-between items-center border-b border-surface-200-800 pb-3">
				<h2 class="text-lg font-bold text-surface-900-100">
					Business Function Compliance Breakdown
				</h2>
				<span class="badge variant-soft-primary font-mono text-xs">{summary.target_name}</span>
			</div>

			<div class="overflow-x-auto">
				<table class="table table-hover w-full text-sm">
					<thead>
						<tr class="bg-surface-100-900">
							<th>Business Function</th>
							<th>Year</th>
							<th class="text-center">Assigned</th>
							<th class="text-center">Pending Evidence</th>
							<th class="text-center">Under Review</th>
							<th class="text-center">Approved</th>
							<th class="text-center">Rejected</th>
							<th class="text-center">Approved Rate (%)</th>
							<th class="text-center">Coverage (%)</th>
						</tr>
					</thead>
					<tbody>
						{#each summary.business_function_breakdown as bf}
							<tr>
								<td class="font-semibold">{bf.domain_name}</td>
								<td class="text-surface-500">{bf.year_name}</td>
								<td class="text-center font-mono font-bold">{bf.total_assigned}</td>
								<td class="text-center font-mono text-surface-500">{bf.pending_evidence}</td>
								<td class="text-center font-mono text-amber-500 font-bold">{bf.under_review}</td>
								<td class="text-center font-mono text-success-500 font-bold">{bf.approved}</td>
								<td class="text-center font-mono text-error-500 font-bold">{bf.rejected}</td>
								<td class="text-center font-mono font-bold text-primary-500">{bf.compliance_rate}%</td>
								<td class="text-center font-mono font-bold text-sky-500">{bf.coverage}%</td>
							</tr>
						{:else}
							<tr>
								<td colspan="9" class="text-center py-6 text-surface-500">No Business Functions found for selected scope.</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<!-- Partner Breakdown Table -->
		<div class="card p-6 shadow-md bg-surface-50-950 space-y-4 border border-surface-200-800">
			<div class="flex justify-between items-center border-b border-surface-200-800 pb-3">
				<h2 class="text-lg font-bold text-surface-900-100">
					Partner Compliance Statuses
				</h2>
				<span class="text-xs text-surface-500 font-mono">Total Partners: {summary.partner_breakdown.length}</span>
			</div>

			<div class="overflow-x-auto max-h-[400px]">
				<table class="table table-hover w-full text-sm">
					<thead>
						<tr class="bg-surface-100-900">
							<th>Partner Name</th>
							<th>Business Function</th>
							<th>Year</th>
							<th>Status</th>
							<th>SPOC</th>
							<th>Reviewer</th>
							<th>Last Submitted</th>
							<th>Last Reviewed</th>
						</tr>
					</thead>
					<tbody>
						{#each summary.partner_breakdown as pb}
							<tr>
								<td class="font-bold">{pb.partner_name}</td>
								<td>{pb.domain_name}</td>
								<td class="text-surface-500">{pb.year_name}</td>
								<td>
									{#if pb.status === 'APPROVED / COMPLIANT'}
										<span class="badge variant-filled-success font-semibold text-xs">APPROVED</span>
									{:else if pb.status === 'REJECTED / NON-COMPLIANT'}
										<span class="badge variant-filled-error font-semibold text-xs">REJECTED</span>
									{:else if pb.status === 'UNDER REVIEW'}
										<span class="badge variant-filled-warning font-semibold text-xs">UNDER REVIEW</span>
									{:else}
										<span class="badge variant-soft font-semibold text-xs text-surface-500">PENDING EVIDENCE</span>
									{/if}
								</td>
								<td class="text-xs text-surface-600-400">{pb.spoc}</td>
								<td class="text-xs text-surface-600-400">{pb.reviewer}</td>
								<td class="text-xs font-mono">{pb.last_submitted || '--'}</td>
								<td class="text-xs font-mono">{pb.last_reviewed || '--'}</td>
							</tr>
						{:else}
							<tr>
								<td colspan="8" class="text-center py-6 text-surface-500">No partner requirements assigned under scope.</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<!-- Non-Compliant & At-Risk Entities Section -->
		{#if summary.non_compliant_partners.length > 0}
			<div class="card p-6 shadow-md bg-error-500/5 border border-error-500/30 space-y-3">
				<div class="flex items-center space-x-2 text-error-500 border-b border-error-500/20 pb-2">
					<i class="fa-solid fa-triangle-exclamation text-lg"></i>
					<h3 class="text-base font-bold uppercase tracking-wide">Attention Required &mdash; Non-Compliant / At-Risk Partners ({summary.non_compliant_partners.length})</h3>
				</div>
				<ul class="space-y-2 text-sm">
					{#each summary.non_compliant_partners as ncp}
						<li class="flex flex-col md:flex-row justify-between p-2 rounded bg-surface-50-950 border border-surface-200-800">
							<div>
								<span class="font-bold text-surface-900-100">{ncp.partner_name}</span>
								<span class="text-surface-500 text-xs ml-2">({ncp.domain_name} &bull; {ncp.year_name})</span>
							</div>
							<div class="flex items-center space-x-3 text-xs mt-1 md:mt-0">
								<span class="font-semibold text-surface-500">SPOC: {ncp.spoc}</span>
								<span class="font-semibold text-surface-500">Reviewer: {ncp.reviewer}</span>
								<span class="badge variant-filled-error">{ncp.status}</span>
							</div>
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Generated Reports History Section -->
		<div class="card p-6 shadow-md bg-surface-50-950 space-y-4 border border-surface-200-800">
			<div class="flex justify-between items-center border-b border-surface-200-800 pb-3">
				<div class="flex items-center space-x-2">
					<i class="fa-solid fa-history text-primary-500"></i>
					<h2 class="text-lg font-bold text-surface-900-100">Generated Reports Archive</h2>
				</div>
				<span class="text-xs text-surface-500 font-mono">Total Saved PDFs: {generatedReports.length}</span>
			</div>

			<div class="overflow-x-auto">
				<table class="table table-hover w-full text-sm">
					<thead>
						<tr class="bg-surface-100-900">
							<th>Report Title</th>
							<th>Scope Level</th>
							<th>Reporting Period</th>
							<th>Generated By</th>
							<th>Date Generated</th>
							<th class="text-right">Action</th>
						</tr>
					</thead>
					<tbody>
						{#each generatedReports as gr}
							<tr>
								<td class="font-bold text-primary-500">{gr.title}</td>
								<td><span class="badge variant-soft-primary text-xs">{gr.scope_name}</span></td>
								<td class="text-surface-500 font-mono text-xs">{gr.reporting_period}</td>
								<td class="text-xs">{gr.generated_by}</td>
								<td class="text-xs font-mono">{gr.created_at}</td>
								<td class="text-right">
									<button
										class="btn btn-sm variant-soft-primary cursor-pointer"
										onclick={() => downloadGeneratedPdf(gr.id, gr.title)}
									>
										<i class="fa-solid fa-download mr-1"></i> Download PDF
									</button>
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="6" class="text-center py-6 text-surface-500">No generated PDF reports saved yet. Click "Generate PDF Audit Dossier" above to create one.</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
