import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch, locals }) => {
	const user = locals.user;
	if (!user) {
		return { hasPermission: false, assessments: [], frameworks: [], currentUser: null };
	}

	const isSuperAdmin = Boolean(user.is_superuser || user.platform_role === 'superadmin');
	const isWebAdmin = user.platform_role === 'webadmin';

	const hasPermission = isSuperAdmin || isWebAdmin;

	// Audit Reports page is OFF LIMITS for Admin & User accounts! Redirect to SPOC Submission page
	if (!hasPermission) {
		throw redirect(303, '/control-assignments/submit');
	}

	let assessments: any[] = [];
	let frameworks: any[] = [];

	try {
		const [assRes, ctrlRes] = await Promise.all([
			fetch(`${BASE_API_URL}/compliance-assessments/`),
			fetch(`${BASE_API_URL}/control-assignments/controls/`)
		]);

		if (assRes.ok) {
			const aData = await assRes.json();
			assessments = aData.results || aData || [];
		}

		if (ctrlRes.ok) {
			const cData = await ctrlRes.json();
			frameworks = (cData.frameworks || []).map((fw: any) => ({ id: fw.id, name: fw.name }));
		}
	} catch (e) {
		console.error('Error preloading report data:', e);
	}

	return {
		hasPermission,
		assessments,
		frameworks,
		currentUser: user
	};
};
