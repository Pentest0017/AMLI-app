<script lang="ts">
	import { onMount } from 'svelte';
	import { pageTitle } from '$lib/utils/stores';

	pageTitle.set('Report Templates');

	let activeTab = $state<'compliance' | 'intermediary_compliance'>('compliance');
	let loading = $state(true);
	let saving = $state(false);
	let successMessage = $state('');
	let errorMessage = $state('');

	// Page preview selection state
	let selectedPreviewPage = $state<number>(1); // 0 = All Pages, 1-5 = Specific Pages

	interface ReportTemplateConfig {
		id?: string;
		report_type: string;
		title: string;
		header_text: string;
		footer_text: string;
		company_name: string;
		primary_color: string;
		show_executive_summary: boolean;
		show_findings: boolean;
		show_evidence_details: boolean;
		show_activity_history: boolean;
		is_active: boolean;
		section_order: string[];
		custom_executive_summary_text: string;
		custom_concluding_notes: string;
		custom_findings_title: string;
		custom_evidence_title: string;
		custom_activity_title: string;
	}

	const defaultSectionOrder = ['executive_summary', 'findings', 'evidence_details', 'activity_history'];

	const SECTION_LABELS: Record<string, string> = {
		executive_summary: 'Executive Summary & Donut Chart',
		findings: 'Audit Findings & Rejections',
		evidence_details: 'Active & Historical Evidence Register',
		activity_history: 'Audit Trail & Assignment History'
	};

	let complianceConfig = $state<ReportTemplateConfig>({
		report_type: 'compliance',
		title: 'Security Audit Compliance Report',
		header_text: 'CONFIDENTIAL - FOR INTERNAL USE ONLY',
		footer_text: 'Enterprise Compliance & Risk Management Platform',
		company_name: 'Enterprise Compliance Organization',
		primary_color: '#4f46e5',
		show_executive_summary: true,
		show_findings: true,
		show_evidence_details: true,
		show_activity_history: true,
		is_active: true,
		section_order: ['executive_summary', 'findings', 'evidence_details', 'activity_history'],
		custom_executive_summary_text: 'This comprehensive audit report encapsulates overall organizational adherence to mandated cybersecurity standards, risk controls, and evidence validations.',
		custom_concluding_notes: 'All compliance assessments and evidence validations have been verified by authorized auditors. Continued compliance oversight is strictly maintained.',
		custom_findings_title: 'Audit Findings & Observations',
		custom_evidence_title: 'Evidence Register & Verification Records',
		custom_activity_title: 'Audit Activity Logs & Governance Trail'
	});

	let intermediaryConfig = $state<ReportTemplateConfig>({
		report_type: 'intermediary_compliance',
		title: 'Intermediary Compliance Audit Dossier',
		header_text: 'STRICTLY CONFIDENTIAL - AUDIT DOSSIER',
		footer_text: 'Intermediary Compliance Oversight Committee',
		company_name: 'Enterprise Compliance Organization',
		primary_color: '#0284c7',
		show_executive_summary: true,
		show_findings: true,
		show_evidence_details: true,
		show_activity_history: true,
		is_active: true,
		section_order: ['executive_summary', 'findings', 'evidence_details', 'activity_history'],
		custom_executive_summary_text: 'Official regulatory audit dossier evaluating intermediary partner compliance, business function alignment, and evidence repositories.',
		custom_concluding_notes: 'Intermediary compliance scores are updated dynamically based on reviewer feedback and partner submissions.',
		custom_findings_title: 'Intermediary Audit Findings & Non-Compliances',
		custom_evidence_title: 'Partner Uploaded Evidence Register',
		custom_activity_title: 'Intermediary Governance & Assignment Log'
	});

	let currentConfig = $derived(
		activeTab === 'compliance' ? complianceConfig : intermediaryConfig
	);

	function moveSectionUp(key: string) {
		const order = [...(currentConfig.section_order || defaultSectionOrder)];
		const idx = order.indexOf(key);
		if (idx > 0) {
			const temp = order[idx - 1];
			order[idx - 1] = order[idx];
			order[idx] = temp;
			currentConfig.section_order = order;
		}
	}

	function moveSectionDown(key: string) {
		const order = [...(currentConfig.section_order || defaultSectionOrder)];
		const idx = order.indexOf(key);
		if (idx >= 0 && idx < order.length - 1) {
			const temp = order[idx + 1];
			order[idx + 1] = order[idx];
			order[idx] = temp;
			currentConfig.section_order = order;
		}
	}

	async function loadConfigurations() {
		loading = true;
		errorMessage = '';
		try {
			const [cRes, iRes] = await Promise.all([
				fetch('/api/custom-report-templates/by-type/compliance/'),
				fetch('/api/custom-report-templates/by-type/intermediary_compliance/')
			]);

			if (cRes.ok) {
				const cData = await cRes.json();
				if (cData) {
					complianceConfig = {
						...complianceConfig,
						...cData,
						section_order: cData.section_order?.length ? cData.section_order : defaultSectionOrder
					};
				}
			}
			if (iRes.ok) {
				const iData = await iRes.json();
				if (iData) {
					intermediaryConfig = {
						...intermediaryConfig,
						...iData,
						section_order: iData.section_order?.length ? iData.section_order : defaultSectionOrder
					};
				}
			}
		} catch (err: any) {
			errorMessage = 'Failed to load report template configurations.';
		} finally {
			loading = false;
		}
	}

	async function saveCurrentTemplate() {
		saving = true;
		successMessage = '';
		errorMessage = '';
		const target = activeTab === 'compliance' ? complianceConfig : intermediaryConfig;

		try {
			let res;
			if (target.id) {
				res = await fetch(`/api/custom-report-templates/${target.id}/`, {
					method: 'PATCH',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(target)
				});
			} else {
				res = await fetch('/api/custom-report-templates/', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(target)
				});
			}

			if (res.ok) {
				const data = await res.json();
				if (activeTab === 'compliance') complianceConfig = { ...complianceConfig, ...data };
				else intermediaryConfig = { ...intermediaryConfig, ...data };
				successMessage = `Saved ${activeTab === 'compliance' ? 'Compliance Report' : 'Intermediary Compliance Report'} template settings successfully!`;
			} else {
				const errData = await res.json();
				errorMessage = errData.detail || 'Failed to save report template settings.';
			}
		} catch (err: any) {
			errorMessage = err.message || 'Error saving report template settings.';
		} finally {
			saving = false;
		}
	}

	function resetDefaults() {
		if (activeTab === 'compliance') {
			complianceConfig.title = 'Security Audit Compliance Report';
			complianceConfig.header_text = 'CONFIDENTIAL - FOR INTERNAL USE ONLY';
			complianceConfig.footer_text = 'Enterprise Compliance & Risk Management Platform';
			complianceConfig.company_name = 'Enterprise Compliance Organization';
			complianceConfig.primary_color = '#4f46e5';
			complianceConfig.show_executive_summary = true;
			complianceConfig.show_findings = true;
			complianceConfig.show_evidence_details = true;
			complianceConfig.show_activity_history = true;
			complianceConfig.section_order = [...defaultSectionOrder];
			complianceConfig.custom_executive_summary_text = 'This comprehensive audit report encapsulates overall organizational adherence to mandated cybersecurity standards, risk controls, and evidence validations.';
			complianceConfig.custom_concluding_notes = 'All compliance assessments and evidence validations have been verified by authorized auditors. Continued compliance oversight is strictly maintained.';
			complianceConfig.custom_findings_title = 'Audit Findings & Observations';
			complianceConfig.custom_evidence_title = 'Evidence Register & Verification Records';
			complianceConfig.custom_activity_title = 'Audit Activity Logs & Governance Trail';
		} else {
			intermediaryConfig.title = 'Intermediary Compliance Audit Dossier';
			intermediaryConfig.header_text = 'STRICTLY CONFIDENTIAL - AUDIT DOSSIER';
			intermediaryConfig.footer_text = 'Intermediary Compliance Oversight Committee';
			intermediaryConfig.company_name = 'Enterprise Compliance Organization';
			intermediaryConfig.primary_color = '#0284c7';
			intermediaryConfig.show_executive_summary = true;
			intermediaryConfig.show_findings = true;
			intermediaryConfig.show_evidence_details = true;
			intermediaryConfig.show_activity_history = true;
			intermediaryConfig.section_order = [...defaultSectionOrder];
			intermediaryConfig.custom_executive_summary_text = 'Official regulatory audit dossier evaluating intermediary partner compliance, business function alignment, and evidence repositories.';
			intermediaryConfig.custom_concluding_notes = 'Intermediary compliance scores are updated dynamically based on reviewer feedback and partner submissions.';
			intermediaryConfig.custom_findings_title = 'Intermediary Audit Findings & Non-Compliances';
			intermediaryConfig.custom_evidence_title = 'Partner Uploaded Evidence Register';
			intermediaryConfig.custom_activity_title = 'Intermediary Governance & Assignment Log';
		}
	}

	onMount(() => {
		loadConfigurations();
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
		<div>
			<h2 class="h2 font-extrabold flex items-center gap-3">
				<i class="fa-solid fa-file-invoice text-primary-500"></i>
				<span>Report Templates</span>
			</h2>
			<p class="text-sm text-surface-600-400 mt-1">
				Configure report layout, section arrangement, custom content commentary, header/footer notices, colors, and live page previews for generated audit dossiers.
			</p>
		</div>
	</div>

	{#if successMessage}
		<div class="alert preset-filled-success-500 p-3 flex items-center justify-between">
			<span class="flex items-center gap-2 text-sm font-medium">
				<i class="fa-solid fa-circle-check"></i>
				{successMessage}
			</span>
			<button class="btn btn-sm cursor-pointer" onclick={() => (successMessage = '')}>&times;</button>
		</div>
	{/if}

	{#if errorMessage}
		<div class="alert preset-filled-error-500 p-3 flex items-center justify-between">
			<span class="flex items-center gap-2 text-sm font-medium">
				<i class="fa-solid fa-triangle-exclamation"></i>
				{errorMessage}
			</span>
			<button class="btn btn-sm cursor-pointer" onclick={() => (errorMessage = '')}>&times;</button>
		</div>
	{/if}

	<!-- Report Type Tabs -->
	<div class="flex border-b border-surface-200-800 gap-2">
		<button
			class="px-4 py-2.5 font-semibold text-sm border-b-2 transition-all cursor-pointer flex items-center gap-2 {activeTab === 'compliance' ? 'border-primary-500 text-primary-500' : 'border-transparent text-surface-600-400 hover:text-surface-900-100'}"
			onclick={() => (activeTab = 'compliance')}
		>
			<i class="fa-solid fa-certificate"></i>
			<span>Compliance Audit Report</span>
		</button>
		<button
			class="px-4 py-2.5 font-semibold text-sm border-b-2 transition-all cursor-pointer flex items-center gap-2 {activeTab === 'intermediary_compliance' ? 'border-primary-500 text-primary-500' : 'border-transparent text-surface-600-400 hover:text-surface-900-100'}"
			onclick={() => (activeTab = 'intermediary_compliance')}
		>
			<i class="fa-solid fa-user-check"></i>
			<span>Intermediary Compliance Report</span>
		</button>
	</div>

	{#if loading}
		<div class="flex justify-center p-12">
			<i class="fa-solid fa-spinner fa-spin text-3xl text-primary-500"></i>
		</div>
	{:else}
		<div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
			<!-- Configuration & Arrangement Form -->
			<div class="lg:col-span-6 card bg-surface-50-950 p-6 border border-surface-200-800 rounded-2xl space-y-6 shadow-lg">
				<h3 class="h4 font-bold text-surface-900-100 flex items-center gap-2 border-b border-surface-200-800 pb-3">
					<i class="fa-solid fa-sliders text-primary-500"></i>
					<span>Template Layout & Section Contents</span>
				</h3>

				<div class="space-y-4">
					<div>
						<label class="label font-medium text-xs uppercase tracking-wider text-surface-500" for="report-title">Report Title</label>
						<input
							id="report-title"
							type="text"
							class="input mt-1 w-full text-sm"
							bind:value={currentConfig.title}
						/>
					</div>

					<div>
						<label class="label font-medium text-xs uppercase tracking-wider text-surface-500" for="company-name">Organization / Company Name</label>
						<input
							id="company-name"
							type="text"
							class="input mt-1 w-full text-sm"
							bind:value={currentConfig.company_name}
						/>
					</div>

					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
						<div>
							<label class="label font-medium text-xs uppercase tracking-wider text-surface-500" for="header-text">Header Text</label>
							<input
								id="header-text"
								type="text"
								class="input mt-1 w-full text-sm font-mono"
								bind:value={currentConfig.header_text}
							/>
						</div>

						<div>
							<label class="label font-medium text-xs uppercase tracking-wider text-surface-500" for="primary-color">Primary Accent Color</label>
							<div class="flex items-center gap-2 mt-1">
								<input
									type="color"
									id="primary-color"
									class="h-9 w-12 rounded cursor-pointer border border-surface-200-800 bg-transparent"
									bind:value={currentConfig.primary_color}
								/>
								<input
									type="text"
									class="input w-full text-sm font-mono"
									bind:value={currentConfig.primary_color}
								/>
							</div>
						</div>
					</div>

					<div>
						<label class="label font-medium text-xs uppercase tracking-wider text-surface-500" for="footer-text">Footer Disclaimer Text</label>
						<input
							id="footer-text"
							type="text"
							class="input mt-1 w-full text-sm font-mono"
							bind:value={currentConfig.footer_text}
						/>
					</div>

					<hr class="border-surface-200-800" />

					<!-- Section Arrangement & Reordering -->
					<div class="space-y-3">
						<div class="flex items-center justify-between">
							<span class="text-xs uppercase font-bold text-surface-500 tracking-wider">Report Section Arrangement</span>
							<span class="text-[11px] text-surface-400">Use ▲ ▼ to reorder dossier sections</span>
						</div>

						<div class="space-y-2">
							{#each currentConfig.section_order || defaultSectionOrder as secKey, idx}
								<div class="p-3 rounded-xl bg-surface-100-900 border border-surface-200-800 flex items-center justify-between gap-3">
									<div class="flex items-center gap-2 min-w-0">
										<span class="badge variant-soft-primary text-xs font-bold w-6 h-6 flex items-center justify-center shrink-0">{idx + 1}</span>
										<span class="text-xs font-semibold text-surface-900-100 truncate">{SECTION_LABELS[secKey] || secKey}</span>
									</div>

									<div class="flex items-center gap-1 shrink-0">
										<button
											class="btn btn-xs variant-soft-surface cursor-pointer disabled:opacity-30"
											disabled={idx === 0}
											onclick={() => moveSectionUp(secKey)}
											title="Move Up"
										>
											<i class="fa-solid fa-arrow-up text-[10px]"></i>
										</button>
										<button
											class="btn btn-xs variant-soft-surface cursor-pointer disabled:opacity-30"
											disabled={idx === (currentConfig.section_order || defaultSectionOrder).length - 1}
											onclick={() => moveSectionDown(secKey)}
											title="Move Down"
										>
											<i class="fa-solid fa-arrow-down text-[10px]"></i>
										</button>
									</div>
								</div>
							{/each}
						</div>
					</div>

					<hr class="border-surface-200-800" />

					<!-- Custom Content & Commentary Editors -->
					<div class="space-y-4">
						<span class="text-xs uppercase font-bold text-surface-500 tracking-wider block">Custom Section Titles & Contents</span>

						<div>
							<label class="label font-medium text-xs text-surface-700-300 mb-1 block">Executive Summary Custom Commentary</label>
							<textarea
								class="textarea text-xs w-full font-sans"
								rows="3"
								bind:value={currentConfig.custom_executive_summary_text}
								placeholder="Enter executive introduction text to appear on the report..."
							></textarea>
						</div>

						<div>
							<label class="label font-medium text-xs text-surface-700-300 mb-1 block">Findings Section Title</label>
							<input
								type="text"
								class="input text-xs w-full"
								bind:value={currentConfig.custom_findings_title}
								placeholder="Audit Findings & Observations"
							/>
						</div>

						<div>
							<label class="label font-medium text-xs text-surface-700-300 mb-1 block">Evidence Register Section Title</label>
							<input
								type="text"
								class="input text-xs w-full"
								bind:value={currentConfig.custom_evidence_title}
								placeholder="Evidence Register & Verification Records"
							/>
						</div>

						<div>
							<label class="label font-medium text-xs text-surface-700-300 mb-1 block">Audit Activity Section Title</label>
							<input
								type="text"
								class="input text-xs w-full"
								bind:value={currentConfig.custom_activity_title}
								placeholder="Audit Activity Logs & Governance Trail"
							/>
						</div>

						<div>
							<label class="label font-medium text-xs text-surface-700-300 mb-1 block">Custom Concluding Notes / Auditor Remarks</label>
							<textarea
								class="textarea text-xs w-full font-sans"
								rows="3"
								bind:value={currentConfig.custom_concluding_notes}
								placeholder="Enter auditor remarks or concluding disclaimer notes..."
							></textarea>
						</div>
					</div>

					<hr class="border-surface-200-800" />

					<!-- Section Visibility Toggles -->
					<div class="space-y-3">
						<span class="text-xs uppercase font-bold text-surface-500 tracking-wider">Section Visibility Toggles</span>

						<label class="flex items-center justify-between p-3 rounded-xl bg-surface-100-900 border border-surface-200-800 cursor-pointer">
							<span class="text-xs font-medium">Include Executive Summary & Donut Chart</span>
							<input type="checkbox" bind:checked={currentConfig.show_executive_summary} class="toggle toggle-primary" />
						</label>

						<label class="flex items-center justify-between p-3 rounded-xl bg-surface-100-900 border border-surface-200-800 cursor-pointer">
							<span class="text-xs font-medium">Include Audit Findings & Rejections</span>
							<input type="checkbox" bind:checked={currentConfig.show_findings} class="toggle toggle-primary" />
						</label>

						<label class="flex items-center justify-between p-3 rounded-xl bg-surface-100-900 border border-surface-200-800 cursor-pointer">
							<span class="text-xs font-medium">Include Active & Historical Evidence Register</span>
							<input type="checkbox" bind:checked={currentConfig.show_evidence_details} class="toggle toggle-primary" />
						</label>

						<label class="flex items-center justify-between p-3 rounded-xl bg-surface-100-900 border border-surface-200-800 cursor-pointer">
							<span class="text-xs font-medium">Include Audit Trail & Assignment History</span>
							<input type="checkbox" bind:checked={currentConfig.show_activity_history} class="toggle toggle-primary" />
						</label>
					</div>
				</div>

				<div class="flex items-center justify-between pt-4 border-t border-surface-200-800">
					<button
						class="btn preset-outlined-surface-500 font-semibold text-xs"
						type="button"
						onclick={resetDefaults}
					>
						<i class="fa-solid fa-rotate-left mr-1"></i>
						Reset Defaults
					</button>

					<button
						class="btn preset-filled-primary-500 font-bold px-6 text-xs"
						type="button"
						disabled={saving}
						onclick={saveCurrentTemplate}
					>
						{#if saving}
							<i class="fa-solid fa-spinner fa-spin mr-1"></i>
						{:else}
							<i class="fa-solid fa-check mr-1"></i>
						{/if}
						Save Template
					</button>
				</div>
			</div>

			<!-- Multi-Page Interactive PDF Live Preview -->
			<div class="lg:col-span-6 card bg-surface-50-950 p-6 border border-surface-200-800 rounded-2xl space-y-4 shadow-lg flex flex-col">
				<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-surface-200-800 pb-3">
					<h3 class="h4 font-bold text-surface-900-100 flex items-center gap-2">
						<i class="fa-solid fa-eye text-primary-500"></i>
						<span>PDF Report Live Preview</span>
					</h3>

					<!-- Page View Navigation Toolbar -->
					<div class="flex items-center gap-1 bg-surface-100-900 p-1 rounded-lg border border-surface-200-800">
						<button
							class="btn btn-xs variant-soft-surface cursor-pointer disabled:opacity-40"
							disabled={selectedPreviewPage <= 1}
							onclick={() => (selectedPreviewPage = Math.max(1, selectedPreviewPage - 1))}
							title="Previous Page"
						>
							<i class="fa-solid fa-chevron-left text-[10px]"></i>
						</button>

						<select
							class="select text-xs py-0.5 px-2 bg-transparent border-0 font-bold text-primary-500"
							bind:value={selectedPreviewPage}
						>
							<option value={1}>Page 1: Cover & Intro</option>
							<option value={2}>Page 2: Exec Summary & Chart</option>
							<option value={3}>Page 3: Audit Findings</option>
							<option value={4}>Page 4: Evidence Register</option>
							<option value={5}>Page 5: Audit Trail & Remarks</option>
							<option value={0}>All Pages (Continuous View)</option>
						</select>

						<button
							class="btn btn-xs variant-soft-surface cursor-pointer disabled:opacity-40"
							disabled={selectedPreviewPage >= 5 || selectedPreviewPage === 0}
							onclick={() => (selectedPreviewPage = Math.min(5, selectedPreviewPage + 1))}
							title="Next Page"
						>
							<i class="fa-solid fa-chevron-right text-[10px]"></i>
						</button>
					</div>
				</div>

				<!-- Page Navigation Pills Bar -->
				<div class="flex flex-wrap gap-1.5 pb-2">
					{#each [1, 2, 3, 4, 5] as pageNum}
						<button
							class="px-2.5 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer {selectedPreviewPage === pageNum ? 'bg-primary-500 text-white shadow-xs' : 'bg-surface-200-800 text-surface-600-400 hover:text-surface-900-100'}"
							onclick={() => (selectedPreviewPage = pageNum)}
						>
							Page {pageNum}
						</button>
					{/each}
					<button
						class="px-2.5 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer {selectedPreviewPage === 0 ? 'bg-indigo-600 text-white shadow-xs' : 'bg-surface-200-800 text-surface-600-400 hover:text-surface-900-100'}"
						onclick={() => (selectedPreviewPage = 0)}
					>
						View All Pages
					</button>
				</div>

				<!-- PDF Page Canvas Window -->
				<div class="flex-1 bg-slate-900/40 p-4 rounded-xl border border-surface-200-800 overflow-y-auto max-h-[700px] space-y-6">
					<!-- Page 1: Cover Page -->
					{#if selectedPreviewPage === 1 || selectedPreviewPage === 0}
						<div class="bg-white text-slate-900 rounded-xl p-6 shadow-2xl border border-slate-300 font-sans flex flex-col justify-between min-h-[520px]">
							<div>
								<div class="flex items-center justify-between pb-3 border-b border-slate-200 text-[10px] text-slate-500 font-mono">
									<span>{currentConfig.header_text || 'CONFIDENTIAL'}</span>
									<span class="font-bold text-indigo-600">Page 1 of 5</span>
								</div>

								<div class="mt-8 space-y-3 text-center py-8 px-4 rounded-xl shadow-xs" style="background-color: {currentConfig.primary_color}10; border-left: 5px solid {currentConfig.primary_color}">
									<span class="text-[11px] uppercase font-bold tracking-widest text-slate-500 block">{currentConfig.company_name}</span>
									<h3 class="text-2xl font-extrabold text-slate-900" style="color: {currentConfig.primary_color}">{currentConfig.title}</h3>
									<span class="text-xs text-slate-500 block font-medium">Audit Period 2026 &bull; Verified Production Scope</span>
								</div>

								{#if currentConfig.custom_executive_summary_text}
									<div class="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
										<p class="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Executive Overview</p>
										<p class="text-xs text-slate-700 leading-relaxed font-sans">{currentConfig.custom_executive_summary_text}</p>
									</div>
								{/if}

								<div class="mt-6 p-4 bg-indigo-50/50 rounded-lg border border-indigo-100 flex items-center justify-between text-xs">
									<div>
										<span class="font-bold text-slate-800 block text-xs">Overall Compliance Score</span>
										<span class="text-[10px] text-slate-500">Based on active control evaluation</span>
									</div>
									<span class="px-3 py-1 rounded-lg text-white font-bold text-xs" style="background-color: {currentConfig.primary_color}">100.0% COMPLIANT</span>
								</div>
							</div>

							<div class="pt-4 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-500 font-mono">
								<span>{currentConfig.footer_text}</span>
								<span>{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
							</div>
						</div>
					{/if}

					<!-- Page 2: Executive Summary & Donut Chart -->
					{#if (selectedPreviewPage === 2 || selectedPreviewPage === 0) && currentConfig.show_executive_summary}
						<div class="bg-white text-slate-900 rounded-xl p-6 shadow-2xl border border-slate-300 font-sans flex flex-col justify-between min-h-[520px]">
							<div>
								<div class="flex items-center justify-between pb-3 border-b border-slate-200 text-[10px] text-slate-500 font-mono">
									<span>{currentConfig.header_text || 'CONFIDENTIAL'}</span>
									<span class="font-bold text-indigo-600">Page 2 of 5</span>
								</div>

								<div class="mt-4 pb-2 border-b border-slate-200 flex items-center justify-between">
									<h4 class="text-sm font-bold text-slate-900 uppercase tracking-wider" style="color: {currentConfig.primary_color}">1. Executive Summary & Status Distribution</h4>
									<span class="badge bg-emerald-100 text-emerald-800 text-[10px] font-bold">STATUS: PASS</span>
								</div>

								<!-- Donut Chart Mockup -->
								<div class="mt-6 flex items-center justify-around p-4 bg-slate-50 rounded-xl border border-slate-200">
									<div class="relative w-28 h-28 rounded-full border-8 border-emerald-500 flex items-center justify-center bg-white shadow-xs">
										<span class="text-xs font-extrabold text-slate-900">100%</span>
									</div>
									<div class="space-y-2 text-xs">
										<p class="flex items-center gap-2 font-semibold text-slate-700"><span class="w-3 h-3 rounded-full bg-emerald-500"></span> Compliant Controls: <strong>24</strong></p>
										<p class="flex items-center gap-2 font-semibold text-slate-700"><span class="w-3 h-3 rounded-full bg-amber-500"></span> Pending Review: <strong>0</strong></p>
										<p class="flex items-center gap-2 font-semibold text-slate-700"><span class="w-3 h-3 rounded-full bg-rose-500"></span> Non-Compliant: <strong>0</strong></p>
									</div>
								</div>

								<div class="mt-6 space-y-2 text-xs">
									<p class="font-bold text-slate-800 text-[11px] uppercase tracking-wider">Section Arrangement Sequence:</p>
									<div class="grid grid-cols-2 gap-2">
										{#each currentConfig.section_order || defaultSectionOrder as sKey, i}
											<div class="p-2 rounded bg-slate-100 text-[11px] font-semibold text-slate-700 border border-slate-200 flex items-center gap-1.5">
												<span class="w-4 h-4 rounded-full bg-indigo-600 text-white text-[9px] font-bold flex items-center justify-center">{i + 1}</span>
												<span class="truncate">{SECTION_LABELS[sKey] || sKey}</span>
											</div>
										{/each}
									</div>
								</div>
							</div>

							<div class="pt-4 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-500 font-mono">
								<span>{currentConfig.footer_text}</span>
								<span>{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
							</div>
						</div>
					{/if}

					<!-- Page 3: Audit Findings & Rejections -->
					{#if (selectedPreviewPage === 3 || selectedPreviewPage === 0) && currentConfig.show_findings}
						<div class="bg-white text-slate-900 rounded-xl p-6 shadow-2xl border border-slate-300 font-sans flex flex-col justify-between min-h-[520px]">
							<div>
								<div class="flex items-center justify-between pb-3 border-b border-slate-200 text-[10px] text-slate-500 font-mono">
									<span>{currentConfig.header_text || 'CONFIDENTIAL'}</span>
									<span class="font-bold text-indigo-600">Page 3 of 5</span>
								</div>

								<div class="mt-4 pb-2 border-b border-slate-200 flex items-center justify-between">
									<h4 class="text-sm font-bold text-slate-900 uppercase tracking-wider" style="color: {currentConfig.primary_color}">
										2. {currentConfig.custom_findings_title || 'Audit Findings & Observations'}
									</h4>
								</div>

								<div class="mt-4 overflow-hidden rounded-lg border border-slate-200">
									<table class="w-full text-left text-[11px]">
										<thead class="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
											<tr>
												<th class="p-2">Control Ref</th>
												<th class="p-2">Control Name</th>
												<th class="p-2">Status</th>
												<th class="p-2">SPOC User</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-slate-200 text-slate-700">
											<tr>
												<td class="p-2 font-mono font-bold">ACC-01</td>
												<td class="p-2 font-medium">Access Control Policy & Review</td>
												<td class="p-2"><span class="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[9px] font-bold">COMPLIANT</span></td>
												<td class="p-2 text-slate-500">spoc1@test.com</td>
											</tr>
											<tr>
												<td class="p-2 font-mono font-bold">LOG-02</td>
												<td class="p-2 font-medium">Audit Logging & SIEM Centralization</td>
												<td class="p-2"><span class="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[9px] font-bold">COMPLIANT</span></td>
												<td class="p-2 text-slate-500">spoc2@test.com</td>
											</tr>
											<tr>
												<td class="p-2 font-mono font-bold">CRY-03</td>
												<td class="p-2 font-medium">Data Encryption at Rest & Transit</td>
												<td class="p-2"><span class="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[9px] font-bold">COMPLIANT</span></td>
												<td class="p-2 text-slate-500">spoc1@test.com</td>
											</tr>
										</tbody>
									</table>
								</div>
							</div>

							<div class="pt-4 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-500 font-mono">
								<span>{currentConfig.footer_text}</span>
								<span>{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
							</div>
						</div>
					{/if}

					<!-- Page 4: Evidence Register -->
					{#if (selectedPreviewPage === 4 || selectedPreviewPage === 0) && currentConfig.show_evidence_details}
						<div class="bg-white text-slate-900 rounded-xl p-6 shadow-2xl border border-slate-300 font-sans flex flex-col justify-between min-h-[520px]">
							<div>
								<div class="flex items-center justify-between pb-3 border-b border-slate-200 text-[10px] text-slate-500 font-mono">
									<span>{currentConfig.header_text || 'CONFIDENTIAL'}</span>
									<span class="font-bold text-indigo-600">Page 4 of 5</span>
								</div>

								<div class="mt-4 pb-2 border-b border-slate-200 flex items-center justify-between">
									<h4 class="text-sm font-bold text-slate-900 uppercase tracking-wider" style="color: {currentConfig.primary_color}">
										3. {currentConfig.custom_evidence_title || 'Evidence Register & Verification Records'}
									</h4>
								</div>

								<div class="mt-4 space-y-2">
									<div class="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-xs">
										<div class="flex items-center gap-2">
											<i class="fa-solid fa-file-pdf text-rose-600 text-base"></i>
											<div>
												<p class="font-bold text-slate-800 text-xs">Access_Control_Policy_2026.pdf</p>
												<p class="text-[10px] text-slate-500">SHA256: 8f9b4c2... • Verified 08 Sep 2026</p>
											</div>
										</div>
										<span class="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded">VERIFIED</span>
									</div>

									<div class="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-xs">
										<div class="flex items-center gap-2">
											<i class="fa-solid fa-file-csv text-emerald-600 text-base"></i>
											<div>
												<p class="font-bold text-slate-800 text-xs">SIEM_Log_Centralization_Audit.csv</p>
												<p class="text-[10px] text-slate-500">SHA256: e41b7a9... • Verified 08 Sep 2026</p>
											</div>
										</div>
										<span class="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded">VERIFIED</span>
									</div>
								</div>
							</div>

							<div class="pt-4 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-500 font-mono">
								<span>{currentConfig.footer_text}</span>
								<span>{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
							</div>
						</div>
					{/if}

					<!-- Page 5: Audit Trail & Concluding Remarks -->
					{#if (selectedPreviewPage === 5 || selectedPreviewPage === 0) && currentConfig.show_activity_history}
						<div class="bg-white text-slate-900 rounded-xl p-6 shadow-2xl border border-slate-300 font-sans flex flex-col justify-between min-h-[520px]">
							<div>
								<div class="flex items-center justify-between pb-3 border-b border-slate-200 text-[10px] text-slate-500 font-mono">
									<span>{currentConfig.header_text || 'CONFIDENTIAL'}</span>
									<span class="font-bold text-indigo-600">Page 5 of 5</span>
								</div>

								<div class="mt-4 pb-2 border-b border-slate-200 flex items-center justify-between">
									<h4 class="text-sm font-bold text-slate-900 uppercase tracking-wider" style="color: {currentConfig.primary_color}">
										4. {currentConfig.custom_activity_title || 'Audit Activity Logs & Governance Trail'}
									</h4>
								</div>

								<div class="mt-4 space-y-2 text-[11px]">
									<div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-slate-700">
										<span>08 Sep 2026 10:15 &bull; Audit Batch Created & SPOC Notifications Dispatched</span>
										<span class="font-mono text-slate-500">SYSTEM</span>
									</div>
									<div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-slate-700">
										<span>08 Sep 2026 11:30 &bull; SPOC Uploaded Evidence Attachment</span>
										<span class="font-mono text-slate-500">SPOC_USER</span>
									</div>
									<div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-slate-700">
										<span>08 Sep 2026 14:20 &bull; Approving Admin Approved Compliance Evidence</span>
										<span class="font-mono text-slate-500">ADMIN_REVIEWER</span>
									</div>
								</div>

								{#if currentConfig.custom_concluding_notes}
									<div class="mt-6 p-4 bg-slate-100 rounded-lg border border-slate-300 space-y-1">
										<p class="text-[10px] uppercase font-bold text-slate-600 tracking-wider">Auditor Concluding Remarks</p>
										<p class="text-xs text-slate-800 leading-relaxed font-sans">{currentConfig.custom_concluding_notes}</p>
									</div>
								{/if}
							</div>

							<div class="pt-4 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-500 font-mono">
								<span>{currentConfig.footer_text}</span>
								<span>{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
							</div>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>
