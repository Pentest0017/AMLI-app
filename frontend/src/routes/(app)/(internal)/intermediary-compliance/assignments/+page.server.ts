import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const assignRes = await fetch(`${BASE_API_URL}/intermediary-compliance/assignments/`);
		if (assignRes.status === 403) {
			return { assignments: [], allUsers: [], isForbidden: true };
		}
		if (!assignRes.ok) {
			return { assignments: [], allUsers: [], isForbidden: false };
		}
		const data = await assignRes.json();
		const assignments = Array.isArray(data) ? data : data.assignments || [];
		const allUsers = data.all_users || [];

		return { assignments, allUsers, isForbidden: false };
	} catch (err) {
		console.error('Error loading assignments:', err);
		return { assignments: [], allUsers: [], isForbidden: false };
	}
};

export const actions: Actions = {
	saveAssignment: async ({ fetch, request }) => {
		try {
			const formData = await request.formData();
			const domain_id = formData.get('domain_id')?.toString();
			const spoc_user_ids = JSON.parse(formData.get('spoc_user_ids')?.toString() || '[]');
			const approving_admin_ids = JSON.parse(formData.get('approving_admin_ids')?.toString() || '[]');

			if (!domain_id) {
				return { success: false, error: 'Domain ID is required.' };
			}

			const res = await fetch(`${BASE_API_URL}/intermediary-compliance/assignments/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ domain_id, spoc_user_ids, approving_admin_ids })
			});

			if (res.ok) {
				const data = await res.json();
				return { success: true, data };
			} else {
				let errText = '';
				try {
					const errData = await res.json();
					errText = errData.error || errData.detail || errData.message || JSON.stringify(errData);
				} catch (e) {
					errText = await res.text();
				}
				return { success: false, error: errText || `Failed to update assignment (${res.status})` };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error' };
		}
	}
};
