import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';

export const load: PageServerLoad = async ({ fetch, locals }) => {
	try {
		const res = await fetch(`${BASE_API_URL}/control-assignments/controls/`);
		if (!res.ok) {
			return { myControls: [], frameworks: [], currentUser: locals.user || null };
		}
		const data = await res.json();
		const list: any[] = [];
		const frameworks: any[] = (data.frameworks || []).map((fw: any) => ({ id: fw.id, name: fw.name }));
		const user = locals.user;

		const isSuperOrWebAdmin = Boolean(
			user?.is_superuser ||
			user?.platform_role === 'superadmin' ||
			user?.platform_role === 'webadmin'
		);

		for (const fw of data.frameworks || []) {
			for (const c of fw.controls || []) {
				if (c.assignment) {
					if (isSuperOrWebAdmin || c.assignment.spoc_user?.id === user?.id || c.assignment.spoc_user?.email === user?.email) {
						list.push({ ...c, framework_name: fw.name, framework_id: fw.id });
					}
				}
			}
		}
		return { myControls: list, frameworks, currentUser: locals.user || null };
	} catch (err) {
		console.error('Error loading SPOC controls:', err);
		return { myControls: [], frameworks: [], currentUser: locals.user || null };
	}
};

export const actions: Actions = {
	submitEvidence: async ({ fetch, request }) => {
		try {
			const formData = await request.formData();
			const res = await fetch(`${BASE_API_URL}/evidence-management/submit/`, {
				method: 'POST',
				body: formData
			});

			if (res.ok) {
				const data = await res.json();
				return { success: true, data };
			} else {
				let errText = 'Failed to submit evidence.';
				try {
					const err = await res.json();
					errText = err.error || errText;
				} catch (e) {}
				return { success: false, error: errText };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error submitting evidence.' };
		}
	}
};
