import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';
import { redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch, url, locals }) => {
	const user = locals.user;
	const isSuperOrWebAdmin = Boolean(
		user?.is_superuser ||
		user?.platform_role === 'superadmin' ||
		user?.platform_role === 'webadmin'
	);

	// Off limits for standard User and Admin accounts! Only webadmin & superadmin can manage control assignments
	if (!isSuperOrWebAdmin) {
		throw redirect(303, '/control-assignments/submit');
	}

	try {
		const frameworkId = url.searchParams.get('framework_id') || '';
		const apiUrl = frameworkId
			? `${BASE_API_URL}/control-assignments/controls/?framework_id=${frameworkId}`
			: `${BASE_API_URL}/control-assignments/controls/`;

		const res = await fetch(apiUrl);
		if (!res.ok) {
			console.error(`Failed to load control assignments: status ${res.status}`);
			return {
				frameworks: [],
				spocUsers: [],
				reviewerUsers: [],
				selectedFrameworkId: frameworkId,
				currentUser: user
			};
		}

		const data = await res.json();
		const frameworks = data.frameworks || [];
		const spocUsers = data.spoc_users || [];
		const reviewerUsers = data.reviewer_users || [];

		let selectedFrameworkId = frameworkId;
		if (!selectedFrameworkId && frameworks.length > 0) {
			selectedFrameworkId = frameworks[0].id;
		}

		return {
			frameworks,
			spocUsers,
			reviewerUsers,
			selectedFrameworkId,
			currentUser: user
		};
	} catch (err) {
		console.error('Error loading control assignments in server load:', err);
		return {
			frameworks: [],
			spocUsers: [],
			reviewerUsers: [],
			selectedFrameworkId: '',
			currentUser: user
		};
	}
};

export const actions: Actions = {
	saveAssignment: async ({ fetch, request }) => {
		try {
			const formData = await request.formData();
			const requirement_node_id = formData.get('requirement_node_id')?.toString();
			const framework_id = formData.get('framework_id')?.toString();
			const spoc_user_id = formData.get('spoc_user_id')?.toString() || null;
			const reviewer_user_id = formData.get('reviewer_user_id')?.toString() || null;
			const due_date = formData.get('due_date')?.toString() || null;
			const evidence_requirements = JSON.parse(formData.get('evidence_requirements')?.toString() || '[]');
			const notes = formData.get('notes')?.toString() || '';

			const is_not_applicable = formData.get('is_not_applicable') === 'true';

			if (!requirement_node_id) {
				return { success: false, error: 'Requirement node ID is required.' };
			}

			const res = await fetch(`${BASE_API_URL}/control-assignments/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					requirement_node_id,
					framework_id,
					spoc_user_id,
					reviewer_user_id,
					due_date,
					evidence_requirements,
					notes,
					is_not_applicable
				})
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
				return { success: false, error: errText || `Failed to save assignment (${res.status})` };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error' };
		}
	},

	toggleNA: async ({ fetch, request }) => {
		try {
			const formData = await request.formData();
			const requirement_node_id = formData.get('requirement_node_id')?.toString();
			const framework_id = formData.get('framework_id')?.toString();
			const is_not_applicable = formData.get('is_not_applicable') === 'true';

			if (!requirement_node_id || !framework_id) {
				return { success: false, error: 'Requirement node ID and framework ID are required.' };
			}

			const res = await fetch(`${BASE_API_URL}/control-assignments/toggle-na/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					requirement_node_id,
					framework_id,
					is_not_applicable
				})
			});

			if (res.ok) {
				const data = await res.json();
				return { success: true, data };
			} else {
				let errText = await res.text();
				return { success: false, error: errText || 'Failed to toggle N/A' };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error' };
		}
	},

	bulkAssign: async ({ fetch, request }) => {
		try {
			const formData = await request.formData();
			const assignments = JSON.parse(formData.get('assignments')?.toString() || '[]');

			if (!assignments || assignments.length === 0) {
				return { success: false, error: 'Assignments array is required.' };
			}

			const res = await fetch(`${BASE_API_URL}/control-assignments/bulk/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ assignments })
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
				return { success: false, error: errText || `Failed bulk assignment (${res.status})` };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error' };
		}
	}
};
