import type { LayoutServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';
import { loadFlash, setFlash } from 'sveltekit-flash-message/server';

const ROUTE_FEATURE_MAP: Record<string, string[]> = {
	'/users': ['users'],
	'/logs': ['logs'],
	'/features': ['features', 'accessRights'],
	'/risk-assessments': ['riskAssessments'],
	'/compliance-assessments': ['complianceAssessments'],
	'/vulnerabilities': ['vulnerabilities'],
	'/incidents': ['incidents'],
	'/ebios-rm': ['ebiosRM'],
	'/quantitative-risk-studies': ['quantitativeRiskStudies'],
	'/privacy': ['processingsRegister'],
	'/tprm': ['tprm', 'tprmOverview'],
	'/analytics': ['analytics'],
	'/reports': ['reports'],
	'/company-hierarchy': ['companyHierarchy'],
	'/frameworks': ['frameworks'],
	'/threats': ['threats'],
	'/security-advisories': ['securityAdvisories'],
	'/cwes': ['cwes'],
	'/reference-controls': ['referenceControls'],
	'/requirement-mapping-sets': ['requirementMappingSets'],
	'/risk-matrices': ['riskMatrices'],
	'/assets': ['assets'],
	'/applied-controls': ['appliedControls'],
	'/documents': ['documents'],
	'/calendar': ['calendar'],
	'/x-rays': ['xRays'],
	'/tasks': ['tasks'],
	'/libraries': ['libraries'],
	'/stored-libraries': ['libraries'],
	'/policies': ['policies'],
	'/organisation-issues': ['organisationIssues'],
	'/organisation-objectives': ['organisationObjectives'],
	'/risk-acceptances': ['riskAcceptances'],
	'/security-exceptions': ['securityExceptions'],
	'/intermediary-compliance/assignments': ['intermediaryAssignments'],
	'/intermediary-compliance/repository': ['reportRepository'],
	'/intermediary-compliance/reports': ['reportGeneration'],
	'/control-assignments': ['controlAssignments'],
	'/evidence-repository': ['evidenceRepository'],
	'/escalation': ['escalationRules'],
	'/defaulters-tracker': ['defaultersTracker'],
	'/evidences': ['evidences'],
	'/recap': ['recap'],
	'/mail-templates': ['mailTemplates'],
	'/report-templates': ['reportTemplates'],
	'/assignment-settings': ['assignmentSettings']
};

export const load = loadFlash(async (event) => {
	const { locals, url } = event;
	if (locals.user?.is_third_party) {
		redirect(302, `/auditee-dashboard`);
	}

	const user = locals.user;
	if (user) {
		const isSuperadmin = Boolean(user.is_superuser || user.platform_role === 'superadmin');
		if (!isSuperadmin) {
			const activeFeatures = Array.isArray(user.active_features) ? user.active_features : [];
			const pathname = url.pathname;

			for (const [routePrefix, featureKeys] of Object.entries(ROUTE_FEATURE_MAP)) {
				if (pathname === routePrefix || pathname.startsWith(routePrefix + '/')) {
					const hasAccess = featureKeys.some((k) => activeFeatures.includes(k));
					if (!hasAccess) {
						setFlash(
							{ type: 'error', message: 'Access to this feature is disabled for your role.' },
							event
						);
						if (pathname !== '/') {
							redirect(302, '/');
						}
					}
				}
			}
		}
	}

	return { user: locals.user };
}) satisfies LayoutServerLoad;
