import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, url }) => {
	try {
		const scopeType = url.searchParams.get('scope_type') || 'FULL';
		const scopeId = url.searchParams.get('scope_id') || url.searchParams.get('folder_id') || '';

		const reportUrl = `${BASE_API_URL}/intermediary-compliance/generate-report/?scope_type=${scopeType}&scope_id=${scopeId}`;
		const scopesUrl = `${BASE_API_URL}/intermediary-compliance/scopes/`;
		const generatedUrl = `${BASE_API_URL}/intermediary-compliance/generated-reports/`;

		const [metricsRes, scopesRes, generatedRes] = await Promise.all([
			fetch(reportUrl),
			fetch(scopesUrl),
			fetch(generatedUrl)
		]);

		const summary = metricsRes.ok ? await metricsRes.json() : null;
		const scopesData = scopesRes.ok ? await scopesRes.json() : { full_repository: null, years: [], business_functions: [] };
		const generatedReports = generatedRes.ok ? await generatedRes.json() : [];

		return {
			summary,
			scopesData,
			generatedReports,
			isForbidden: metricsRes.status === 403
		};
	} catch (err) {
		console.error('Error loading intermediary compliance report page data:', err);
		return {
			summary: null,
			scopesData: { full_repository: null, years: [], business_functions: [] },
			generatedReports: [],
			isForbidden: false
		};
	}
};
